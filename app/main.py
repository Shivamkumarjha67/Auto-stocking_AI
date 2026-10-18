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
    save_to_review_queue,
    scan_reorder_triggers,
    execute_autonomous_po,
    fetch_all_executed_tickets
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

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autostock.api")

class TriggerResponse(BaseModel):
    status: str
    total_evaluated: int = 0
    directly_executed_count: int = 0
    pending_review_count: int = 0
    executed_tickets: List[Dict[str, Any]] = []
    pending_reviews: List[Dict[str, Any]] = []
    active_sku: Optional[str] = None
    urgency: Optional[str] = None
    vendor_id: Optional[str] = None
    order_quantity: int = 0
    total_amount: float = 0.0
    action_type: str = "completed"
    reasoning: str = ""
    po_draft: Optional[Dict[str, Any]] = None
    telemetry: Optional[Dict[str, Any]] = None
    message: str = ""

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

@app.post("/inventory/reset-db")
def reset_db_endpoint():
    from scripts.reset_db import reset_database
    reset_database(include_hitl_demo=True)
    return {"status": "success", "message": "Database successfully reset to clean pre-replenishment demo state."}

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
    triggered_items = scan_reorder_triggers()
    if not triggered_items:
        return TriggerResponse(
            status="completed",
            total_evaluated=0,
            directly_executed_count=0,
            pending_review_count=0,
            executed_tickets=[],
            pending_reviews=[],
            action_type="no_action_needed",
            reasoning="All stock levels are above reorder thresholds.",
            message="All warehouse SKUs are currently at or above healthy stock levels."
        )

    executed_tickets = []
    pending_reviews = []
    last_result = None

    for item in triggered_items:
        initial_state = {
            "low_stock_items": [item],
            "active_item": item,
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
            "telemetry": None,
            "agreement_source": None,
            "agreement_terms": None
        }

        try:
            result = agent.invoke(initial_state)
            last_result = result
        except Exception as e:
            logger.error(f"Agent execution failure for SKU {item.get('sku')}: {str(e)}")
            continue

        po_draft = result.get("po_draft") or {
            "sku": item["sku"],
            "item_name": item.get("item_name", ""),
            "vendor_id": result.get("selected_vendor_id"),
            "vendor_name": "TechCorp Logistics" if result.get("selected_vendor_id") == "VEND-001" else ("GlobalParts Direct" if result.get("selected_vendor_id") == "VEND-002" else "Apex Supply Co."),
            "quantity": result.get("order_quantity", 0),
            "unit_price": result.get("unit_price", 0.0),
            "total_amount": result.get("total_amount", 0.0)
        }
        urgency = item.get("urgency", "Watch")
        agreement_src = result.get("agreement_source") or po_draft.get("agreement_source", "")
        agreement_terms = result.get("agreement_terms") or po_draft.get("agreement_terms", "")
        reasoning = result.get("reasoning", "")
        telemetry_data = result.get("telemetry") or {}
        action_type = result.get("action_type")

        if action_type == "execute_po":
            ticket = execute_autonomous_po(
                draft=po_draft,
                active_item=item,
                agreement_source=agreement_src,
                agreement_terms=agreement_terms,
                reasoning=reasoning,
                telemetry=telemetry_data
            )
            executed_tickets.append(ticket)
            logger.info(
                f"Direct autonomous replenishment executed: PO {ticket.get('po_number')} "
                f"for SKU {item['sku']} (${ticket.get('total_amount'):,.2f})"
            )
        else:
            save_to_review_queue(
                draft=po_draft,
                urgency=urgency,
                reasoning=reasoning,
                active_item=item,
                agreement_source=agreement_src,
                agreement_terms=agreement_terms,
                telemetry=telemetry_data
            )
            pending_reviews.append({
                "sku": item["sku"],
                "item_name": item.get("item_name"),
                "category": item.get("category"),
                "vendor_id": result.get("selected_vendor_id"),
                "vendor_name": po_draft.get("vendor_name"),
                "order_quantity": result.get("order_quantity", 0),
                "unit_price": result.get("unit_price", 0.0),
                "total_amount": result.get("total_amount", 0.0),
                "urgency": urgency,
                "agreement_source": agreement_src,
                "agreement_terms": agreement_terms,
                "reasoning": reasoning,
                "telemetry": telemetry_data
            })
            logger.info(
                f"Replenishment queued for HITL review for SKU {item['sku']} (${result.get('total_amount', 0.0):,.2f})"
            )

    active_sku_disp = triggered_items[0]["sku"] if triggered_items else None
    first_urgency = triggered_items[0].get("urgency") if triggered_items else None
    first_vendor = (last_result or {}).get("selected_vendor_id")
    first_qty = (last_result or {}).get("order_quantity", 0)
    first_tot = (last_result or {}).get("total_amount", 0.0)
    first_act = (last_result or {}).get("action_type", "completed")

    msg = (
        f"Batch evaluated {len(triggered_items)} SKU(s): "
        f"{len(executed_tickets)} autonomous order(s) placed, "
        f"{len(pending_reviews)} queued for human approval."
    )

    return TriggerResponse(
        status="completed",
        total_evaluated=len(triggered_items),
        directly_executed_count=len(executed_tickets),
        pending_review_count=len(pending_reviews),
        executed_tickets=executed_tickets,
        pending_reviews=pending_reviews,
        active_sku=active_sku_disp,
        urgency=first_urgency,
        vendor_id=first_vendor,
        order_quantity=first_qty,
        total_amount=first_tot,
        action_type=first_act,
        reasoning=(last_result or {}).get("reasoning", msg),
        po_draft=(last_result or {}).get("po_draft"),
        telemetry=(last_result or {}).get("telemetry"),
        message=msg
    )

@app.get("/tickets", response_model=List[Dict[str, Any]])
def get_executed_tickets():
    return fetch_all_executed_tickets()

@app.get("/pending-reviews")
def list_pending_reviews():
    pending = get_all_pending_reviews()
    return {"total_pending": len(pending), "queue": pending}

@app.post("/approve-po")
def approve_purchase_order(payload: ApprovalRequest):
    ticket = resolve_review_item(
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
    return {"status": status_str, "sku": payload.sku, "message": msg, "ticket": ticket}