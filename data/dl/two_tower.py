"""
Phase 3: 双塔召回模型（Two-Tower / DSSM）

设计:
  - User Tower: user_id embedding + 用户统计特征 -> MLP -> 32 维（L2 归一化）
  - Item Tower: book_id embedding + category/author embedding + 图书统计特征 -> MLP -> 32 维
  - 训练: in-batch 负采样 InfoNCE（batch 内其他用户的物品即负样本），temperature 0.05
  - 正样本: 训练集全部交互（召回阶段不区分分数高低，评分本身即显式兴趣信号；
            分数区分交给精排层 >=7 二值化——两阶段各司其职）
评测:
  1. 双塔召回独立指标: 每测试用户 Top-100 检索 HR@100 / Recall@100
  2. 端到端: 双塔 Top-100 并入召回候选池 -> DeepFM 精排 -> 对比 Hybrid 基线
输出:
  two_tower_results.json  指标
  item_emb.npy            物品向量（供 Faiss 索引）
  user_tower.onnx         用户塔（在线计算查询向量）
"""

import csv
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import faiss

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.environ.get("DL_DATA_DIR") or SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
from baseline import load_books, load_test, load_train  # noqa: E402
from deepfm import build_stat_features, build_vocabs  # noqa: E402
from metrics import evaluate_all  # noqa: E402

SEED = 42
TOWER_DIM = 32
BATCH = 1024
EPOCHS = 20
LR = 2e-3
TAU = 0.1
RECALL_K = 100


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- 模型 ----------------

class UserTower(nn.Module):
    def __init__(self, n_users, n_num, dim=TOWER_DIM):
        super().__init__()
        self.emb = nn.Embedding(n_users, dim)
        self.mlp = nn.Sequential(nn.Linear(dim + n_num, 64), nn.ReLU(), nn.Linear(64, dim))

    def forward(self, uid, num):
        return self.mlp(torch.cat([self.emb(uid), num], dim=-1))


