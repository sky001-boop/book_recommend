"""
Phase 1a: 数据集切分
留一法（Leave-One-Out）：每个用户的最后一条评分进入测试集，其余进入训练集。
只保留评分 >= 3 条的用户进入测试集（保证留一法有意义）。
Book-Crossing 原始数据无时间戳，按数据序取"最后一条"。

输出:
  data/dl/train.csv   : user_id,book_id,score
  data/dl/test.csv    : user_id,book_id,score
  data/dl/split_stats.json
"""

import csv
import json
import os

HERE = os.environ.get("DL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
RATINGS = os.path.join(HERE, "ratings.csv")
MIN_USER_RATINGS = 3


def load_ratings(path):
    """返回按用户分组的 {user_id: [(book_id, score), ...]}，保持文件序"""
    user_ratings = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid = int(row["user_id"])
            bid = int(row["book_id"])
            score = float(row["score"])
            user_ratings.setdefault(uid, []).append((bid, score))
    return user_ratings


def split_leave_one_out(user_ratings, min_ratings=MIN_USER_RATINGS):
    """每个用户最后 1 条 -> 测试集，其余 -> 训练集"""
    train, test = [], []
    n_test_users = 0
    for uid, ratings in user_ratings.items():
        if len(ratings) < min_ratings:
            train.extend((uid, bid, score) for bid, score in ratings)
            continue
        test.append((uid, ratings[-1][0], ratings[-1][1]))
        train.extend((uid, bid, score) for bid, score in ratings[:-1])
        n_test_users += 1
    return train, test, n_test_users


def main():
    user_ratings = load_ratings(RATINGS)
    n_users = len(user_ratings)
    n_ratings = sum(len(v) for v in user_ratings.values())

    train, test, n_test_users = split_leave_one_out(user_ratings)

    # 统计
    train_users = {u for u, _, _ in train}
    train_books = {b for _, b, _ in train}
    test_books = {b for _, b, _ in test}
    book_ids = set()
    with open(os.path.join(HERE, "books.csv"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            book_ids.add(int(row["id"]))

    stats = {
        "total_users": n_users,
        "total_ratings": n_ratings,
        "test_users": n_test_users,
        "train_ratings": len(train),
        "test_ratings": len(test),
        "train_users": len(train_users),
        "train_books": len(train_books),
        "test_books_not_in_train": len(test_books - train_books),
        "total_books_in_catalog": len(book_ids),
        "matrix_density": round(n_ratings / (n_users * len(book_ids)) * 100, 4),
        "note": "Book-Crossing 无时间戳，留一法按数据序取每用户最后一条评分",
    }

    for name, rows in (("train.csv", train), ("test.csv", test)):
        with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["user_id", "book_id", "score"])
            w.writerows(rows)

    with open(os.path.join(HERE, "split_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
