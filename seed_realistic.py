"""
seed_realistic.py — Replaces demo products with realistic Nepali/TU marketplace items.
Run: python seed_realistic.py
"""
import sqlite3, os, sys, hashlib

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campuscart.db')

if not os.path.exists(DB_PATH):
    print(f"ERROR: {DB_PATH} not found. Run the app once first to create the DB.")
    sys.exit(1)

# Try to use werkzeug (Flask standard) for password hashing; fallback to sha256
try:
    from werkzeug.security import generate_password_hash
    def hash_pw(pw): return generate_password_hash(pw)
except ImportError:
    def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

# ── Realistic products: (name, category, price, icon, description, stock) ──
PRODUCTS = [
    # Books
    ("Data Structures & Algorithms — 3rd Sem CSIT", "Books", 450, "📘",
     "Good condition, minimal highlighting. Used for one semester. Handwritten notes in margins.", 1),
    ("Database Management Systems — Silberschatz (6th Ed.)", "Books", 380, "📗",
     "Cover slightly worn but pages clean. Essential for 4th semester DBMS.", 1),
    ("Operating System Concepts — Silberschatz (9th Ed.)", "Books", 520, "📕",
     "Standard OS textbook. No missing pages, some highlighting in chapters 5-7.", 1),
    ("Let Us C — Yashavant Kanetkar (13th Ed.)", "Books", 350, "📙",
     "Perfect for beginners. Slight cover wear. No tears or water damage.", 2),
    ("Python Crash Course — 3rd Edition", "Books", 600, "📗",
     "Like new. Only opened a few times. Great for self-study.", 1),
    ("Computer Networks — Tanenbaum (5th Ed.)", "Books", 550, "📘",
     "5th semester textbook. Highlighted important sections for exams.", 1),

    # Electronics
    ("Casio FX-991ES Plus Scientific Calculator", "Electronics", 1800, "🧮",
     "Barely used. Comes with original cover. Perfect for engineering exams.", 2),
    ("Dell Inspiron 15 — i5, 8GB RAM, 512GB SSD", "Electronics", 32000, "💻",
     "Used 2 years. Battery holds ~4 hours. Minor scratches on lid. Charger included.", 1),
    ("HP Original 65W Laptop Charger", "Electronics", 1500, "🔌",
     "Genuine HP charger. Works with most Pavilion and ProBook models.", 3),
    ("Logitech Wireless Mouse M170", "Electronics", 900, "🖱️",
     "Brand new, sealed. Bought extra by mistake. Still in original packaging.", 4),
    ("Sony Wired Earphones (MDR-EX15AP)", "Electronics", 1200, "🎧",
     "Original Sony. Excellent sound quality. Used only 2 months.", 2),
    ("4-Port USB 3.0 Hub — Compact", "Electronics", 450, "🔗",
     "Works perfectly. Great for laptops with limited USB ports.", 5),

    # Notes
    ("BSc CSIT 3rd Semester — Complete Handwritten Notes", "Notes", 150, "📝",
     "All subjects covered. Clear handwriting. PDF emailed after payment.", 99),
    ("BIT 5th Semester DBMS Notes (Typed)", "Notes", 100, "📄",
     "Comprehensive typed notes. Includes past exam questions with solutions.", 99),
    ("Operating Systems Exam Prep Question Bank", "Notes", 120, "📋",
     "Collected from past 5 years of TU exams. All with detailed solutions.", 99),
    ("Data Structures Lab Manual — Complete Programs", "Notes", 200, "📓",
     "All lab programs with sample outputs. C and C++ implementations.", 99),

    # Stationery
    ("Camlin Geometry Box — Complete Set", "Stationery", 350, "📐",
     "All instruments intact. Compass, protractor, set squares included.", 3),
    ("Classmate Long Notebooks (Pack of 5)", "Stationery", 250, "📔",
     "Unused. Single-line ruled, 172 pages each. Perfect for semester notes.", 10),
    ("Apsara Pencils + Eraser + Sharpener Combo", "Stationery", 90, "✏️",
     "New pack. 10 pencils included. Ideal for exam preparation.", 8),

    # Furniture
    ("Wooden Study Table with Drawer", "Furniture", 3500, "🪑",
     "Sturdy wooden table, 3x2 feet. Minor scratches. Perfect for hostel room.", 1),
    ("Study Table LED Lamp — Adjustable", "Furniture", 650, "💡",
     "3 brightness levels. USB powered. Great for late-night study sessions.", 4),
    ("Plastic Study Chair — Sturdy", "Furniture", 800, "🪑",
     "Comfortable plastic chair. No cracks. Pairs perfectly with a study table.", 2),

    # Clothing
    ("College Hoodie — Size M (Navy)", "Clothing", 1100, "👕",
     "Washed once, worn twice. Too small for me. Like-new condition.", 1),
    ("Casual T-Shirt — Size L (Grey)", "Clothing", 500, "👕",
     "New with tags. Bought wrong size. 100% cotton, very comfortable.", 2),
    ("Winter Jacket — Size M (Black)", "Clothing", 2200, "🧥",
     "Warm fleece-lined jacket. Used one winter. Excellent condition.", 1),

    # Others
    ("Mini Electric Kettle (1L)", "Others", 1200, "☕",
     "Used for 3 months. Great for hostel room. Auto-shutoff works perfectly.", 2),
    ("Nepal Engineering Council Exam Guide", "Others", 500, "📚",
     "Complete guide for the NEC license exam. Latest edition, barely used.", 2),
    ("BSc CSIT 1st Semester Reference Bundle", "Others", 900, "📦",
     "3 books bundled: Math I, Physics, Digital Logic. Great starter pack.", 1),
    ("USB Desk Fan — Small, Quiet", "Others", 400, "🌀",
     "Quiet operation. USB powered. Great for warm study rooms.", 5),
    ("Dell Wired Keyboard — Full Size", "Others", 850, "⌨️",
     "Standard Dell keyboard. All keys working. Minor wear on space bar.", 3),
]

