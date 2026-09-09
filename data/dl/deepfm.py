"""
Phase 2: DeepFM 精排模型（v2：策略分入模）

设计（业界 Rank 模型通行做法）:
  - 多路召回的"策略分"作为精排模型特征输入：UserCF 分 / ItemCF 分 / 内容画像分 / 热度分，
    模型在策略融合基础上做深度交叉与校准 —— 召回侧出策略分，精排侧做排序。
  - 样本: 评分 >= 7 为正样本，流行度^0.75 加权负采样，正:负 = 1:4
  - 特征: 稀疏 [user/book/category/author/publisher] + 稠密
      [用户评分次数/均值, 图书被评次数/均值/log流行度, cf分, icf分, 内容分, 热度分]（9 维）
  - 结构: DeepFM（LR + FM + DNN(64->32, BatchNorm)），sigmoid
  - 统计特征只用训练集计算；策略分与在线一致（全量训练历史，评估物品不在历史中，无泄漏）
评测口径: 与 Hybrid 基线同一召回候选池（4 路 Top-20 并集），只替换排序层
输出: deepfm.onnx / deepfm_bundle.pt / deepfm_results.json / candidate_pools.json
"""

import csv
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.environ.get("DL_DATA_DIR") or SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
from baseline import (build_item_sim, build_user_sim, load_books, load_train,  # noqa: E402
                      load_test, Popularity, ItemCF, UserCF, Content, CHANNEL_TOP)
from metrics import evaluate_all  # noqa: E402

SEED = 42
EMB_DIM = 16
BATCH = 4096
EPOCHS = 12
LR = 1e-3
NEG_PER_POS = 4
POS_THRESHOLD = 7.0
VAL_RATIO = 0.05
POOL_TOP = 20
N_NUM = 9  # 5 统计 + 4 策略分


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- 词表 / 统计特征 ----------------

def build_vocabs(train, books):
    users = set(train.keys())
    cats, authors, pubs = set(), set(), set()
    for _, (cat, auth, pub) in books.items():
        if cat:
            cats.add(cat)
        if auth:
            authors.add(auth)
        if pub:
            pubs.add(pub)
    v = {"user": {u: i for i, u in enumerate(sorted(users))},
         "book": {b: i for i, b in enumerate(sorted(books.keys()))},
         "category": {c: i for i, c in enumerate(sorted(cats))},
         "author": {a: i for i, a in enumerate(sorted(authors))},
         "publisher": {p: i for i, p in enumerate(sorted(pubs))}}
    return v


def build_stat_features(train, books):
    """统计特征（只用训练集）"""
    u_cnt, u_sum = defaultdict(int), defaultdict(float)
    b_cnt, b_sum = defaultdict(int), defaultdict(float)
    for uid, ratings in train.items():
        for bid, score in ratings:
            u_cnt[uid] += 1
            u_sum[uid] += score
            b_cnt[bid] += 1
            b_sum[bid] += score
    num = {}
    for uid in u_cnt:
        num[("user", uid)] = [u_cnt[uid], u_sum[uid] / u_cnt[uid]]
    for bid in b_cnt:
        num[("book", bid)] = [b_cnt[bid], b_sum[bid] / b_cnt[bid], math.log(1 + b_cnt[bid])]
    return num, dict(b_cnt)


# ---------------- 策略分（召回侧输出，作为精排特征） ----------------