class ItemTower(nn.Module):
    def __init__(self, n_books, n_cats, n_authors, n_num, dim=TOWER_DIM):
        super().__init__()
        # 跳过空词表字段（如 MovieLens 无作者），输入位置保持不变
        sizes = [n_books, n_cats, n_authors]
        self.active = [i for i, n in enumerate(sizes) if n > 0]
        dims = {0: dim, 1: dim // 2, 2: dim // 2}
        self.embeddings = nn.ModuleList([nn.Embedding(sizes[i], dims[i]) for i in self.active])
        emb_total = sum(dims[i] for i in self.active)
        self.mlp = nn.Sequential(nn.Linear(emb_total + n_num, 64), nn.ReLU(), nn.Linear(64, dim))

    def forward(self, bid, cat_idx, auth_idx, num):
        inputs = [bid, cat_idx, auth_idx]
        parts = [emb(inputs[i]) for i, emb in zip(self.active, self.embeddings)]
        x = torch.cat(parts + [num], dim=-1)
        return self.mlp(x)


# ---------------- 训练 ----------------

def train(user_ids, book_ids, cat_idx, auth_idx, u_num, b_num, model_u, model_i):
    """in-batch InfoNCE：batch 内其他用户的物品即负样本，逐 batch 训练"""
    torch.manual_seed(SEED)
    opt = torch.optim.Adam(list(model_u.parameters()) + list(model_i.parameters()), lr=LR)
    n = len(user_ids)
    n_val = max(1, int(n * 0.05))
    perm = torch.randperm(n)
    tr_idx, va_idx = perm[n_val:], perm[:n_val]

    def batch_loss(idx, train_mode):
        model_u.train(train_mode)
        model_i.train(train_mode)
        total, cnt = 0.0, 0
        for i in range(0, len(idx), BATCH):
            b = idx[i:i + BATCH]
            u = torch.nn.functional.normalize(model_u(user_ids[b], u_num[b]), dim=-1)
            it = torch.nn.functional.normalize(
                model_i(book_ids[b], cat_idx[b], auth_idx[b], b_num[b]), dim=-1)
            logits = u @ it.T / TAU
            loss = nn.functional.cross_entropy(logits, torch.arange(b.size(0)))
            if train_mode:
                opt.zero_grad()
                loss.backward()
                opt.step()
            else:
                total += loss.item() * b.size(0)
                cnt += b.size(0)
        return total / cnt if cnt else 0.0

    best_loss, best_state, patience = float("inf"), None, 0
    for epoch in range(EPOCHS):
        batch_loss(tr_idx, train_mode=True)
        with torch.no_grad():
            val = batch_loss(va_idx, train_mode=False)
            tr = batch_loss(tr_idx[: BATCH * 4], train_mode=False)  # 抽样评估训练损失
        log(f"  epoch {epoch + 1}: train_loss={tr:.4f} val_loss={val:.4f}")
        if val < best_loss - 1e-3:
            best_loss, patience = val, 0
            best_state = ({k: v.clone() for k, v in model_u.state_dict().items()},
                          {k: v.clone() for k, v in model_i.state_dict().items()})
        else:
            patience += 1
            if patience >= 2:
                log(f"  early stop @ epoch {epoch + 1}")
                break
    model_u.load_state_dict(best_state[0])
    model_i.load_state_dict(best_state[1])


# ---------------- 主流程 ----------------

def main():
    t0 = time.time()
    log("加载数据...")
    train_data = load_train()
    test_truth = load_test()
    books = load_books()
    test_users = list(test_truth.keys())

    vocabs = build_vocabs(train_data, books)
    num_feats, _ = build_stat_features(train_data, books)
    n_users, n_books = len(vocabs["user"]), len(vocabs["book"])
    n_cats, n_authors = len(vocabs["category"]), len(vocabs["author"])
    log(f"user={n_users}, book={n_books}, cat={n_cats}, author={n_authors}")

    # 交互序列 + 数值特征
    pos = [(uid, bid) for uid, rs in train_data.items() for bid, _ in rs]
    u_ids = torch.tensor([vocabs["user"][uid] for uid, _ in pos])
    b_ids = torch.tensor([vocabs["book"][bid] for _, bid in pos])
    cats = torch.tensor([vocabs["category"].get(books[bid][0], 0) for _, bid in pos])
    auths = torch.tensor([vocabs["author"].get(books[bid][1], 0) for _, bid in pos])

    u_num_arr = np.array([num_feats.get(("user", uid), [0.0, 0.0]) for uid, _ in pos], dtype=np.float32)
    b_num_arr = np.array([num_feats.get(("book", bid), [0.0, 0.0, 0.0]) for _, bid in pos], dtype=np.float32)
    u_mean, u_std = u_num_arr.mean(0), u_num_arr.std(0) + 1e-6
    b_mean, b_std = b_num_arr.mean(0), b_num_arr.std(0) + 1e-6
    # 保存归一化统计量（模型服务推理时需要）
    torch.save({"u_mean": u_mean, "u_std": u_std, "b_mean": b_mean, "b_std": b_std},
               os.path.join(HERE, "user_tower_meta.pt"))
    u_num = torch.tensor((u_num_arr - u_mean) / u_std)
    b_num = torch.tensor((b_num_arr - b_mean) / b_std)

    model_u = UserTower(n_users, 2)
    model_i = ItemTower(n_books, n_cats, n_authors, 3)
    log(f"参数量: user塔 {sum(p.numel() for p in model_u.parameters()):,} / item塔 {sum(p.numel() for p in model_i.parameters()):,}")

    log("训练双塔（in-batch InfoNCE）...")
    train(u_ids, b_ids, cats, auths, u_num, b_num, model_u, model_i)

    # 物品向量全量导出 + Faiss
    model_i.eval()
    with torch.no_grad():
        all_b = torch.arange(n_books)
        all_cat = torch.tensor([vocabs["category"].get(books[bid][0], 0)
                                for bid in sorted(books.keys())])
        all_auth = torch.tensor([vocabs["author"].get(books[bid][1], 0)
                                 for bid in sorted(books.keys())])
        all_num = np.array([num_feats.get(("book", bid), [0.0, 0.0, 0.0])
                            for bid in sorted(books.keys())], dtype=np.float32)
        all_num = torch.tensor((all_num - b_mean) / b_std)
        item_vecs = model_i(all_b, all_cat, all_auth, all_num)
        item_vecs = torch.nn.functional.normalize(item_vecs, dim=-1).numpy()
    np.save(os.path.join(HERE, "item_emb.npy"), item_vecs)
    index = faiss.IndexFlatIP(TOWER_DIM)
    index.add(item_vecs.astype(np.float32))
    faiss.write_index(index, os.path.join(HERE, "item_emb.faiss"))
    log(f"Faiss 索引已构建: {n_books} 个 32 维向量")

    # 双塔召回独立评测: HR@100
    book_id_list = sorted(books.keys())
    model_u.eval()
    recs = {}
    with torch.no_grad():
        for uid in test_users:
            u_idx = torch.tensor([vocabs["user"][uid]])
            u_n = np.array([num_feats.get(("user", uid), [0.0, 0.0])], dtype=np.float32)
            u_n = torch.tensor((u_n - u_mean) / u_std)
            q = torch.nn.functional.normalize(model_u(u_idx, u_n), dim=-1).numpy().astype(np.float32)
            _, ids = index.search(q, RECALL_K)
            recs[uid] = [book_id_list[i] for i in ids[0]]
    m100 = evaluate_all(recs, test_truth, ks=(100,))
    log("双塔召回独立: " + ", ".join(f"{k}={v:.4f}" for k, v in m100.items()))

    # 导出用户塔 ONNX
    model_u.eval()
    torch.onnx.export(model_u, (u_ids[:1], u_num[:1]), os.path.join(HERE, "user_tower.onnx"),
                      input_names=["user_id", "user_num"], output_names=["user_vec"],
                      dynamic_axes={"user_id": {0: "batch"}, "user_num": {0: "batch"}})
    log("user_tower.onnx 已导出")

    # 保存召回结果，端到端评测由 eval_end2end.py 在独立进程中执行
    # （本进程 torch 内存分配器不向 OS 归还内存，无法再重建相似度矩阵）
    with open(os.path.join(HERE, "two_tower_recs.json"), "w", encoding="utf-8") as f:
        json.dump(recs, f)
    with open(os.path.join(HERE, "two_tower_results.json"), "w", encoding="utf-8") as f:
        json.dump({"TwoTower召回(HR@100)": m100}, f, ensure_ascii=False, indent=2)
    log("召回结果已保存，端到端评测请运行: python eval_end2end.py")

    log(f"完成，总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
