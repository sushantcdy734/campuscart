import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'campuscart.db')
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'products')

CATALOG = {
    "dsa-book.jpg":         ("Data Structures & Algorithms - 3rd Sem CSIT", "Books", 450, "Good condition, minimal highlighting. Used one semester.", 1),
    "dbms-book.jpg":        ("Database Management Systems - Silberschatz (6th Ed.)", "Books", 380, "Cover slightly worn, pages clean. Essential for 4th semester.", 1),
    "os-book.jpg":          ("Operating System Concepts - Silberschatz (9th Ed.)", "Books", 520, "Standard OS textbook. No missing pages, some highlighting.", 1),
    "letusc-book.jpg":      ("Let Us C - Yashavant Kanetkar (13th Ed.)", "Books", 350, "Perfect for beginners. Slight cover wear.", 2),
    "python-book.jpg":      ("Python Crash Course - 3rd Edition", "Books", 600, "Like new. Opened only a few times.", 1),
    "networks-book.jpg":    ("Computer Networks - Tanenbaum (5th Ed.)", "Books", 550, "5th semester textbook. Highlighted important sections.", 1),
    "casio-calc.jpg":       ("Casio FX-991ES Plus Scientific Calculator", "Electronics", 1800, "Barely used. Comes with original cover.", 2),
    "dell-laptop.jpg":      ("Dell Inspiron 15 - i5, 8GB RAM, 512GB SSD", "Electronics", 32000, "Used 2 years. Battery holds 4 hours. Charger included.", 1),
    "hp-charger.jpg":       ("HP Original 65W Laptop Charger", "Electronics", 1500, "Genuine HP charger. Works with Pavilion and ProBook.", 3),
    "logitech-mouse.jpg":   ("Logitech Wireless Mouse M170", "Electronics", 900, "Brand new, sealed. Bought extra by mistake.", 4),
    "sony-earphones.jpg":   ("Sony Wired Earphones (MDR-EX15AP)", "Electronics", 1200, "Original Sony. Excellent sound. Used only 2 months.", 2),
    "usb-hub.jpg":          ("4-Port USB 3.0 Hub - Compact", "Electronics", 450, "Works perfectly. Great for laptops with limited USB ports.", 5),
    "handwritten-notes.jpg":("BSc CSIT 3rd Semester - Complete Handwritten Notes", "Notes", 150, "All subjects covered. Clear handwriting.", 99),
    "dbms-notes.jpg":       ("BIT 5th Semester DBMS Notes (Typed)", "Notes", 100, "Comprehensive typed notes. Includes past exam questions.", 99),
    "question-bank.jpg":    ("Operating Systems Exam Prep Question Bank", "Notes", 120, "Collected from past 5 years of TU exams with solutions.", 99),
    "lab-manual.jpg":       ("Data Structures Lab Manual - Complete Programs", "Notes", 200, "All lab programs with sample outputs.", 99),
    "geometry-box.jpg":     ("Camlin Geometry Box - Complete Set", "Stationery", 350, "All instruments intact. Compass, protractor, set squares.", 3),
    "notebooks.jpg":        ("Classmate Long Notebooks (Pack of 5)", "Stationery", 250, "Unused. Single-line ruled, 172 pages each.", 10),
    "pencils.jpg":          ("Apsara Pencils + Eraser + Sharpener Combo", "Stationery", 90, "New pack. 10 pencils included.", 8),
    "study-table.jpg":      ("Wooden Study Table with Drawer", "Furniture", 3500, "Sturdy wooden table, 3x2 feet. Minor scratches.", 1),
    "table-lamp.jpg":       ("Study Table LED Lamp - Adjustable", "Furniture", 650, "3 brightness levels. USB powered.", 4),
    "study-chair.jpg":      ("Plastic Study Chair - Sturdy", "Furniture", 800, "Comfortable plastic chair. No cracks.", 2),
    "hoodie.jpg":           ("College Hoodie - Size M (Navy)", "Clothing", 1100, "Washed once, worn twice. Too small for me.", 1),
    "tshirt.jpg":           ("Casual T-Shirt - Size L (Grey)", "Clothing", 500, "New with tags. Bought wrong size. 100% cotton.", 2),
    "jacket.jpg":           ("Winter Jacket - Size M (Black)", "Clothing", 2200, "Warm fleece-lined. Used one winter.", 1),
    "kettle.jpg":           ("Mini Electric Kettle (1L)", "Others", 1200, "Used 3 months. Great for hostel room. Auto-shutoff works.", 2),
    "nec-guide.jpg":        ("Nepal Engineering Council Exam Guide", "Others", 500, "Complete guide for NEC license exam. Latest edition.", 2),
    "csit-bundle.jpg":      ("BSc CSIT 1st Semester Reference Bundle", "Others", 900, "3 books bundled: Math I, Physics, Digital Logic.", 1),
    "desk-fan.jpg":         ("USB Desk Fan - Small, Quiet", "Others", 400, "Quiet operation. USB powered. Great for warm study rooms.", 5),
    "dell-keyboard.jpg":    ("Dell Wired Keyboard - Full Size", "Others", 850, "Standard Dell keyboard. All keys working. Minor wear on spacebar.", 3),
}

def main():
    if not os.path.isdir(IMG_DIR):
        print(f"ERROR: {IMG_DIR} not found.")
        sys.exit(1)

    files = set(os.listdir(IMG_DIR))
    print(f"Found {len(files)} files in static/products/")

    to_add = []
    for filename in sorted(files):
        if filename in CATALOG:
            name, cat, price, desc, stock = CATALOG[filename]
            to_add.append((name, cat, price, desc, stock, filename))

    if not to_add:
        print("No matching products found. Check your filenames.")
        sys.exit(1)

    print(f"\nProducts to add: {len(to_add)}\n")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM users WHERE role='seller' ORDER BY id LIMIT 1")
    seller = cur.fetchone()
    if not seller:
        print("ERROR: No seller found in users table.")
        sys.exit(1)
    seller_id, seller_name = seller
    print(f"Assigning products to seller: {seller_name} (id={seller_id})\n")

    cur.execute("SELECT COUNT(*) FROM products")
    old = cur.fetchone()[0]
    print(f"Deleting {old} existing products...")
    cur.execute("DELETE FROM products")
    conn.commit()

    for name, cat, price, desc, stock, filename in to_add:
        image_url = f"/static/products/{filename}"
        cur.execute(
            "INSERT INTO products (name, category, price, icon, description, stock, seller_id, image_url) VALUES (?,?,?,?,?,?,?,?)",
            (name, cat, price, "📦", desc, stock, seller_id, image_url)
        )
        print(f"  OK  {name[:50]}")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM products")
    total = cur.fetchone()[0]
    conn.close()

    print(f"\n{'='*60}")
    print(f"Done. {total} products in DB, all with images.")
    print("Refresh browser with Ctrl+Shift+R.")

if __name__ == "__main__":
    main()