class ChannelScores:
    """每用户预计算 4 路策略分字典（与在线口径一致：全量训练历史）"""

    def __init__(self, train, books, item_sim, user_sim, b_pop):
        self.train = train
        self.books = books
        self.item_sim = item_sim
        self.user_sim = user_sim
        self.b_pop = b_pop
        self._content = Content(train, books)
        self._cache = {}

    def get(self, uid):
        # 单条目缓存：顺序按用户批处理时零内存增长（稠密数据每用户策略分很大）
        if self._cache.get("uid") == uid:
            return self._cache["data"]
        hist = dict(self.train[uid])

        # UserCF 分: 邻居全部评分加权
        cf = defaultdict(float)
        neighbors = self.user_sim.get(uid, {})
        sim_sum = sum(neighbors.values())
        if sim_sum > 0:
            for v, sim in neighbors.items():
                for b, s in self.train.get(v, ()):
                    cf[b] += s * sim / sim_sum

        # ItemCF 分: 高分书 x Top-20 相似
        icf = defaultdict(float)
        for b, s in hist.items():
            if s >= 7:
                for c, sim in self.item_sim.get(b, {}).items():
                    icf[c] += sim * s

        # 内容画像分（评分时现算，此处先建画像）
        cw, aw, pw = self._content.profile(uid, self.train)
        profile = (cw, aw, pw)

        data = (cf, icf, profile)
        self._cache = {"uid": uid, "data": data}
        return data

    def content_score(self, profile, bid):
        cw, aw, pw = profile
        cat, auth, pub = self.books.get(bid, ("", "", ""))
        cm = max(cw.values()) if cw else 1.0
        am = max(aw.values()) if aw else 1.0
        pm = max(pw.values()) if pw else 1.0
        return 0.5 * (cw.get(cat, 0.0) / cm) + 0.35 * (aw.get(auth, 0.0) / am) + 0.15 * (pw.get(pub, 0.0) / pm)

    def clear_cache(self):
        """按批评测时定期调用，避免全量用户策略分常驻内存"""
        self._cache.clear()


# ---------------- 样本 ----------------

def _sparse_idx(uid, bid, vocabs, books):
    cat, auth, pub = books.get(bid, ("", "", ""))
    return [vocabs["user"][uid], vocabs["book"][bid],
            vocabs["category"].get(cat, 0), vocabs["author"].get(auth, 0), vocabs["publisher"].get(pub, 0)]


def _numeric(uid, bid, num_feats, b_pop, ch: ChannelScores):
    cf, icf, profile = ch.get(uid)
    u_cnt, u_avg = num_feats.get(("user", uid), [0.0, 0.0])
    b_cnt, b_avg, b_logpop = num_feats.get(("book", bid), [0.0, 0.0, 0.0])
    return [u_cnt, u_avg, b_cnt, b_avg, b_logpop,
            cf.get(bid, 0.0), icf.get(bid, 0.0), ch.content_score(profile, bid), float(b_pop.get(bid, 0))]


def build_samples(train, books, vocabs, num_feats, b_pop, ch: ChannelScores):
    log("构造正负样本（含策略分特征）...")
    pos = [(uid, bid) for uid, rs in train.items() for bid, s in rs if s >= POS_THRESHOLD]
    log(f"  正样本 {len(pos):,}")
    weights = np.array([b_pop.get(b, 1) ** 0.75 for b in sorted(books.keys())], dtype=np.float64)
    weights /= weights.sum()
    book_ids = sorted(books.keys())
    rated = {uid: {b for b, _ in rs} for uid, rs in train.items()}
    rng = np.random.default_rng(SEED)

    samples = []
    for uid, bid in pos:
        samples.append((_sparse_idx(uid, bid, vocabs, books), _numeric(uid, bid, num_feats, b_pop, ch), 1.0))
    for uid, _ in pos:
        ex = rated[uid]
        for _ in range(NEG_PER_POS):
            b = book_ids[rng.choice(len(book_ids), p=weights)]
            tries = 0
            while b in ex and tries < 20:
                b = book_ids[rng.choice(len(book_ids), p=weights)]
                tries += 1
            samples.append((_sparse_idx(uid, b, vocabs, books), _numeric(uid, b, num_feats, b_pop, ch), 0.0))
    log(f"  总样本 {len(samples):,}")
    return samples


# ---------------- 模型 ----------------

