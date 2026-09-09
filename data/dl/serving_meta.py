"""
Phase 4a: 导出推理资产（serving_meta.json）

模型服务（FastAPI）只加载 JSON/ONNX/Faiss，不依赖训练代码：
  - vocabs           : user/book/category/author/publisher -> 索引
  - book_sparse      : book_id -> [book_idx, cat_idx, auth_idx, pub_idx]
  - user_feats       : user_id -> [评分次数, 评分均值]
  - book_feats       : book_id -> [被评次数, 被评均值, log流行度]
  - item_order       : Faiss 索引位置 -> book_id（与训练时 sorted(books) 顺序一致）
  - deepfm_mean/std  : DeepFM 数值特征 z-score
  - tower_u_mean/std : 双塔用户特征 z-score
"""

import json
import os
import sys

import torch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.environ.get("DL_DATA_DIR") or SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
from baseline import load_books, load_train  # noqa: E402
from deepfm import build_stat_features, build_vocabs  # noqa: E402


def main():
    train = load_train()
    books = load_books()
    vocabs = build_vocabs(train, books)
    num_feats, _ = build_stat_features(train, books)

    book_sparse = {}
    for bid, (cat, auth, pub) in books.items():
        book_sparse[str(bid)] = [
            vocabs["book"][bid],
            vocabs["category"].get(cat, 0),
            vocabs["author"].get(auth, 0),
            vocabs["publisher"].get(pub, 0),
        ]
    user_feats = {str(k[1]): v for k, v in num_feats.items() if k[0] == "user"}
    book_feats = {str(k[1]): v for k, v in num_feats.items() if k[0] == "book"}

    bundle = torch.load(os.path.join(HERE, "deepfm_bundle.pt"), weights_only=False)
    tower_meta = torch.load(os.path.join(HERE, "user_tower_meta.pt"), weights_only=False)

    meta = {
        "vocabs": {"user": len(vocabs["user"]), "book": len(vocabs["book"]),
                   "category": len(vocabs["category"]), "author": len(vocabs["author"]),
                   "publisher": len(vocabs["publisher"])},
        "user_index": {str(u): i for u, i in vocabs["user"].items()},
        "book_sparse": book_sparse,
        "user_feats": user_feats,
        "book_feats": book_feats,
        "item_order": sorted(books.keys()),
        "deepfm_mean": [float(x) for x in bundle["mean"]],
        "deepfm_std": [float(x) for x in bundle["std"]],
        "tower_u_mean": [float(x) for x in tower_meta["u_mean"]],
        "tower_u_std": [float(x) for x in tower_meta["u_std"]],
    }
    out = os.path.join(HERE, "serving_meta.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"serving_meta.json 已导出: {out}")
    print(f"  user_index={len(meta['user_index'])}, book_sparse={len(meta['book_sparse'])}, "
          f"item_order={len(meta['item_order'])}")


if __name__ == "__main__":
    main()
