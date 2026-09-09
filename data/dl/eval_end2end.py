"""
Phase 3b: 端到端评测（独立进程）

双塔 Top-100 并入召回候选池 -> DeepFM 精排 -> 对比 Hybrid 基线。
独立进程原因: 训练进程的 torch 内存分配器不向 OS 归还内存，
重建相似度矩阵需要干净的进程内存。

依赖产物:
  candidate_pools.json  （deepfm.py 生成，4 路通道候选池）
  two_tower_recs.json   （two_tower.py 生成，双塔 Top-100 召回）
  deepfm_bundle.pt      （DeepFM 权重 + 数值特征统计量）
输出:
  two_tower_results.json（补充"双塔+DeepFM端到端"）
"""

import json
import os
import sys
import time

import numpy as np
import torch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.environ.get("DL_DATA_DIR") or SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
from baseline import build_item_sim, build_user_sim, load_books, load_test, load_train  # noqa: E402
from metrics import evaluate_all  # noqa: E402
import deepfm as dm  # noqa: E402

RECALL_K = 100


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    t0 = time.time()
    log("加载数据...")
    train_data = load_train()
    test_truth = load_test()
    books = load_books()
    test_users = list(test_truth.keys())

    with open(os.path.join(HERE, "candidate_pools.json"), encoding="utf-8") as f:
        pools = json.load(f)
    pools = {int(k): v for k, v in pools.items()}
    with open(os.path.join(HERE, "two_tower_recs.json"), encoding="utf-8") as f:
        tower_recs = json.load(f)
    tower_recs = {int(k): v for k, v in tower_recs.items()}
    with open(os.path.join(HERE, "baseline_results.json"), encoding="utf-8") as f:
        hyb = json.load(f)["results"]["Hybrid(现有基线)"]

    log("重建相似度与策略分...")
    item_sim = build_item_sim(train_data)
    user_sim = build_user_sim(train_data)
    vocabs = dm.build_vocabs(train_data, books)
    num_feats, b_pop = dm.build_stat_features(train_data, books)
    ch = dm.ChannelScores(train_data, books, item_sim, user_sim, b_pop)

    log("加载 DeepFM ...")
    bundle = torch.load(os.path.join(HERE, "deepfm_bundle.pt"), weights_only=False)
    model = dm.DeepFM([len(vocabs[k]) for k in ("user", "book", "category", "author", "publisher")])
    model.load_state_dict(bundle["state"])
    model.eval()

    log("端到端打分: 双塔 Top-100 并入候选池 -> DeepFM 精排 ...")
    e2e_recs = {}
    with torch.no_grad():
        for i, uid in enumerate(test_users):
            pool = sorted(set(pools.get(uid, [])) | set(tower_recs.get(uid, [])[:RECALL_K]))
            if not pool:
                e2e_recs[uid] = []
                continue
            sp = torch.tensor([dm._sparse_idx(uid, b, vocabs, books) for b in pool], dtype=torch.long)
            nums = np.array([dm._numeric(uid, b, num_feats, b_pop, ch) for b in pool], dtype=np.float32)
            nums = (nums - bundle["mean"]) / bundle["std"]
            scores = model(sp, torch.tensor(nums)).sigmoid().numpy()
            order = np.argsort(-scores)
            e2e_recs[uid] = [pool[i] for i in order[:10]]
            if (i + 1) % 500 == 0:
                ch.clear_cache()
                log(f"  {i + 1}/{len(test_users)}")

    e2e = evaluate_all(e2e_recs, test_truth)
    log("双塔+DeepFM 端到端: " + ", ".join(f"{k}={v:.4f}" for k, v in e2e.items()))
    log("===== 对比 Hybrid 基线 =====")
    for k in ("HR@10", "NDCG@10", "HR@20", "NDCG@20"):
        if hyb.get(k, 0) > 0:
            log(f"  {k}: 基线 {hyb[k]:.4f} -> 端到端 {e2e[k]:.4f} ({(e2e[k] - hyb[k]) / hyb[k] * 100:+.1f}%)")

    path = os.path.join(HERE, "two_tower_results.json")
    with open(path, encoding="utf-8") as f:
        results = json.load(f)
    results["双塔+DeepFM端到端"] = e2e
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log(f"完成，总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