# ── New sellers to create if none exist ──
NEW_SELLERS = [
    ("Sushant Chaudhary", "sushant.seller@campuscart.test", "test1234"),
    ("Priya Sharma",      "priya.seller@campuscart.test",   "test1234"),
    ("Rahul Thapa",       "rahul.seller@campuscart.test",   "test1234"),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Find or create sellers
    cur.execute("SELECT id, name FROM users WHERE role='seller' ORDER BY id")
    sellers = [dict(r) for r in cur.fetchall()]

    if not sellers:
        print("No sellers found. Creating 3 test sellers...")
        for name, email, pw in NEW_SELLERS:
            try:
                cur.execute(
                    "INSERT INTO users(name, email, password_hash, role) VALUES (?,?,?,?)",
                    (name, email, hash_pw(pw), "seller")
                )
            except sqlite3.IntegrityError:
                pass  # already exists
        conn.commit()
        cur.execute("SELECT id, name FROM users WHERE role='seller' ORDER BY id")
        sellers = [dict(r) for r in cur.fetchall()]

    if not sellers:
        print("ERROR: Could not find or create any sellers. Aborting.")
        sys.exit(1)

    print(f"Using {len(sellers)} seller(s):")
    for s in sellers:
        print(f"  id={s['id']}  {s['name']}")

    # 2. Wipe existing products
    cur.execute("SELECT COUNT(*) FROM products")
    old_count = cur.fetchone()[0]
    print(f"\nDeleting {old_count} existing products...")
    cur.execute("DELETE FROM products")
    conn.commit()

    # 3. Insert realistic products, distributed across sellers
    print(f"\nInserting {len(PRODUCTS)} realistic products...")
    for i, (name, cat, price, icon, desc, stock) in enumerate(PRODUCTS):
        seller = sellers[i % len(sellers)]
        cur.execute(
            """INSERT INTO products
               (name, category, price, icon, description, stock, seller_id)
               VALUES (?,?,?,?,?,?,?)""",
            (name, cat, price, icon, desc, stock, seller['id'])
        )
    conn.commit()

    # 4. Summary
    cur.execute("SELECT COUNT(*) FROM products")
    new_count = cur.fetchone()[0]
    cur.execute("""
        SELECT u.name AS seller, COUNT(p.id) AS n
        FROM users u LEFT JOIN products p ON p.seller_id = u.id
        WHERE u.role='seller'
        GROUP BY u.id ORDER BY n DESC
    """)
    print(f"\nDone. Now {new_count} products in the DB.\n")
    print("Products per seller:")
    for row in cur.fetchall():
        print(f"  {row['seller']:25s} → {row['n']} products")

    conn.close()
    print("\nRefresh your browser. Your marketplace is now realistic.")

if __name__ == "__main__":
    main()