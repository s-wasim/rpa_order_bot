import json
import os
import random
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("MOCKSHOP_DB", "/data/mockshop.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL,
            stock INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            items_total REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER,
            product_title TEXT NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
    """)
    cur = conn.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        catalog_path = os.path.join(os.path.dirname(__file__), "catalog.json")
        with open(catalog_path) as f:
            products = json.load(f)
        for p in products:
            conn.execute(
                "INSERT INTO products (id, title, description, price, stock) VALUES (?, ?, ?, ?, ?)",
                (p["id"], p["title"], p["description"], p["price"], 1 if p["stock"] else 0),
            )
        conn.commit()
    conn.close()


def _row_to_dict(row):
    return dict(zip(row.keys(), row)) if row else None

def search_products(q):
    conn = _get_conn()
    like = f"%{q}%"
    rows = conn.execute(
        "SELECT * FROM products WHERE title LIKE ? OR description LIKE ? ORDER BY id",
        (like, like),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_product(product_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def create_order(items):
    conn = _get_conn()
    order_no = f"DM-{random.randint(10000, 99999)}"
    items_total = sum(item["qty"] * item["unit_price"] for item in items)
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO orders (order_no, items_total, created_at) VALUES (?, ?, ?)",
        (order_no, items_total, now),
    )
    order_id = cur.lastrowid
    for item in items:
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, product_title, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
            (order_id, item.get("product_id"), item["title"], item["qty"], item["unit_price"]),
        )
    conn.commit()
    conn.close()
    return order_no


def get_order(order_no):
    conn = _get_conn()
    order = conn.execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()
    if not order:
        conn.close()
        return None
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order["id"],)
    ).fetchall()
    conn.close()
    return {**_row_to_dict(order), "order_items": [_row_to_dict(i) for i in items]}


def get_all_orders():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    orders = []
    for row in rows:
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (row["id"],)
        ).fetchall()
        orders.append({**_row_to_dict(row), "order_items": [_row_to_dict(i) for i in items]})
    conn.close()
    return orders
