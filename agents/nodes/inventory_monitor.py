from agents.state import ReplenishmentState
from agents.tools.erp_sql_tool import scan_reorder_triggers

def inventory_monitor_node(state: ReplenishmentState) -> dict:
    triggered = scan_reorder_triggers()
    if not triggered:
        return {
            "low_stock_items": [],
            "active_item": None,
            "action_type": "no_action_needed",
            "reasoning": "All SKUs are above reorder points."
        }
    
    return {
        "low_stock_items": triggered,
        "active_item": triggered[0]
    }