class DeepFM(nn.Module):
    def __init__(self, voc_sizes, n_num=N_NUM, emb_dim=EMB_DIM):
        super().__init__()
        # 跳过空词表字段（如 MovieLens 无作者/出版社），输入列位置保持不变
        self.active = [i for i, vs in enumerate(voc_sizes) if vs > 0]
        self.voc_sizes = [vs for vs in voc_sizes if vs > 0]
        self.embeddings = nn.ModuleList([nn.Embedding(vs, emb_dim) for vs in self.voc_sizes])
        self.linear = nn.ModuleList([nn.Embedding(vs, 1) for vs in self.voc_sizes])
        self.num_linear = nn.Linear(n_num, 1)
        dnn_in = emb_dim * len(self.voc_sizes) + n_num
        self.dnn = nn.Sequential(
            nn.Linear(dnn_in, 64), nn.BatchNorm1d(64), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(64, 32), nn.BatchNorm1d(32), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(32, 1),
        )

    def forward(self, sparse, numeric):
        embs = [self.embeddings[k](sparse[:, i]) for k, i in enumerate(self.active)]
        emb_stack = torch.stack(embs, dim=1)  # (B, F, D)
        sum_sq = emb_stack.sum(dim=1).pow(2)
        sq_sum = emb_stack.pow(2).sum(dim=1)
        fm = 0.5 * (sum_sq - sq_sum).sum(dim=1, keepdim=True)
        lr_part = sum(self.linear[k](sparse[:, i]) for k, i in enumerate(self.active))
        lr_part = lr_part.sum(dim=1, keepdim=True) + self.num_linear(numeric)
        dnn = self.dnn(torch.cat([emb_stack.reshape(sparse.size(0), -1), numeric], dim=1))
        return (lr_part + fm + dnn).squeeze(-1)


# ---------------- 训练 ----------------

def _auc(y, p):
    order = np.argsort(p)  # 升序：高分排名大
    y = y[order]
    n_pos = y.sum()
    if n_pos == 0 or n_pos == len(y):
        return 0.5
    ranks = np.arange(1, len(y) + 1)[y > 0]
    return (ranks.sum() - n_pos * (n_pos + 1) / 2) / (n_pos * (len(y) - n_pos))


def train_model(model, samples):
    torch.manual_seed(SEED)
    random.seed(SEED)
    random.shuffle(samples)
    arr = np.array([s[1] for s in samples], dtype=np.float32)
    mean, std = arr.mean(axis=0), arr.std(axis=0) + 1e-6
    arr = (arr - mean) / std

    sparse = torch.tensor([s[0] for s in samples], dtype=torch.long)
    numeric = torch.tensor(arr, dtype=torch.float32)
    labels = torch.tensor([s[2] for s in samples], dtype=torch.float32)

    n_val = int(len(samples) * VAL_RATIO)
    tr_sp, tr_num, tr_y = sparse[n_val:], numeric[n_val:], labels[n_val:]
    va_sp, va_num, va_y = sparse[:n_val], numeric[:n_val], labels[:n_val]
    log(f"训练样本 {len(tr_sp):,} / 验证样本 {len(va_sp):,}")

    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.BCEWithLogitsLoss()
    best_auc, best_state, patience = 0.0, None, 0

    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(len(tr_sp))
        total_loss, nb = 0.0, 0
        for i in range(0, len(perm), BATCH):
            idx = perm[i:i + BATCH]
            opt.zero_grad()
            loss = loss_fn(model(tr_sp[idx], tr_num[idx]), tr_y[idx])
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(idx)
            nb += len(idx)
        model.eval()
        with torch.no_grad():
            va_out = model(va_sp, va_num).sigmoid().numpy()
            auc = _auc(va_y.numpy(), va_out)
        log(f"  epoch {epoch + 1}: loss={total_loss / nb:.4f} val_auc={auc:.4f}")
        if auc > best_auc + 1e-4:
            best_auc, best_state, patience = auc, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 3:
                log(f"  early stop @ epoch {epoch + 1}")
                break
    model.load_state_dict(best_state)
    return mean, std


# ---------------- 候选池（与 Hybrid 基线同口径） ----------------

def build_candidate_pools(test_users, channels, content_cache, rated_sets):
    user_cf, item_cf, content, popular = channels
    pools = {}
    for uid in test_users:
        rated = rated_sets[uid]
        pool = set()
        for b, _ in user_cf.recommend(uid, rated, CHANNEL_TOP):
            pool.add(b)
        for b, _ in item_cf.recommend(rated, CHANNEL_TOP):
            pool.add(b)
        for b, _ in content_cache[uid]:
            pool.add(b)
        for b, _ in popular.recommend(rated, CHANNEL_TOP):
            pool.add(b)
        pools[uid] = sorted(pool)
    return pools


