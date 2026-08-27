from typing import TypedDict, List, Optional, Dict, Any

class InventoryItem(TypedDict):
    sku: str
    item_name: str
    category: str
    current_stock: int
    reorder_point: int
    daily_sales_rate: float
    unit_holding_cost: float
    runway_days: float
    urgency: str  # 'Critical', 'Watch', 'Healthy'

class ReplenishmentState(TypedDict):
    low_stock_items: List[InventoryItem]
    active_item: Optional[InventoryItem]
    retrieved_supplier_terms: List[Dict[str, Any]]
    procurement_policy_context: str
    selected_vendor_id: Optional[str]
    order_quantity: int
    unit_price: float
    total_amount: float
    po_draft: Optional[Dict[str, Any]]
    action_type: str  # 'execute_po', 'pending_review', 'reject_and_escalate', 'no_action_needed'
    reasoning: str
    approval_granted: bool