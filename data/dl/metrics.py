"""
Phase 1b: 离线评测指标
HR@K / Recall@K / NDCG@K

输入:
  recs : {user_id: [book_id, ...]}  推荐列表（有序，前 K 名参与计算）
  truth: {user_id: [book_id, ...]}  真实评分书（测试集）
"""

import math


def _hits_at_k(rec_list, truth_items, k):
    rec = rec_list[:k]
    return sum(1 for b in truth_items if b in rec)


def hr_at_k(recs, truth, k=10):
    """命中率：真实评分书出现在推荐前 K 名的用户占比"""
    hit = sum(1 for uid, truth_items in truth.items()
              if _hits_at_k(recs.get(uid, []), truth_items, k) > 0)
    return hit / len(truth) if truth else 0.0


def recall_at_k(recs, truth, k=10):
    """召回率：命中的真实评分书 / 该用户真实评分书总数"""
    total = 0.0
    for uid, truth_items in truth.items():
        total += _hits_at_k(recs.get(uid, []), truth_items, k) / len(truth_items)
    return total / len(truth) if truth else 0.0


def ndcg_at_k(recs, truth, k=10):
    """NDCG@K：带位置权重的命中质量，越靠前得分越高"""
    total = 0.0
    for uid, truth_items in truth.items():
        rec = recs.get(uid, [])[:k]
        dcg = 0.0
        for pos, book in enumerate(rec, start=1):
            if book in truth_items:
                dcg += 1.0 / math.log2(pos + 1)
        # 理想排序：所有真实书排在最前
        ideal = sum(1.0 / math.log2(pos + 1) for pos in range(1, min(k, len(truth_items)) + 1))
        total += dcg / ideal if ideal > 0 else 0.0
    return total / len(truth) if truth else 0.0


def evaluate_all(recs, truth, ks=(10, 20)):
    """返回各指标表，用于报告"""
    result = {}
    for k in ks:
        result[f"HR@{k}"] = hr_at_k(recs, truth, k)
        result[f"Recall@{k}"] = recall_at_k(recs, truth, k)
        result[f"NDCG@{k}"] = ndcg_at_k(recs, truth, k)
    return result