# ---------------- 主流程 ----------------

def main():
    t0 = time.time()
    log("加载数据...")
    train = load_train()
    test_truth = load_test()
    books = load_books()
    test_users = list(test_truth.keys())
    vocabs = build_vocabs(train, books)
    num_feats, b_pop = build_stat_features(train, books)
    log(f"  词表: user={len(vocabs['user'])}, book={len(vocabs['book'])}, "
        f"category={len(vocabs['category'])}, author={len(vocabs['author'])}, publisher={len(vocabs['publisher'])}")

    log("构建相似度（策略分特征依赖）...")
    item_sim = build_item_sim(train)
    user_sim = build_user_sim(train)
    ch = ChannelScores(train, books, item_sim, user_sim, b_pop)

    samples = build_samples(train, books, vocabs, num_feats, b_pop, ch)
    voc_sizes = [len(vocabs[k]) for k in ("user", "book", "category", "author", "publisher")]
    model = DeepFM(voc_sizes)
    log(f"参数量: {sum(p.numel() for p in model.parameters()):,}")
    mean, std = train_model(model, samples)

    torch.save({"state": model.state_dict(), "mean": mean, "std": std},
               os.path.join(HERE, "deepfm_bundle.pt"))

    onnx_path = os.path.join(HERE, "deepfm.onnx")
    model.eval()
    torch.onnx.export(model, (torch.zeros(1, 5, dtype=torch.long), torch.zeros(1, N_NUM, dtype=torch.float32)),
                      onnx_path, input_names=["sparse", "numeric"], output_names=["logit"],
                      dynamic_axes={"sparse": {0: "batch"}, "numeric": {0: "batch"}})
    log(f"ONNX 已导出: {onnx_path}")

    # ---- 评测：同一候选池，只换排序层 ----
    log("构建召回候选池与策略分...")
    channels = (UserCF(user_sim, train), ItemCF(item_sim), Content(train, books), Popularity(train))
    rated_sets = {uid: {b: s for b, s in train[uid]} for uid in test_users}
    content_cache = {}
    for uid in test_users:
        content_cache[uid] = channels[2].recommend(uid, rated_sets[uid], CHANNEL_TOP,
                                                   channels[2].profile(uid, train))
    pools = build_candidate_pools(test_users, channels, content_cache, rated_sets)
    log(f"  平均候选数: {np.mean([len(p) for p in pools.values()]):.1f}")

    log("DeepFM 对候选打分...")
    with torch.no_grad():
        recs = {}
        for uid in test_users:
            pool = pools[uid]
            if not pool:
                recs[uid] = []
                continue
            sp = torch.tensor([_sparse_idx(uid, b, vocabs, books) for b in pool], dtype=torch.long)
            nums = np.array([_numeric(uid, b, num_feats, b_pop, ch) for b in pool], dtype=np.float32)
            nums = (nums - mean) / std
            scores = model(sp, torch.tensor(nums)).sigmoid().numpy()
            order = np.argsort(-scores)
            recs[uid] = [pool[i] for i in order[:10]]

    m = evaluate_all(recs, test_truth)
    log("DeepFM: " + ", ".join(f"{k}={v:.4f}" for k, v in m.items()))

    with open(os.path.join(HERE, "deepfm_results.json"), "w", encoding="utf-8") as f:
        json.dump({"DeepFM精排": m}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "candidate_pools.json"), "w", encoding="utf-8") as f:
        json.dump(pools, f)

    with open(os.path.join(HERE, "baseline_results.json"), encoding="utf-8") as f:
        hyb = json.load(f)["results"]["Hybrid(现有基线)"]
    log("===== 对比（同一候选池，只换排序层）=====")
    for k in ("HR@10", "NDCG@10", "HR@20", "NDCG@20"):
        if hyb.get(k, 0) > 0:
            log(f"  {k}: 基线 {hyb[k]:.4f} -> DeepFM {m[k]:.4f} ({(m[k] - hyb[k]) / hyb[k] * 100:+.1f}%)")
    log(f"完成，总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
