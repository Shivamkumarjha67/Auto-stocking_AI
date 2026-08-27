import sqlite3
from typing import List, Dict, Any

DB_PATH = "data/mock_db/warehouse.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def scan_reorder_triggers() -> List[Dict[str, Any]]:
    """Fetches all items where current_stock <= reorder_point sorted by critical urgency."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT sku, item_name, category, current_stock, reorder_point, daily_sales_rate, unit_holding_cost
        FROM inventory
        WHERE current_stock <= reorder_point
        ORDER BY (current_stock / daily_sales_rate) ASC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    triggered_items = []
    for r in rows:
        runway = round(r["current_stock"] / r["daily_sales_rate"], 2)
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
    """Queries candidate suppliers from the relational catalog."""
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