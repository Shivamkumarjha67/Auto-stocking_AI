import sqlite3
import time
import json
from typing import List, Dict, Any, Optional

DB_PATH = "data/mock_db/warehouse.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _add_column_if_missing(cursor, table: str, col_name: str, col_type: str):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cursor.fetchall()]
    if col_name not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

def init_review_queue_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            item_name TEXT,
            category TEXT,
            vendor_id TEXT,
            vendor_name TEXT,
            order_quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            urgency TEXT,
            agreement_source TEXT,
            agreement_terms TEXT,
            reasoning TEXT,
            telemetry_json TEXT,
            status TEXT DEFAULT 'pending_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS executed_purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT,
            sku TEXT NOT NULL,
            item_name TEXT,
            category TEXT,
            vendor_id TEXT,
            vendor_name TEXT,
            order_quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            execution_type TEXT DEFAULT 'DIRECT_AUTONOMOUS',
            agreement_source TEXT,
            agreement_terms TEXT,
            reasoning TEXT,
            reviewer_notes TEXT,
            telemetry_json TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Run safe column additions for pre-existing tables
    for col, ctype in [
        ("category", "TEXT"), ("vendor_name", "TEXT"), ("agreement_source", "TEXT"),
        ("agreement_terms", "TEXT"), ("telemetry_json", "TEXT")
    ]:
        _add_column_if_missing(cursor, "pending_review_queue", col, ctype)

    for col, ctype in [
        ("po_number", "TEXT"), ("item_name", "TEXT"), ("category", "TEXT"),
        ("vendor_name", "TEXT"), ("execution_type", "TEXT DEFAULT 'DIRECT_AUTONOMOUS'"),
        ("agreement_source", "TEXT"), ("agreement_terms", "TEXT"),
        ("reasoning", "TEXT"), ("telemetry_json", "TEXT")
    ]:
        _add_column_if_missing(cursor, "executed_purchase_orders", col, ctype)

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

def save_to_review_queue(
    draft: dict,
    urgency: str,
    reasoning: str,
    active_item: Optional[dict] = None,
    agreement_source: str = "",
    agreement_terms: str = "",
    telemetry: Optional[dict] = None
):
    sku = draft.get("sku") or (active_item.get("sku") if active_item else "")
    item_name = draft.get("item_name") or (active_item.get("item_name") if active_item else "")
    category = (active_item.get("category") if active_item else None) or draft.get("category", "Electronics")
    vendor_id = draft.get("vendor_id")
    vendor_name = draft.get("vendor_name", "")
    qty = int(draft.get("quantity", 0))
    unit_price = float(draft.get("unit_price", 0.0))
    total_amount = float(draft.get("total_amount", round(qty * unit_price, 2)))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pending_review_queue (
            sku, item_name, category, vendor_id, vendor_name,
            order_quantity, unit_price, total_amount, urgency,
            agreement_source, agreement_terms, reasoning, telemetry_json, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review');
    """, (
        sku, item_name, category, vendor_id, vendor_name,
        qty, unit_price, total_amount, urgency,
        agreement_source, agreement_terms, reasoning,
        json.dumps(telemetry) if telemetry else None
    ))
    conn.commit()
    conn.close()

def execute_autonomous_po(
    draft: dict,
    active_item: dict,
    agreement_source: str = "",
    agreement_terms: str = "",
    reasoning: str = "",
    telemetry: Optional[dict] = None
) -> Dict[str, Any]:
    sku = active_item.get("sku") or draft.get("sku")
    item_name = active_item.get("item_name") or draft.get("item_name", "")
    category = active_item.get("category", "Electronics")
    vendor_id = draft.get("vendor_id")
    vendor_name = draft.get("vendor_name", "")
    qty = int(draft.get("quantity", 0))
    unit_price = float(draft.get("unit_price", 0.0))
    total_amount = float(draft.get("total_amount", round(qty * unit_price, 2)))
    po_number = f"PO-{time.strftime('%Y%m%d%H%M%S')}-{sku}"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO executed_purchase_orders (
            po_number, sku, item_name, category, vendor_id, vendor_name,
            order_quantity, unit_price, total_amount, execution_type,
            agreement_source, agreement_terms, reasoning, reviewer_notes,
            telemetry_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DIRECT_AUTONOMOUS', ?, ?, ?, 'Auto-approved (within $5,000 threshold)', ?);
    """, (
        po_number, sku, item_name, category, vendor_id, vendor_name,
        qty, unit_price, total_amount,
        agreement_source, agreement_terms, reasoning,
        json.dumps(telemetry) if telemetry else None
    ))

    # Replenish warehouse inventory stock
    cursor.execute("""
        UPDATE inventory
        SET current_stock = current_stock + ?
        WHERE sku = ?;
    """, (qty, sku))

    conn.commit()
    cursor.execute("SELECT * FROM executed_purchase_orders WHERE id = last_insert_rowid();")
    created_ticket = dict(cursor.fetchone())
    conn.close()
    return created_ticket

