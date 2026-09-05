import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = "data/mock_db/warehouse.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_review_queue_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            item_name TEXT,
            vendor_id TEXT,
            order_quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            urgency TEXT,
            reasoning TEXT,
            status TEXT DEFAULT 'pending_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS executed_purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            vendor_id TEXT,
            order_quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            reviewer_notes TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def scan_reorder_triggers() -> List[Dict[str, Any]]:
    """
    Fetches items where current_stock <= reorder_point.
    Excludes any SKU that already has an unresolved item in 'pending_review'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT sku, item_name, category, current_stock, reorder_point, daily_sales_rate, unit_holding_cost
        FROM inventory
        WHERE current_stock <= reorder_point
          AND sku NOT IN (
              SELECT sku FROM pending_review_queue WHERE status = 'pending_review'
          )
        ORDER BY (current_stock / daily_sales_rate) ASC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    triggered_items = []
    for r in rows:
        daily_sales = r["daily_sales_rate"]
        runway = round(r["current_stock"] / daily_sales, 2) if daily_sales > 0 else 999.0
        urgency = "Critical" if runway < 3.0 else ("Watch" if runway <= 14.0 else "Healthy")
        triggered_items.append({
            "sku": r["sku"],
            "item_name": r["item_name"],
            "category": r["category"],
            "current_stock": r["current_stock"],
            "reorder_point": r["reorder_point"],
            "daily_sales_rate": r["daily_sales_rate"],
            "unit_holding_cost": r["unit_holding_cost"],
            "runway_days": runway,
            "urgency": urgency
        })
    return triggered_items

def get_vendor_catalog_for_sku(sku: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT v.vendor_id, v.name, v.payment_terms, v.reliability_rating,
               c.base_unit_cost, c.min_order_qty, c.standard_lead_days
        FROM vendor_sku_catalog c
        JOIN vendors v ON c.vendor_id = v.vendor_id
        WHERE c.sku = ?
        ORDER BY c.base_unit_cost ASC;
    """
    cursor.execute(query, (sku,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_all_inventory() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sku, item_name, category, current_stock, reorder_point, daily_sales_rate, unit_holding_cost
        FROM inventory;
    """)
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        dsr = d["daily_sales_rate"]
        runway = round(d["current_stock"] / dsr, 1) if dsr > 0 else 999.0
        d["runway_days"] = runway
        d["urgency"] = "Critical" if runway < 3.0 else ("Watch" if runway <= 14.0 else "Healthy")
        items.append(d)
    return items

def bulk_replace_inventory(items: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory;")
    for it in items:
        cursor.execute("""
            INSERT INTO inventory (sku, item_name, category, current_stock, reorder_point, daily_sales_rate, unit_holding_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            it["sku"],
            it["item_name"],
            it.get("category", "Electronics"),
            int(it["current_stock"]),
            int(it["reorder_point"]),
            float(it["daily_sales_rate"]),
            float(it.get("unit_holding_cost", 1.5))
        ))
    conn.commit()
    conn.close()

def save_to_review_queue(draft: dict, urgency: str, reasoning: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pending_review_queue (sku, item_name, vendor_id, order_quantity, unit_price, total_amount, urgency, reasoning, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review');
    """, (
        draft.get("sku"),
        draft.get("item_name", ""),
        draft.get("vendor_id"),
        draft.get("quantity", 0),
        draft.get("unit_price", 0.0),
        draft.get("total_amount", 0.0),
        urgency,
        reasoning
    ))
    conn.commit()
    conn.close()

def get_all_pending_reviews() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sku, item_name, vendor_id, order_quantity, unit_price, total_amount, urgency, reasoning, status, created_at
        FROM pending_review_queue
        WHERE status = 'pending_review'
        ORDER BY created_at DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_review_item(sku: str, approved: bool, override_qty: Optional[int] = None, notes: str = ""):
    """Updates pending status, creates executed order log, and increments stock on approval."""
    conn = get_db_connection()
    cursor = conn.cursor()
    new_status = "approved" if approved else "rejected"

    cursor.execute("""
        UPDATE pending_review_queue
        SET status = ?
        WHERE id = (
            SELECT id FROM pending_review_queue 
            WHERE sku = ? AND status = 'pending_review' 
            ORDER BY created_at DESC LIMIT 1
        );
    """, (new_status, sku))

    if approved:
        cursor.execute("""
            SELECT vendor_id, order_quantity, unit_price, total_amount
            FROM pending_review_queue
            WHERE sku = ?
            ORDER BY created_at DESC LIMIT 1;
        """, (sku,))
        row = cursor.fetchone()
        if row:
            qty = override_qty if (override_qty and override_qty > 0) else row["order_quantity"]
            unit_p = row["unit_price"]
            total = round(qty * unit_p, 2)
            
            # Record executed PO
            cursor.execute("""
                INSERT INTO executed_purchase_orders (sku, vendor_id, order_quantity, unit_price, total_amount, reviewer_notes)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (sku, row["vendor_id"], qty, unit_p, total, notes))

            # Replenish warehouse inventory
            cursor.execute("""
                UPDATE inventory
                SET current_stock = current_stock + ?
                WHERE sku = ?;
            """, (qty, sku))
    else:
        # On rejection, bump stock above reorder point to simulate operational cancellation
        cursor.execute("""
            UPDATE inventory
            SET current_stock = reorder_point + 1
            WHERE sku = ?;
        """, (sku,))

    conn.commit()
    conn.close()