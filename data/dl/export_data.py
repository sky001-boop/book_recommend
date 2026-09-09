"""
Phase 0: 数据导出
从 preprocess.py 生成的 SQL 文件解析出训练/评测所需的 CSV
（不依赖 MySQL，直接解析 INSERT 语句，SQL 格式由 preprocess.py 保证）

输出:
  data/dl/books.csv   : id,title,author,publisher,isbn,publish_year,category
  data/dl/ratings.csv : user_id,book_id,score
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..")
OUT_DIR = HERE

IMPORT_SQL = os.path.join(DATA_DIR, "import_data.sql")
CAT_SQL = os.path.join(DATA_DIR, "cat_fix2.sql")


def parse_sql_values(line: str):
    """解析形如 "(1, 'Clara Callan', 'A', 'B', '0002', 2001, 'http://...');" 的值列表
    处理 SQL 单引号转义（''）和逗号在字符串内的情况。"""
    marker = line.find("VALUES ")
    if marker == -1:
        return None
    start = line.find("(", marker)
    end = line.rfind(")")
    if start == -1 or end == -1:
        return None
    content = line[start + 1 : end]
    values = []
    buf = []
    in_str = False
    i = 0
    while i < len(content):
        ch = content[i]
        if in_str:
            if ch == "'":
                if i + 1 < len(content) and content[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
            else:
                buf.append(ch)
        else:
            if ch == "'":
                in_str = True
            elif ch == ",":
                values.append("".join(buf).strip())
                buf = []
                i += 1
                continue
            else:
                buf.append(ch)
        i += 1
    values.append("".join(buf).strip())
    return values


def export_books():
    print("[1/2] 解析图书数据...")
    rows = []
    with open(IMPORT_SQL, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("INSERT INTO book "):
                continue
            vals = parse_sql_values(line)
            if not vals or len(vals) < 7:
                continue
            # (id, title, author, publisher, isbn, publish_year, cover)
            book_id = int(vals[0])
            title = vals[1]
            author = vals[2]
            publisher = vals[3]
            isbn = vals[4]
            year = vals[5] if vals[5] and vals[5].upper() != "NULL" else ""
            rows.append([book_id, title, author, publisher, isbn, year])
    print(f"  图书: {len(rows):,}")

    print("    合并分类标签 (cat_fix2.sql)...")
    category = {}
    cat_re = re.compile(r"category='([^']*)'\s+WHERE\s+id=(\d+)")
    with open(CAT_SQL, "r", encoding="utf-8") as f:
        for line in f:
            m = cat_re.search(line)
            if m:
                category[int(m.group(2))] = m.group(1)
    n_cat = sum(1 for r in rows if r[0] in category)
    print(f"  有分类标签: {n_cat:,} / {len(rows):,}")

    out = os.path.join(OUT_DIR, "books.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "author", "publisher", "isbn", "publish_year", "category"])
        for r in rows:
            w.writerow(r + [category.get(r[0], "")])
    print(f"  输出: {out}")


def export_ratings():
    print("[2/2] 解析评分数据...")
    n = 0
    out = os.path.join(OUT_DIR, "ratings.csv")
    with open(IMPORT_SQL, "r", encoding="utf-8") as fin, open(out, "w", newline="", encoding="utf-8") as fout:
        w = csv.writer(fout)
        w.writerow(["user_id", "book_id", "score"])
        for line in fin:
            if not line.startswith("INSERT INTO rating "):
                continue
            m = re.match(r"INSERT INTO rating \(user_id, book_id, score\) VALUES \((\d+), (\d+), ([\d.]+)\);", line)
            if not m:
                print("  跳过无法解析的行:", line.strip()[:80])
                continue
            w.writerow([int(m.group(1)), int(m.group(2)), float(m.group(3))])
            n += 1
    print(f"  评分: {n:,}")
    print(f"  输出: {out}")


if __name__ == "__main__":
    export_books()
    export_ratings()
    print("Done.")
