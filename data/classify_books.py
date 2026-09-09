"""
图书自动分类脚本
基于书名和作者关键词，为 2,046 本英文书打中文分类标签
"""

import mysql.connector

# ===== 分类规则：关键词 → 分类 =====
RULES = [
    ("科幻", [
        "science fiction", "sci-fi", "space", "alien", "mars",
        "dystopian", "cyberpunk", "robot", "time machine",
        "star trek", "star wars", "hitchhiker", "ender",
        "neuromancer", "foundation", "dune", "hyperion",
        "interstellar", "galactic", "cosmic", "orbit",
        "asimov", "clarke", "heinlein", "bradbury", "wells",
        "philip k dick", "orson scott card", "william gibson",
        "parallel world", "parallel universe", "timeline",
        "clone", "terraforming", "lunar", "martian",
        "fahrenheit", "brave new world", "1984",
        "douglas adams", "kurt vonnegut", "ursula k le guin",
        "robert heinlein", "jules verne",
    ]),
    ("奇幻", [
        "fantasy", "magic", "dragon", "wizard", "witch", "elf",
        "sword", "sorcerer", "enchant", "mythical", "fairy",
        "middle-earth", "narnia", "hobbit", "ring ",
        "tolkien", "robert jordan", "terry pratchett",
        "george r r martin", "game of thrones", "pratchett",
        "harry potter", "rowling", "c.s. lewis",
        "dark tower", "robin hobb", "goodkind",
        "magician", "unicorn", "quest",
    ]),
    ("推理悬疑", [
        "mystery", "detective", "murder", "crime", "suspense",
        "thriller", "killer", "investigation", "whodunit",
        "serial killer", "forensic", "sherlock holmes",
        "agatha christie", "james patterson", "john grisham",
        "michael connelly", "patricia cornwell", "sue grafton",
        "tess gerritsen", "harlan coben", "david baldacci",
        "lee child", "clive cussler", "scarpetta",
        "alex cross", "john sandford", "robert b parker",
        "janet evanovich", "sandra brown", "linda howard",
        "iris johansen", "mary higgins clark", "joy fielding",
        "conspiracy", "spy", "cia", "fbi", "agent",
        "cold case", "hostage", "abduction", "stolen",
        "alibi", "witness", "betrayal", "deception",
    ]),
    ("恐怖", [
        "horror", "ghost", "vampire", "haunt", "terror",
        "zombie", "stephen king", "dean koontz", "anne rice",
        "lovecraft", "edgar allan poe", "clive barker",
        "nightmare", "darkness", "dark ", "evil",
        "creepy", "supernatural", "pet sematary",
        "blood", "crypt", "monster",
    ]),
    ("爱情", [
        "romance", "love story", "lover", "heart",
        "nora roberts", "danielle steel", "nicholas sparks",
        "julia quinn", "jude deveraux", "johanna lindsey",
        "debbie macomber", "sherrilyn kenyon", "barbara taylor",
        "wedding", "bride", "sweet", "kiss", "desire",
        "passion", "destiny", "forever",
    ]),
    ("历史", [
        "history", "historical", "ancient", "medieval",
        "world war", "civil war", "revolution", "empire",
        "century", "victorian", "renaissance", "roman",
        "nazi", "holocaust", "pearl harbor", "vietnam",
        "hitler", "churchill", "lincoln", "napoleon",
        "colonial", "kingdom", "dynasty", "crusade",
    ]),
    ("文学经典", [
        "classic", "literature", "literary fiction",
        "hemingway", "faulkner", "steinbeck", "dickens",
        "austen", "tolstoy", "dostoevsky", "twain",
        "fitzgerald", "melville", "hawthorne", "wharton",
        "shakespeare", "virginia woolf", "james joyce",
        "pulitzer", "nobel", "toni morrison",
        "john updike", "philip roth", "cormac mccarthy",
        "margaret atwood", "gabriel garcia",
        "alice walker", "salman rushdie", "ian mcewan",
        "milan kundera", "umberto eco",
    ]),
    ("哲学", [
        "philosophy", "ethics", "consciousness",
        "plato", "aristotle", "nietzsche", "kant",
        "sartre", "descartes", "meaning of life",
        "tao", "zen ", "wisdom",
    ]),
    ("宗教灵性", [
        "religion", "bible", "god", "christian", "church",
        "spiritual", "faith", "prayer", "jesus", "heaven",
        "dalai lama", "buddhis", "catholic", "islam",
        "pope", "grace", "holy", "soul",
    ]),
    ("科普", [
        "science", "physics", "chemistry", "biology",
        "mathematics", "astronomy", "evolution", "genome",
        "stephen hawking", "carl sagan", "richard dawkins",
        "brief history", "universe", "quantum", "cosmos",
        "nature of", "natural history", "weather",
        "ocean", "volcano", "earthquake", "planet",
        "dinosaur", "animal", "bird",
    ]),
    ("传记回忆录", [
        "biography", "memoir", "autobiography", "life of",
        "letters of", "diary", "portrait", "my life",
        "personal history", "true story",
    ]),
    ("诗歌戏剧", [
        "poetry", "poems", "verse", "sonnet",
        "play ", "theatre", "bard",
    ]),
    ("少儿", [
        "children", "young readers", "bedtime",
        "picture book", "roald dahl", "dr seuss",
        "alice in wonderland", "winnie", "charlotte",
        "kid ", "kids ", "toddler", "preschool",
        "nursery", "fairy tale", "folktale",
    ]),
    ("计算机技术", [
        "computer", "programming", "software", "java ",
        "database", "web design", "web development",
        "algorithm", "internet", "digital", "code ",
        "html", "linux", "unix", "hacker",
        "networking", "data ", "server",
    ]),
    ("商业经济", [
        "business", "management", "leadership", "economics",
        "investing", "finance", "marketing", "entrepreneur",
        "organization", "strategy", "money", "wealth",
        "corporation", "wall street", "trade",
    ]),
    ("励志自助", [
        "self-help", "self help", "inspiration", "success",
        "personal growth", "motivation", "happiness",
        "fulfillment", "chicken soup", "zen",
        "guide to", "how to", "positive thinking",
        "meditation", "healing", "empower",
    ]),
    ("历史小说", [
        "historical fiction", "saga", "family saga",
        "lahaye", "jeffrey archer", "ken follett",
        "jean m auel", "colleen mccullough",
        "clan of", "century novel",
    ]),
    ("漫画绘本", [
        "comic", "graphic novel", "manga", "cartoon",
        "calvin and hobbes", "garfield", "peanuts",
        "illustrated", "sketch",
    ]),
]


def classify(title, author):
    """根据书名+作者返回分类"""
    text = (title + " " + author).lower()

    best_category = "小说"
    best_score = 0

    for category, keywords in RULES:
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def main():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",
        database="book_recommend",
        charset="utf8mb4",
    )
    cursor = conn.cursor()

    # 查询所有图书
    cursor.execute("SELECT id, title, author FROM book")
    books = cursor.fetchall()

    stats = {}
    updates = []

    for book_id, title, author in books:
        cat = classify(title or "", author or "")
        stats[cat] = stats.get(cat, 0) + 1
        updates.append((cat, book_id))

    # 批量更新
    for cat, book_id in updates:
        cursor.execute("UPDATE book SET category = %s WHERE id = %s", (cat, book_id))

    conn.commit()
    cursor.close()
    conn.close()

    # 打印统计
    print("===== 分类结果 =====")
    total = sum(stats.values())
    for cat, cnt in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * (cnt * 50 // total)
        print(f"  {cat:8s}  {cnt:>4}  ({cnt/total*100:5.1f}%)  {bar}")
    print(f"  {'合计':8s}  {total}")
    print(f"\n 未分类（其他）: {stats.get('其他', 0)}")


if __name__ == "__main__":
    main()
