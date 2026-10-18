import pytest
from fastapi.testclient import TestClient
from app.main import app
from agents.tools.erp_sql_tool import (
    get_db_connection,
    init_review_queue_table,
    fetch_all_executed_tickets,
    get_all_pending_reviews,
    scan_reorder_triggers
)

@pytest.fixture(autouse=True)
def reset_db():
    conn = get_db_connection()
    with open("data/mock_db/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    with open("data/mock_db/seed_data.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    init_review_queue_table()
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_review_queue;")
    cursor.execute("DELETE FROM executed_purchase_orders;")
    # Configure SKU-1005 to trigger high-value spend (> $5,000) for HITL testing:
    # 14 days * 40 units/day = 560 units target buffer.
    # Current stock 10 units -> Restock needed: 550 units.
    # 550 units * $14.80/unit = $8,140.00 > $5,000.00 limit.
    cursor.execute("""
        UPDATE inventory 
        SET daily_sales_rate = 40.0, current_stock = 10, reorder_point = 560 
        WHERE sku = 'SKU-1005';
    """)
    conn.commit()
    conn.close()

@pytest.fixture
def client():
    return TestClient(app)

def test_batch_replenishment_and_ticket_generation(client):
    # Step 1: Pre-check triggered low-stock SKUs
    low_stock = scan_reorder_triggers()
    assert len(low_stock) >= 3, "Database should contain at least 3 low-stock items"

    # Step 2: Trigger continuous autonomous replenishment
    resp = client.post("/trigger-replenishment")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "completed"
    assert data["total_evaluated"] == len(low_stock)
    assert data["directly_executed_count"] > 0
    assert data["pending_review_count"] > 0
    assert data["directly_executed_count"] + data["pending_review_count"] == len(low_stock)

    # Step 3: Verify executed tickets endpoint
    tickets_resp = client.get("/tickets")
    assert tickets_resp.status_code == 200
    tickets = tickets_resp.json()
    assert len(tickets) == data["directly_executed_count"]

    for ticket in tickets:
        assert ticket["execution_type"] == "DIRECT_AUTONOMOUS"
        assert ticket["po_number"].startswith("PO-")
        assert ticket["agreement_source"] is not None and len(ticket["agreement_source"]) > 0
        assert ticket["agreement_terms"] is not None and len(ticket["agreement_terms"]) > 0
        assert ticket["total_amount"] <= 5000.0

    # Step 4: Verify HITL queue for items exceeding threshold
    pending_resp = client.get("/pending-reviews")
    assert pending_resp.status_code == 200
    pending_queue = pending_resp.json()["queue"]
    assert len(pending_queue) == data["pending_review_count"]

    # Verify SKU-1005 is in the HITL queue with agreement attribution
    hitl_item = next((item for item in pending_queue if item["sku"] == "SKU-1005"), None)
    assert hitl_item is not None
    assert hitl_item["total_amount"] > 5000.0
    assert hitl_item["agreement_source"] is not None
    assert hitl_item["agreement_terms"] is not None

    # Step 5: Test Sequential HITL Approval flow
    approve_resp = client.post("/approve-po", json={
        "sku": "SKU-1005",
        "approved": True,
        "override_quantity": 400,
        "reviewer_notes": "Manager authorized partial override."
    })
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["status"] == "executed"
    assert approve_data["ticket"] is not None
    assert approve_data["ticket"]["execution_type"] == "HITL_APPROVED"
    assert approve_data["ticket"]["order_quantity"] == 400
    assert approve_data["ticket"]["reviewer_notes"] == "Manager authorized partial override."

    # Step 6: Verify executed ticket promoted to /tickets
    updated_tickets = client.get("/tickets").json()
    assert len(updated_tickets) == len(tickets) + 1
    promoted = next((t for t in updated_tickets if t["sku"] == "SKU-1005"), None)
    assert promoted is not None
    assert promoted["execution_type"] == "HITL_APPROVED"
    assert promoted["order_quantity"] == 400
    assert promoted["agreement_source"] is not None

    # Step 7: Verify pending queue decremented
    remaining_pending = client.get("/pending-reviews").json()["queue"]
    assert len(remaining_pending) == len(pending_queue) - 1
    assert not any(p["sku"] == "SKU-1005" for p in remaining_pending)