def fetch_all_executed_tickets() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM executed_purchase_orders
        ORDER BY executed_at DESC, id DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_pending_reviews() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sku, item_name, category, vendor_id, vendor_name, order_quantity,
               unit_price, total_amount, urgency, agreement_source, agreement_terms,
               reasoning, telemetry_json, status, created_at
        FROM pending_review_queue
        WHERE status = 'pending_review'
        ORDER BY created_at DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def resolve_review_item(sku: str, approved: bool, override_qty: Optional[int] = None, notes: str = "") -> Optional[Dict[str, Any]]:
    """Updates pending status, creates executed order ticket, and increments stock on approval."""
    conn = get_db_connection()
    cursor = conn.cursor()
    new_status = "approved" if approved else "rejected"

    cursor.execute("""
        SELECT * FROM pending_review_queue 
        WHERE sku = ? AND status = 'pending_review' 
        ORDER BY created_at DESC LIMIT 1;
    """, (sku,))
    pending_row = cursor.fetchone()
    if not pending_row:
        conn.close()
        return None
    
    pending_dict = dict(pending_row)
    item_id = pending_dict["id"]

    cursor.execute("""
        UPDATE pending_review_queue
        SET status = ?
        WHERE id = ?;
    """, (new_status, item_id))

    executed_ticket = None
    if approved:
        qty = int(override_qty) if (override_qty and override_qty > 0) else int(pending_dict["order_quantity"])
        unit_p = float(pending_dict["unit_price"])
        total = round(qty * unit_p, 2)
        po_number = f"PO-{time.strftime('%Y%m%d%H%M%S')}-{sku}"

        cursor.execute("""
            INSERT INTO executed_purchase_orders (
                po_number, sku, item_name, category, vendor_id, vendor_name,
                order_quantity, unit_price, total_amount, execution_type,
                agreement_source, agreement_terms, reasoning, reviewer_notes, telemetry_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'HITL_APPROVED', ?, ?, ?, ?, ?);
        """, (
            po_number, sku, pending_dict.get("item_name"), pending_dict.get("category", "Electronics"),
            pending_dict.get("vendor_id"), pending_dict.get("vendor_name"),
            qty, unit_p, total,
            pending_dict.get("agreement_source"), pending_dict.get("agreement_terms"),
            pending_dict.get("reasoning"), notes or "Manager Approved via HITL",
            pending_dict.get("telemetry_json")
        ))

        # Replenish warehouse inventory
        cursor.execute("""
            UPDATE inventory
            SET current_stock = current_stock + ?
            WHERE sku = ?;
        """, (qty, sku))

        cursor.execute("SELECT * FROM executed_purchase_orders WHERE id = last_insert_rowid();")
        executed_ticket = dict(cursor.fetchone())
    else:
        # On rejection, bump stock above reorder point to simulate operational cancellation
        cursor.execute("""
            UPDATE inventory
            SET current_stock = reorder_point + 1
            WHERE sku = ?;
        """, (sku,))

    conn.commit()
    conn.close()
    return executed_ticket