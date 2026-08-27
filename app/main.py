from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from agents.graph import build_autostock_agent

app = FastAPI(
    title="AutoStock-AI Procurement API",
    description="Autonomous replenishment and purchase order routing system.",
    version="1.0.0"
)

agent = build_autostock_agent()

class TriggerResponse(BaseModel):
    status: str
    active_sku: Optional[str] = None
    urgency: Optional[str] = None
    vendor_id: Optional[str] = None
    order_quantity: int = 0
    total_amount: float = 0.0
    action_type: str
    reasoning: str
    po_draft: Optional[Dict[str, Any]] = None

class ApprovalRequest(BaseModel):
    sku: str
    approved: bool
    override_quantity: Optional[int] = None
    reviewer_notes: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "autostock-ai"}

@app.post("/trigger-replenishment", response_model=TriggerResponse)
def run_replenishment():
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
    active_item = result.get("active_item")

    if not active_item:
        return TriggerResponse(
            status="completed",
            action_type="no_action_needed",
            reasoning=result.get("reasoning", "All stock levels are above reorder thresholds.")
        )

    return TriggerResponse(
        status="completed",
        active_sku=active_item["sku"],
        urgency=active_item["urgency"],
        vendor_id=result.get("selected_vendor_id"),
        order_quantity=result.get("order_quantity", 0),
        total_amount=result.get("total_amount", 0.0),
        action_type=result.get("action_type"),
        reasoning=result.get("reasoning"),
        po_draft=result.get("po_draft")
    )

@app.post("/approve-po")
def approve_purchase_order(payload: ApprovalRequest):
    if not payload.approved:
        return {
            "status": "rejected",
            "sku": payload.sku,
            "message": f"PO rejected. Notes: {payload.reviewer_notes}"
        }
    
    return {
        "status": "executed",
        "sku": payload.sku,
        "message": "Purchase order approved by manager. Transmitted to supplier ERP."
    }