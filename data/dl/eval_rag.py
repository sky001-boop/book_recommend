"""
Phase 5b: RAG 语义检索离线评测

构造 50 条查询（30 条分类语义查询 + 20 条书名查询），
计算 Top-5 命中率（分类查询: Top-5 含该书分类; 书名查询: Top-5 含该书本身）。

依赖: book_emb.npy / book_emb_order.json（build_book_embeddings.py 生成）
"""

import csv
import json
import os
import sys
import time

import numpy as np

HERE = os.environ.get("DL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("缺少 sentence-transformers，请先安装")
    sys.exit(1)

if os.environ.get("HF_ENDPOINT") is None:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 30 条分类查询: (查询文本, 期望分类) —— 期望分类与数据集真实分类词表一致
CAT_QUERIES = [
    ("推荐几本科幻小说", "科幻"),
    ("有哪些推理悬疑小说推荐", "推理悬疑"),
    ("侦探破案类的书", "推理悬疑"),
    ("找一些奇幻冒险的故事", "奇幻"),
    ("魔法世界题材的小说", "奇幻"),
    ("经典文学作品推荐", "文学经典"),
    ("适合文学爱好者的名著", "文学经典"),
    ("历史类的书籍", "历史"),
    ("讲历史故事的书", "历史"),
    ("浪漫爱情小说", "爱情"),
    ("言情类小说", "爱情"),
    ("恐怖惊悚的书", "恐怖"),
    ("吓人的恐怖小说", "恐怖"),
    ("科普读物推荐", "科普"),
    ("科学普及类的书", "科普"),
    ("儿童读物", "少儿"),
    ("给孩子看的书", "少儿"),
    ("诗歌类书籍", "诗歌戏剧"),
    ("诗集推荐", "诗歌戏剧"),
    ("宗教和灵性方面的书", "宗教灵性"),
    ("哲学思想类书籍", "哲学"),
    ("讲哲学的入门书", "哲学"),
    ("战争历史题材的小说", "历史小说"),
    ("历史演义类小说", "历史小说"),
    ("商业管理类书籍", "商业经济"),
    ("职场和管理书籍", "商业经济"),
    ("计算机编程类书籍", "计算机技术"),
    ("自我成长心灵鸡汤", "励志自助"),
    ("传记类图书", "传记回忆录"),
    ("漫画绘本推荐", "漫画绘本"),
]

# 20 条书名查询: (查询文本, 期望命中的书名关键词)
TITLE_QUERIES = [
    ("找《The Da Vinci Code》这本书", "da vinci code"),
    ("《1984》奥威尔", "1984"),
    ("《Animal Farm》动物农场", "animal farm"),
    ("《The Hobbit》霍比特人", "hobbit"),
    ("《Pride and Prejudice》傲慢与偏见", "pride and prejudice"),
    ("《The Catcher in the Rye》", "catcher in the rye"),
    ("《To Kill a Mockingbird》", "to kill a mockingbird"),
    ("《The Great Gatsby》了不起的盖茨比", "great gatsby"),
    ("《Moby Dick》白鲸", "moby"),
    ("The Alchemist", "alchemist"),
    ("《One Hundred Years of Solitude》百年孤独", "solitude"),
    ("《The Shining》闪灵", "shining"),
    ("Stephen King horror novel", "stephen king"),
    ("《The Stand》末日逼近", "stand"),
    ("《A Brief History of Time》时间简史", "brief history of time"),
    ("《The Selfish Gene》自私的基因", "selfish gene"),
    ("《Silent Spring》寂静的春天", "silent spring"),
    ("《The Art of War》孙子兵法", "art of war"),
    ("《The Little Prince》小王子", "little prince"),
    ("《Dune》沙丘", "dune"),
]


def main():
    t0 = time.time()
    print("加载模型与书籍向量...")
    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    embs = np.load(os.path.join(HERE, "book_emb.npy"))
    with open(os.path.join(HERE, "book_emb_order.json"), encoding="utf-8") as f:
        order = json.load(f)

    books = {}
    with open(os.path.join(HERE, "books.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            books[int(row["id"])] = (row["title"], row["category"])

    def search_top5(query):
        q = model.encode([query], normalize_embeddings=True)[0].astype(np.float32)
        sims = embs @ q
        top = np.argsort(-sims)[:5]
        return [order[i] for i in top]

    n_cat_hit = 0
    for query, expect_cat in CAT_QUERIES:
        top_ids = search_top5(query)
        hit = any(books.get(bid, ("", ""))[1] == expect_cat for bid in top_ids)
        n_cat_hit += hit
        if not hit:
            got = [books.get(bid, ("", ""))[1] for bid in top_ids[:3]]
            print(f"  [未命中] {query!r} 期望[{expect_cat}] 实际{got}")

    n_title_hit = 0
    for query, keyword in TITLE_QUERIES:
        top_ids = search_top5(query)
        hit = any(keyword in books.get(bid, ("", ""))[0].lower() for bid in top_ids)
        n_title_hit += hit
        if not hit:
            got = [books.get(bid, ("", ""))[0][:40] for bid in top_ids[:3]]
            print(f"  [未命中] {query!r} 实际{got}")

    cat_hit_rate = n_cat_hit / len(CAT_QUERIES)
    title_hit_rate = n_title_hit / len(TITLE_QUERIES)
    overall = (n_cat_hit + n_title_hit) / (len(CAT_QUERIES) + len(TITLE_QUERIES))
    print(f"\n分类查询 Top-5 命中率: {n_cat_hit}/{len(CAT_QUERIES)} = {cat_hit_rate:.2%}")
    print(f"书名查询 Top-5 命中率: {n_title_hit}/{len(TITLE_QUERIES)} = {title_hit_rate:.2%}")
    print(f"综合 Top-5 命中率: {overall:.2%}")

    with open(os.path.join(HERE, "rag_eval_results.json"), "w", encoding="utf-8") as f:
        json.dump({
            "cat_queries": len(CAT_QUERIES), "cat_hits": n_cat_hit, "cat_hit_rate": cat_hit_rate,
            "title_queries": len(TITLE_QUERIES), "title_hits": n_title_hit, "title_hit_rate": title_hit_rate,
            "overall_top5_hit_rate": overall,
        }, f, ensure_ascii=False, indent=2)
    print(f"耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
