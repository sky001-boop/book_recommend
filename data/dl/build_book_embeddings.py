"""
Phase 5a: 书籍文本向量化（RAG 语义找书）

将 22,808 本书的「分类 + 书名 + 作者」编码为 512 维语义向量，
供自然语言找书接口做余弦检索。模型: bge-small-zh-v1.5（CPU 可跑）。

输出:
  book_emb.npy         (22808, 512) float32
  book_emb_order.json  向量行号 -> book_id
"""

import csv
import json
import os
import time

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
BATCH = 512

# huggingface.co 直连不稳定时使用国内镜像
if os.environ.get("HF_ENDPOINT") is None:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


def main():
    t0 = time.time()
    books = []
    with open(os.path.join(HERE, "books.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            books.append((int(row["id"]), row["category"], row["title"], row["author"]))

    texts = [f"分类:{cat} 书名:{title} 作者:{auth}" for _, cat, title, auth in books]
    print(f"[{time.strftime('%H:%M:%S')}] 加载模型 {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)

    print(f"[{time.strftime('%H:%M:%S')}] 编码 {len(texts):,} 本书 ...")
    embs = model.encode(texts, batch_size=BATCH, normalize_embeddings=True,
                        show_progress_bar=True)

    np.save(os.path.join(HERE, "book_emb.npy"), embs.astype(np.float32))
    order = [bid for bid, *_ in books]
    with open(os.path.join(HERE, "book_emb_order.json"), "w", encoding="utf-8") as f:
        json.dump(order, f)
    print(f"完成: book_emb.npy {embs.shape}, 耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
