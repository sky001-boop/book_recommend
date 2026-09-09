"""
Book-Crossing 数据集预处理脚本

目标：筛选出一个高质量的 用户-图书 评分矩阵
- 只保留显式评分 (1-10)
- 迭代过滤：用户评分>=10 AND 图书被评>=10
- 输出可直接导入 MySQL 的 SQL 文件
"""

import csv
import re
import html

INPUT_DIR = "."
OUTPUT_DIR = "."

# ===== 第一步：读取所有显式评分 =====
print("[1/5] 读取评分数据，筛选显式评分...")
ratings = []  # list of (user_id, isbn, score)
user_rating_count = {}
book_rating_count = {}

with open(f"{INPUT_DIR}/Ratings.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)  # skip header
    for row in reader:
        user_id = int(row[0])
        isbn = row[1].strip()
        score = float(row[2])
        if score > 0:  # 只保留显式评分
            ratings.append((user_id, isbn, score))
            user_rating_count[user_id] = user_rating_count.get(user_id, 0) + 1
            book_rating_count[isbn] = book_rating_count.get(isbn, 0) + 1

print(f"  显式评分: {len(ratings):,} 条")
print(f"  原始用户数: {len(user_rating_count):,}")
print(f"  原始图书数: {len(book_rating_count):,}")

# ===== 第二步：迭代过滤 =====
print("\n[2/5] 迭代过滤（用户>=3 且 图书>=3）...")

MIN_RATINGS = 3
round_num = 0

while True:
    round_num += 1
    # 过滤用户
    valid_users = {u for u, c in user_rating_count.items() if c >= MIN_RATINGS}
    # 过滤图书
    valid_books = {b for b, c in book_rating_count.items() if c >= MIN_RATINGS}

    # 重新统计
    new_user_count = {}
    new_book_count = {}
    new_ratings = []

    for user_id, isbn, score in ratings:
        if user_id in valid_users and isbn in valid_books:
            new_ratings.append((user_id, isbn, score))
            new_user_count[user_id] = new_user_count.get(user_id, 0) + 1
            new_book_count[isbn] = new_book_count.get(isbn, 0) + 1

    removed = len(ratings) - len(new_ratings)
    ratings = new_ratings
    user_rating_count = new_user_count
    book_rating_count = new_book_count

    print(f"  Round {round_num}: {len(ratings):,} 评分, "
          f"{len(user_rating_count):,} 用户, "
          f"{len(book_rating_count):,} 图书 "
          f"(-{removed:,})")

    if removed == 0:
        break

print(f"\n  最终: {len(ratings):,} 评分")
print(f"  用户数: {len(user_rating_count):,}")
print(f"  图书数: {len(book_rating_count):,}")
print(f"  矩阵密度: {len(ratings)/(len(user_rating_count)*len(book_rating_count))*100:.2f}%")

# ===== 第三步：读取并清洗图书信息 =====
print("\n[3/5] 读取并清洗图书数据...")

valid_isbns = set(book_rating_count.keys())
books = {}  # isbn -> book_info dict

# 匹配书名中括号年份的常见模式
year_in_title = re.compile(r'\s*\(\d{4}\)\s*$')

with open(f"{INPUT_DIR}/Books.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        isbn = row[0].strip()
        if isbn not in valid_isbns:
            continue

        title = row[1].strip()
        author = row[2].strip()
        year_str = row[3].strip()
        publisher = row[4].strip()
        cover = row[7].strip()  # Image-URL-L 大图

        # 跳过标题为空的
        if not title:
            continue

        # 跳过被 HTML encode 的奇怪标题
        if title.startswith('&'):
            continue

        # 清理标题中的特殊字符 + 截断过长标题
        title = html.unescape(title)
        if len(title) > 200:
            title = title[:200]
        title = title.replace("'", "''")  # SQL 单引号转义

        # 清理作者名
        author = html.unescape(author)
        author = author.replace("'", "''")
        if not author or author.lower() == 'unknown':
            author = '未知'

        # 清理出版社
        publisher = html.unescape(publisher)
        publisher = publisher.replace("'", "''")
        if not publisher:
            publisher = '未知'

        # 年份
        try:
            year = int(year_str) if year_str and year_str != '0' else None
        except ValueError:
            year = None

        # 封面（保留所有 URL，前端 image error 兜底）
        if not cover:
            cover = ''

        books[isbn] = {
            'title': title,
            'author': author,
            'category': '',  # BX 数据集没有分类
            'publisher': publisher,
            'isbn': isbn,
            'publish_year': year,
            'description': '',
            'cover': cover,
        }

print(f"  有效图书: {len(books):,}")

# ===== 第四步：生成 SQL =====
print("\n[4/5] 生成 SQL 文件...")

# 先删除 MySQL 中手动设置的某些安全模式
sql_header = """SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 清空旧数据
TRUNCATE TABLE rating;
TRUNCATE TABLE book;
DELETE FROM sys_user WHERE username LIKE 'bx_user_%';

SET FOREIGN_KEY_CHECKS = 1;

"""

# 图书 SQL
book_sql_lines = []
book_isbn_to_id = {}
book_id = 0
for isbn, info in books.items():
    book_id += 1
    book_isbn_to_id[isbn] = book_id
    title = info['title']
    author = info['author']
    publisher = info['publisher']
    isbn_val = info['isbn']
    year = info['publish_year']
    cover = info['cover']

    year_sql = str(year) if year else 'NULL'
    publisher_sql = f"'{publisher}'" if publisher else 'NULL'

    book_sql_lines.append(
        f"INSERT INTO book (id, title, author, publisher, isbn, publish_year, cover) "
        f"VALUES ({book_id}, '{title}', '{author}', {publisher_sql}, '{isbn_val}', {year_sql}, '{cover}');"
    )

# 用户 SQL（创建 bx_user_ 前缀的用户）
user_sql_lines = []
bx_user_to_internal = {}  # mapping from BX user_id to our internal id
internal_user_id = 100  # start from 100 to avoid conflict with existing users

# 对 BX 用户按评分数量降序排列
sorted_users = sorted(user_rating_count.items(), key=lambda x: x[1], reverse=True)

for bx_uid, count in sorted_users:
    internal_user_id += 1
    bx_user_to_internal[bx_uid] = internal_user_id
    username = f"bx_user_{bx_uid}"
    # BCrypt hash of "bx123456" — 所有BX用户的默认密码
    password = "$2a$10$zl2VSndMWNIezea6240cIOVlFxCEqpQ0kvCvCLuSBMqGkOawdtHF."
    user_sql_lines.append(
        f"INSERT IGNORE INTO sys_user (id, username, password, email, role) "
        f"VALUES ({internal_user_id}, '{username}', '{password}', 'bx{bx_uid}@dataset.com', 'USER');"
    )

# 评分 SQL
rating_sql_lines = []
for user_id, isbn, score in ratings:
    internal_uid = bx_user_to_internal.get(user_id)
    internal_bid = book_isbn_to_id.get(isbn)
    if internal_uid and internal_bid:
        rating_sql_lines.append(
            f'INSERT INTO rating (user_id, book_id, score) '
            f'VALUES ({internal_uid}, {internal_bid}, {score});'
        )

print(f"  SQL 行数: 图书={len(book_sql_lines):,}, 用户={len(user_sql_lines):,}, 评分={len(rating_sql_lines):,}")

# 写入 SQL 文件
with open(f"{OUTPUT_DIR}/import_data.sql", "w", encoding="utf-8") as f:
    f.write(sql_header)
    f.write("\n-- ===== 用户 =====\n")
    # 分批写入，每 500 行一个事务
    for i in range(0, len(user_sql_lines), 500):
        batch = user_sql_lines[i:i+500]
        f.write('\n'.join(batch) + '\n')

    f.write("\n-- ===== 图书 =====\n")
    for i in range(0, len(book_sql_lines), 500):
        batch = book_sql_lines[i:i+500]
        f.write('\n'.join(batch) + '\n')

    f.write("\n-- ===== 评分 =====\n")
    for i in range(0, len(rating_sql_lines), 1000):
        batch = rating_sql_lines[i:i+1000]
        f.write('\n'.join(batch) + '\n')

print(f"\n  SQL 文件已生成: {OUTPUT_DIR}/import_data.sql")

# ===== 第五步：统计摘要 =====
print("\n[5/5] 数据摘要")
print("-" * 50)
print(f"  用户数:    {len(bx_user_to_internal):,}")
print(f"  图书数:    {len(book_isbn_to_id):,}")
print(f"  评分数:    {len(rating_sql_lines):,}")
print(f"  矩阵密度:  {len(rating_sql_lines)/(len(bx_user_to_internal)*len(book_isbn_to_id))*100:.2f}%")

# 评分分布
from collections import Counter
score_dist = Counter()
# 重新统计评分分布
with open(f"{INPUT_DIR}/Ratings.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        user_id = int(row[0])
        isbn = row[1].strip()
        score = float(row[2])
        if score > 0 and user_id in bx_user_to_internal and isbn in book_isbn_to_id:
            score_dist[int(score)] += 1

print(f"\n  评分分布:")
total = sum(score_dist.values())
for s in sorted(score_dist.keys()):
    bar = '█' * int(score_dist[s] / total * 50)
    print(f"    {s:2d}: {score_dist[s]:>8,} ({score_dist[s]/total*100:5.1f}%) {bar}")

print("\nDone! Preprocessing complete.")
