from langgraph.graph import StateGraph, START, END
from agents.state import ReplenishmentState
from agents.nodes.inventory_monitor import inventory_monitor_node
from agents.nodes.supplier_matcher import supplier_matcher_node
from agents.nodes.po_generator import po_generator_node
from agents.nodes.human_review import human_review_node

def route_after_monitoring(state: ReplenishmentState) -> str:
    if not state.get("active_item"):
        return END
    return "supplier_matcher"

def route_after_po_generation(state: ReplenishmentState) -> str:
    total = state.get("total_amount", 0.0)
    action = state.get("action_type")
    
    if action == "pending_review" or total > 5000.0:
        return "human_review"
    return END

def build_autostock_agent():
    workflow = StateGraph(ReplenishmentState)

    workflow.add_node("inventory_monitor", inventory_monitor_node)
    workflow.add_node("supplier_matcher", supplier_matcher_node)
    workflow.add_node("po_generator", po_generator_node)
    workflow.add_node("human_review", human_review_node)

    workflow.add_edge(START, "inventory_monitor")
    workflow.add_conditional_edges("inventory_monitor", route_after_monitoring)
    workflow.add_edge("supplier_matcher", "po_generator")
    workflow.add_conditional_edges("po_generator", route_after_po_generation)
    workflow.add_edge("human_review", END)

    return workflow.compile()

agent_app = build_autostock_agent()

if __name__ == "__main__":
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
        "approval_granted": False,
        "telemetry": None
    }
    result = agent_app.invoke(initial_state)
    print("\n=== AGENT EXECUTION SUMMARY ===")
    print(f"Target SKU: {result['active_item']['sku']} ({result['active_item']['item_name']})")
    print(f"Urgency Level: {result['active_item']['urgency']} (Runway: {result['active_item']['runway_days']} days)")
    print(f"Selected Vendor: {result['selected_vendor_id']}")
    print(f"Order Quantity: {result['order_quantity']} units @ ${result['unit_price']}/unit")
    print(f"Total Amount: ${result['total_amount']}")
    print(f"Action Type: {result['action_type']}")
    print(f"Reasoning: {result['reasoning']}")