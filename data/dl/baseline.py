"""
Phase 1c: 基线复刻与离线评测

忠实复刻 Java 侧现有 4 路策略与混合加权逻辑（HybridRecommendService），
在同一测试集（留一法）上跑出基线指标，作为 DeepFM / 双塔的对比基准。

口径对照（与 Java 代码一致）:
  - Popularity : 按被评分次数排序（排除已评分书）
  - ItemCF     : 高分书(>=7) × Top-20 相似书，score += sim * rating
  - UserCF     : Top-100 邻居（余弦, 共同评分>=2），score = Σ(rating*sim)/Σsim
  - Content    : 画像 = 全量评分(score/10)按分类/作者/出版社累积，逐属性 max 归一化，
                 打分 = 0.5*分类 + 0.35*作者 + 0.15*出版社，偏好分类书优先，不足 2N 再全量
  - Hybrid     : 按评分量分档取权重（<5: 0/0.1/0.4/0.5, 5-50: 0.2/0.2/0.4/0.2, >50: 0.35/0.3/0.25/0.1），
                 各通道 Top-20 做 min-max 归一化后加权合并取 Top-10

输出:
  baseline_report.md   基线报告
  baseline_results.json 指标（供后续模型对比）
"""

import csv
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import scipy.sparse as sp

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.environ.get("DL_DATA_DIR") or SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
from metrics import evaluate_all  # noqa: E402

TOP_K_ITEM_SIM = int(os.environ.get("DL_TOP_K_ITEM", "20"))     # Java ItemSimilarityService.TOP_K
TOP_K_USER_NEIGHBORS = int(os.environ.get("DL_TOP_K_USER", "100"))  # Java UserSimilarityService.TOP_K
# 最小共同评分阈值: Book-Crossing 默认 2（Java 口径）；稠密数据可调高（文献 ItemKNN 常用 5）
COMMON_ITEM = int(os.environ.get("DL_COMMON_ITEM", "2"))
COMMON_USER = int(os.environ.get("DL_COMMON_USER", "2"))
# 归一化加权聚合（文献 ItemKNN 标准做法: score = Σsim·r / Σsim）
NORM_CF = os.environ.get("DL_NORM_CF") == "1"
HYBRID_TOP = 10
CHANNEL_TOP = 20          # Java Hybrid: topN * 2


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- 数据加载 ----------------

