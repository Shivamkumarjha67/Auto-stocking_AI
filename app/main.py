import os
import shutil
from typing import Optional, Dict, Any, List, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from agents.graph import build_autostock_agent
from agents.tools.erp_sql_tool import (
    init_review_queue_table,
    fetch_all_inventory,
    bulk_replace_inventory,
    get_all_pending_reviews,
    resolve_review_item,
    save_to_review_queue
)
from rag.indexer import build_vector_store

agent = build_autostock_agent()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_review_queue_table()
    yield

app = FastAPI(
    title="AutoStock-AI Procurement API",
    description="Autonomous replenishment and purchase order routing system.",
    version="1.0.0",
    lifespan=lifespan
)

class InventoryItem(BaseModel):
    sku: str
    item_name: str
    category: Literal["Electronics", "Hardware"] = "Electronics"
    current_stock: int
    reorder_point: int
    daily_sales_rate: float
    unit_holding_cost: float = 1.5

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

@app.get("/inventory", response_model=List[Dict[str, Any]])
def get_inventory():
    return fetch_all_inventory()

@app.post("/inventory/load-json")
def load_inventory(items: List[InventoryItem]):
    if not items:
        raise HTTPException(status_code=400, detail="Inventory item list cannot be empty.")
    raw_dicts = [item.model_dump() for item in items]
    bulk_replace_inventory(raw_dicts)
    return {
        "status": "success",
        "items_loaded": len(items),
        "message": "Warehouse inventory successfully updated."
    }

@app.post("/rag/upload-document")
async def upload_document(file: UploadFile = File(...)):
    save_dir = "data/raw/supplier_contracts"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        build_vector_store()
        return {
            "status": "success",
            "filename": file.filename,
            "message": f"{file.filename} saved and re-indexed into ChromaDB/BM25."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

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
    
    try:
        result = agent.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent execution failure: {str(e)}")

    active_item = result.get("active_item")
    if not active_item:
        return TriggerResponse(
            status="completed",
            action_type="no_action_needed",
            reasoning=result.get("reasoning", "All stock levels are above reorder thresholds.")
        )

    # Persist flagged order if sent to review
    if result.get("action_type") == "pending_review":
        po_draft = result.get("po_draft") or {
            "sku": active_item["sku"],
            "item_name": active_item.get("item_name", ""),
            "vendor_id": result.get("selected_vendor_id"),
            "quantity": result.get("order_quantity", 0),
            "unit_price": result.get("unit_price", 0.0),
            "total_amount": result.get("total_amount", 0.0)
        }
        save_to_review_queue(
            draft=po_draft,
            urgency=active_item["urgency"],
            reasoning=result.get("reasoning", "")
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

@app.get("/pending-reviews")
def list_pending_reviews():
    pending = get_all_pending_reviews()
    return {"total_pending": len(pending), "queue": pending}

@app.post("/approve-po")
def approve_purchase_order(payload: ApprovalRequest):
    resolve_review_item(
        sku=payload.sku,
        approved=payload.approved,
        override_qty=payload.override_quantity,
        notes=payload.reviewer_notes or ""
    )
    
    status_str = "executed" if payload.approved else "rejected"
    msg = (
        f"PO for {payload.sku} approved and committed to ERP."
        if payload.approved
        else f"PO for {payload.sku} rejected. Reason: {payload.reviewer_notes}"
    )
    return {"status": status_str, "sku": payload.sku, "message": msg}