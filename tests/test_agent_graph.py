import pytest
from agents.graph import build_autostock_agent
from agents.tools.erp_sql_tool import get_db_connection

@pytest.fixture(autouse=True)
def reset_db():
    conn = get_db_connection()
    with open("data/mock_db/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    with open("data/mock_db/seed_data.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()

@pytest.fixture(scope="module")
def agent():
    return build_autostock_agent()

def test_critical_item_prioritization(agent):
    initial_state = {
        "low_stock_items": [],
        "active_item": None,
        "retrieved_supplier_terms": [],
        "procurement_policy_context": "",
        "selected_vendor_id": None,
        "order_quantity": 0,
        "unit_price": 0.0,
        "total_amount": 0.0,
        "po_draft": None,
        "action_type": "pending_review",
        "reasoning": "",
        "approval_granted": False
    }
    result = agent.invoke(initial_state)

    # 1. Verification of DB Scan & Urgency
    assert result["active_item"] is not None
    assert result["active_item"]["sku"] == "SKU-1003"
    assert result["active_item"]["urgency"] == "Critical"
    assert result["active_item"]["runway_days"] < 3.0

    # 2. Verification of Selected Supplier & Sizing
    assert result["selected_vendor_id"] in ["VEND-001", "VEND-002"]
    assert result["order_quantity"] > 0
    assert result["total_amount"] > 0.0

    # 3. Verification of Gatekeeper Policy ($5,000 threshold)
    if result["total_amount"] > 5000.0:
        assert result["action_type"] == "pending_review"
        assert result["approval_granted"] is False
    else:
        assert result["action_type"] == "execute_po"
        assert result["approval_granted"] is True

    # 4. Verification of Telemetry Tracking
    assert "telemetry" in result
    assert result["telemetry"] is not None
    assert result["telemetry"]["execution_time_ms"] > 0
    assert result["telemetry"]["total_tokens"] > 0