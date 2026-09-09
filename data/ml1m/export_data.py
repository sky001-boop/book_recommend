"""
MovieLens-1M 数据适配
将原始 CSV 转换为推荐管线统一格式（与 Book-Crossing 同 schema）:

  books.csv   : id,title,author,publisher,isbn,publish_year,category
                电影 -> category 取首个 genre，年份从标题 "(1995)" 提取
  ratings.csv : user_id,book_id,score
                评分 1-5 映射到 1-10 刻度（x2），正样本阈值 >=7 与原 5 分制的 >=3.5 等价

数据规模: 1,000,209 评分 / 6,040 用户 / 3,706 电影，密度 4.47%
"""

import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


def export_movies():
    rows = []
    # MovieLens 原始文件为 ISO-8859-1 编码（标题含 ü 等字符）
    with open(os.path.join(HERE, "movies.csv"), encoding="latin-1") as f:
        for row in csv.DictReader(f):
            movie_id = int(row["movie_id"])
            title = row["movie"]
            m = YEAR_RE.search(title)
            year = int(m.group(1)) if m else 0
            title_clean = YEAR_RE.sub("", title).strip()
            genres = row["genres"].split("|")
            category = genres[0] if genres and genres[0] else ""
            rows.append([movie_id, title_clean, "", "", "", year, category])
    with open(os.path.join(HERE, "books.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "author", "publisher", "isbn", "publish_year", "category"])
        w.writerows(rows)
    print(f"books.csv: {len(rows):,} 部电影")


def export_ratings():
    raw = os.path.join(HERE, "ratings.csv")
    backup = os.path.join(HERE, "ratings_raw.csv")
    if not os.path.exists(backup):  # 保留原始文件
        os.replace(raw, backup)
    n = 0
    with open(backup, encoding="utf-8") as fin, \
            open(raw, "w", newline="", encoding="utf-8") as fout:
        w = csv.writer(fout)
        w.writerow(["user_id", "book_id", "score"])
        for row in csv.DictReader(fin):
            w.writerow([int(row["user_id"]), int(row["movie_id"]), float(row["rating"]) * 2])
            n += 1
    print(f"ratings.csv（管线格式）: {n:,} 条评分，原始数据保留为 ratings_raw.csv")


if __name__ == "__main__":
    export_movies()
    export_ratings()
    print("适配完成，可直接运行管线: DL_DATA_DIR=<本目录> python <脚本>")