def load_train():
    user_ratings = defaultdict(list)
    with open(os.path.join(HERE, "train.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            user_ratings[int(row["user_id"])].append((int(row["book_id"]), float(row["score"])))
    return user_ratings


def load_test():
    truth = defaultdict(list)
    with open(os.path.join(HERE, "test.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            truth[int(row["user_id"])].append(int(row["book_id"]))
    return truth


def load_books():
    books = {}
    with open(os.path.join(HERE, "books.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            books[int(row["id"])] = (row["category"], row["author"], row["publisher"])
    return books


# ---------------- 相似度构建 ----------------
# scipy 稀疏矩阵实现：dot/norm 只在共同维度上累计，与 Java 余弦口径完全一致
# （增量版在稠密数据下配对爆炸，此实现可扩展到任意规模）

def _to_sparse(user_ratings):
    """评分矩阵 X（用户×物品）+ 紧凑索引映射
    DL_ADJUSTED=1 时做均值中心化（调整余弦，ML-1M 等稠密数据的标准做法）"""
    user_index = {u: i for i, u in enumerate(sorted(user_ratings.keys()))}
    book_index = {b: i for i, b in enumerate(
        sorted({b for rs in user_ratings.values() for b, _ in rs}))}
    rows, cols, vals = [], [], []
    for uid, ratings in user_ratings.items():
        ui = user_index[uid]
        for b, s in ratings:
            rows.append(ui)
            cols.append(book_index[b])
            vals.append(s)
    X = sp.csr_matrix((vals, (rows, cols)),
                      shape=(len(user_index), len(book_index)), dtype=np.float32)
    if os.environ.get("DL_ADJUSTED") == "1":
        # 用户均值中心化：Xc = X - mean(u) ⊙ B（消除评分标度导致的全 1.0 平票）
        row_sum = np.asarray(X.sum(axis=1)).ravel()
        row_cnt = np.asarray((X != 0).sum(axis=1)).ravel()
        row_mean = row_sum / np.maximum(row_cnt, 1)
        X = (X - sp.diags(row_mean) @ (X != 0)).tocsr()
    B = X.copy()
    B.data[:] = 1.0  # 二值矩阵（共同计数用）
    X2 = X.copy()
    X2.data = X2.data ** 2
    return X, B, X2, user_index, book_index


def _sim_matrix(dot, n1, n2, common, min_common):
    """余弦相似度矩阵: sim = dot / sqrt(n1*n2)，仅保留共同维度 >= 阈值 且 sim > 0"""
    sim = np.zeros_like(dot, dtype=np.float32)
    mask = (common >= min_common) & (n1 > 0) & (n2 > 0)
    sim[mask] = dot[mask] / np.sqrt(n1[mask] * n2[mask])
    sim[sim <= 0] = 0
    return sim


def build_item_sim(user_ratings):
    """物品-物品余弦相似度（共同评分用户 >= COMMON_ITEM），每本书保留 Top-20"""
    X, B, X2, _, book_index = _to_sparse(user_ratings)
    common = (B.T @ B).toarray()          # 共同评分用户数
    dot = (X.T @ X).toarray()             # 共同维度点积
    n1 = (X2.T @ B).toarray()             # 物品 i 在共同维度上的范数²
    n2 = n1.T
    sim = _sim_matrix(dot, n1, n2, common, COMMON_ITEM)
    ids = sorted(book_index, key=book_index.get)

    result = defaultdict(dict)
    for i in range(len(ids)):
        row = sim[i]
        if i < len(ids) - 1:
            # 去掉自己（对角）
            row = row.copy()
            row[i] = 0
        idx = np.argpartition(-row, min(TOP_K_ITEM_SIM, len(row) - 1))[:TOP_K_ITEM_SIM]
        for j in idx:
            if row[j] > 0:
                result[ids[i]][ids[j]] = float(row[j])
    return result


def build_user_sim(user_ratings):
    """用户-用户余弦相似度（共同评分书 >= COMMON_USER），每用户保留 Top-100 邻居
    分块计算避免 6040x6040 全矩阵驻留内存"""
    X, B, X2, user_index, _ = _to_sparse(user_ratings)
    n_users = len(user_index)
    ids = sorted(user_index, key=user_index.get)
    BLOCK = 512

    result = defaultdict(dict)
    for start in range(0, n_users, BLOCK):
        end = min(start + BLOCK, n_users)
        Xb, Bb, X2b = X[start:end], B[start:end], X2[start:end]
        common = (Bb @ B.T).toarray()
        dot = (Xb @ X.T).toarray()
        n1 = (X2b @ B.T).toarray()        # 块内用户 u 的范数²（共同书籍）
        n2 = (X2 @ Bb.T).toarray().T      # 邻居 v 的范数²
        sim = _sim_matrix(dot, n1, n2, common, COMMON_USER)
        for k in range(end - start):
            row = sim[k]
            row = row.copy()
            row[start + k] = 0
            idx = np.argpartition(-row, min(TOP_K_USER_NEIGHBORS, len(row) - 1))[:TOP_K_USER_NEIGHBORS]
            for j in idx:
                if row[j] > 0:
                    result[ids[start + k]][ids[j]] = float(row[j])
    return result


# ---------------- 四路策略 ----------------

class Popularity:
    """热门：被评分次数降序，排除已评分书"""

    def __init__(self, train):
        counts = defaultdict(int)
        for ratings in train.values():
            for b, _ in ratings:
                counts[b] += 1
        self.hot = sorted(counts.items(), key=lambda x: -x[1])

    def recommend(self, rated, top_n):
        return [(b, float(c)) for b, c in self.hot if b not in rated][:top_n]


class ItemCF:
    """物品协同过滤
    - Java 口径（默认）: 高分书(>=7) 的 Top-20 相似书，score += sim * rating
    - 文献口径（DL_NORM_CF=1）: 全部已评物品聚合，归一化加权 score = Σsim·r / Σsim"""

    def __init__(self, item_sim):
        self.sim = item_sim

    def recommend(self, rated, top_n):
        scores = defaultdict(float)
        sim_sum = defaultdict(float)
        items = list(rated.items()) if NORM_CF else [(b, s) for b, s in rated.items() if s >= 7]
        if not items:
            return []
        # 文献模式: 偏差聚合 score(c) = mean_u + Σ sim·(r - mean_u) / Σ sim
        # （原始分聚合在 8~10 分扎堆的数据上会退化成满分级排序，失去区分度）
        my_mean = sum(s for _, s in items) / len(items) if NORM_CF else 0.0
        for b, r in items:
            for c, s in self.sim.get(b, {}).items():
                if c not in rated:
                    scores[c] += s * (r - my_mean)
                    sim_sum[c] += s
        if NORM_CF:
            for c in scores:
                if sim_sum[c] > 0:
                    scores[c] = my_mean + scores[c] / sim_sum[c]
        return sorted(scores.items(), key=lambda x: -x[1])[:top_n]


class UserCF:
    """用户协同过滤：Top-100 邻居全部评分加权聚合
    - Java 口径（默认）: score = Σ(rating*sim)/Σsim
    - 文献口径（DL_NORM_CF=1）: 均值偏差公式 pred = mean_u + Σ sim·(r_vi - mean_v) / Σsim"""

    def __init__(self, user_sim, train):
        self.sim = user_sim
        self.train = train

    def recommend(self, uid, rated, top_n):
        neighbors = self.sim.get(uid)
        if not neighbors:
            return []
        scores = defaultdict(float)
        sim_sum = sum(neighbors.values())
        if NORM_CF:
            my_mean = sum(rated.values()) / len(rated) if rated else 0.0
            for v, sim in neighbors.items():
                rs = self.train.get(v, ())
                if not rs:
                    continue
                v_mean = sum(s for _, s in rs) / len(rs)
                for b, s in rs:
                    if b not in rated:
                        scores[b] += sim * (s - v_mean) / sim_sum
            for b in scores:
                scores[b] += my_mean
        else:
            for v, sim in neighbors.items():
                for b, s in self.train.get(v, ()):
                    if b not in rated:
                        scores[b] += s * sim / sim_sum
        return sorted(scores.items(), key=lambda x: -x[1])[:top_n]


class Content:
    """内容画像：分类(0.5) + 作者(0.35) + 出版社(0.15)，偏好分类书优先，不足 2N 再全量"""

    def __init__(self, train, books):
        self.books = books
        self.cat_books = defaultdict(list)
        for bid, (cat, _, _) in books.items():
            self.cat_books[cat].append(bid)

    def profile(self, uid, train):
        cw, aw, pw = defaultdict(float), defaultdict(float), defaultdict(float)
        for b, s in train[uid]:
            cat, auth, pub = self.books.get(b, ("", "", ""))
            w = s / 10.0
            if cat:
                cw[cat] += w
            if auth:
                aw[auth] += w
            if pub:
                pw[pub] += w
        cm = max(cw.values()) if cw else 1.0
        am = max(aw.values()) if aw else 1.0
        pm = max(pw.values()) if pw else 1.0
        return ({c: w / cm for c, w in cw.items()},
                {a: w / am for a, w in aw.items()},
                {p: w / pm for p, w in pw.items()})

    def recommend(self, uid, rated, top_n, profile=None):
        if profile is None:
            return []  # 画像必须由调用方传入（避免重复构建）
        cw, aw, pw = profile
        scored, seen = [], set()

        def score_book(b):
            if b in seen:
                return
            seen.add(b)
            cat, auth, pub = self.books.get(b, ("", "", ""))
            s = 0.5 * cw.get(cat, 0.0) + 0.35 * aw.get(auth, 0.0) + 0.15 * pw.get(pub, 0.0)
            if s > 0:
                scored.append((b, s))

        for cat in cw:  # 偏好分类书优先
            for b in self.cat_books[cat]:
                if b not in rated:
                    score_book(b)
        if len(scored) < top_n * 2:  # Java: 不足 topN*2 再全量
            for b in self.books:
                if b not in rated:
                    score_book(b)
        scored.sort(key=lambda x: -x[1])
        return scored[:top_n]


# ---------------- 混合加权（复刻 HybridRecommendService） ----------------

def compute_weights(cnt):
    if cnt < 5:
        return (0.0, 0.1, 0.4, 0.5)          # 新用户: 热门为主+内容辅助
    if cnt <= 50:
        return (0.2, 0.2, 0.4, 0.2)          # 中等: 内容为主
    return (0.35, 0.30, 0.25, 0.10)          # 老用户: 协同为主


def minmax(recs):
    if not recs:
        return []
    mx = max(s for _, s in recs)
    mn = min(s for _, s in recs)
    rng = (mx - mn) or 1.0
    return [(b, (s - mn) / rng) for b, s in recs]


def hybrid_recommend(uid, rated, cnt, profile, channels, channel_cache):
    wu, wi, wc, wp = compute_weights(cnt)
    user_cf, item_cf, content, popular = channels
    merged = defaultdict(float)
    if wu > 0:
        for b, s in minmax(user_cf.recommend(uid, rated, CHANNEL_TOP)):
            merged[b] += s * wu
    if wi > 0:
        for b, s in minmax(item_cf.recommend(rated, CHANNEL_TOP)):
            merged[b] += s * wi
    if wc > 0:
        for b, s in minmax(channel_cache["content"][uid]):
            merged[b] += s * wc
    for b, s in minmax(popular.recommend(rated, CHANNEL_TOP)):
        merged[b] += s * wp
    return [(b, s) for b, s in sorted(merged.items(), key=lambda x: -x[1])[:HYBRID_TOP]]


# ---------------- 主流程 ----------------

def main():
    t0 = time.time()
    log("加载数据...")
    train = load_train()
    test_truth = load_test()
    books = load_books()
    test_users = list(test_truth.keys())
    log(f"训练集 {sum(len(v) for v in train.values()):,} 条评分 / 测试用户 {len(test_users):,}")

    log("构建物品相似度（倒排增量累积）...")
    item_sim = build_item_sim(train)
    log(f"  有效相似度条目 {sum(len(v) for v in item_sim.values()):,}")

    log("构建用户相似度...")
    user_sim = build_user_sim(train)
    log(f"  有效邻居条目 {sum(len(v) for v in user_sim.values()):,}")

    popular = Popularity(train)
    item_cf = ItemCF(item_sim)
    user_cf = UserCF(user_sim, train)
    content = Content(train, books)
    channels = (user_cf, item_cf, content, popular)

    rated_sets = {uid: {b: s for b, s in train[uid]} for uid in test_users}

    log("预计算测试用户画像与内容通道...")
    profiles = {}
    content_cache = {}
    for i, uid in enumerate(test_users):
        profiles[uid] = content.profile(uid, train)
        content_cache[uid] = content.recommend(uid, rated_sets[uid], CHANNEL_TOP, profiles[uid])
        if (i + 1) % 2000 == 0:
            log(f"  {i + 1}/{len(test_users)}")
    channel_cache = {"content": content_cache}

    results = {}
    log("评测 Popularity ...")
    recs = {uid: [b for b, _ in popular.recommend(rated_sets[uid], HYBRID_TOP)] for uid in test_users}
    results["Popularity"] = evaluate_all(recs, test_truth)

    log("评测 ItemCF ...")
    recs = {uid: [b for b, _ in item_cf.recommend(rated_sets[uid], HYBRID_TOP)] for uid in test_users}
    results["ItemCF"] = evaluate_all(recs, test_truth)

    log("评测 UserCF ...")
    recs = {uid: [b for b, _ in user_cf.recommend(uid, rated_sets[uid], HYBRID_TOP)] for uid in test_users}
    results["UserCF"] = evaluate_all(recs, test_truth)

    log("评测 ContentBased ...")
    recs = {uid: [b for b, _ in content_cache[uid][:HYBRID_TOP]] for uid in test_users}
    results["ContentBased"] = evaluate_all(recs, test_truth)

    log("评测 Hybrid（手工加权混合，现有系统口径）...")
    tier_counts = defaultdict(int)
    hybrid_recs = {}
    for uid in test_users:
        cnt = len(train[uid])
        tier_counts["<5" if cnt < 5 else "5-50" if cnt <= 50 else ">50"] += 1
        hybrid_recs[uid] = [b for b, _ in hybrid_recommend(uid, rated_sets[uid], cnt, profiles[uid], channels, channel_cache)]
    results["Hybrid(现有基线)"] = evaluate_all(hybrid_recs, test_truth)

    for name, m in results.items():
        log(f"  {name}: " + ", ".join(f"{k}={v:.4f}" for k, v in m.items()))

    with open(os.path.join(HERE, "baseline_results.json"), "w", encoding="utf-8") as f:
        json.dump({"results": results, "tier_distribution": dict(tier_counts)}, f, ensure_ascii=False, indent=2)

    # 报告
    with open(os.path.join(HERE, "baseline_report.md"), "w", encoding="utf-8") as f:
        f.write("# 基线评测报告\n\n")
        f.write(f"- 数据集: Book-Crossing 清洗后 22,808 本书 / 15,083 用户 / 184,738 条评分\n")
        f.write(f"- 切分: 留一法（每用户最后一条评分入测试集，仅保留 >=3 条评分的用户）\n")
        f.write(f"- 测试用户: {len(test_users):,} / 测试样本: {len(test_truth):,}\n")
        f.write(f"- 口径: 与线上 Java 实现一致（相似度阈值、Top-K、权重分档、min-max 归一化）\n")
        f.write(f"- 权重分档分布: {json.dumps(dict(tier_counts), ensure_ascii=False)}\n\n")
        f.write("| 方法 | " + " | ".join(f"{k}" for k in next(iter(results.values()))) + " |\n")
        f.write("|---|" + "---|" * len(next(iter(results.values()))) + "\n")
        for name, m in results.items():
            f.write(f"| {name} | " + " | ".join(f"{v:.4f}" for v in m.values()) + " |\n")
        f.write(f"\n耗时: {time.time() - t0:.1f}s\n")

    log(f"完成，总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
