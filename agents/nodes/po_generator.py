import os
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from agents.state import ReplenishmentState
from agents.tools.math_engine import calculate_restock_quantity

def get_llm():
    local_base_url = os.getenv("LOCAL_LLM_URL", "http://localhost:8000/v1")
    if os.getenv("USE_LOCAL_MODEL", "false").lower() == "true":
        return ChatOpenAI(
            base_url=local_base_url,
            api_key="none",
            model="procurement-llama-finetuned",
            temperature=0.0
        )
    return ChatMistralAI(model="mistral-small-latest", temperature=0.0)

def po_generator_node(state: ReplenishmentState) -> dict:
    item = state.get("active_item")
    if not item:
        return {"action_type": "no_action_needed"}

    sku = item["sku"]
    raw_qty = calculate_restock_quantity(item["current_stock"], item["daily_sales_rate"])
    contracts_context = "\n---\n".join([f"Source: {t['source']}\n{t['content']}" for t in state["retrieved_supplier_terms"]])
    policy_context = state.get("procurement_policy_context", "")

    prompt = f"""
You are AutoStock-AI's Autonomous Procurement Reasoning Engine.
Analyze the inventory state, candidate supplier contracts, and internal procurement policy to select the vendor and output a structured JSON PO.

### INVENTORY STATE:
- SKU: {sku} ({item['item_name']})
- Category: {item['category']}
- Current Stock: {item['current_stock']} units
- Daily Sales Rate: {item['daily_sales_rate']} units/day
- Runway Days: {item['runway_days']} days (Urgency: {item['urgency']})
- Target Units Needed for 14-day buffer: {raw_qty} units

### RETRIEVED SUPPLIER CONTRACTS & PRICING:
{contracts_context}

### INTERNAL PROCUREMENT POLICY:
{policy_context}

### STRICT VENDOR SELECTION POLICY:
1. CRITICAL STOCK OVERRIDE: If Urgency is 'Critical' (Runway < 3.0 days), you MUST select TechCorp Logistics ('VEND-001') for Electronics to prevent a stockout, as their 3-5 day lead time is required regardless of price premium.
2. If Urgency is 'Watch' (Runway >= 3.0 days), select the lowest-cost vendor ('VEND-002' or 'VEND-003').
3. Order quantity must satisfy the chosen vendor's MOQ.
4. Total amount = quantity * unit_price.
5. If total amount > $5,000.00, set action_type to "pending_review".
6. If total amount <= $5,000.00, set action_type to "execute_po".

Respond ONLY with a valid JSON object matching this schema:
{{
  "vendor_id": "VEND-001" | "VEND-002" | "VEND-003",
  "vendor_name": "string",
  "sku": "{sku}",
  "quantity": <int>,
  "unit_price": <float>,
  "total_amount": <float>,
  "lead_time_days": <int>,
  "action_type": "execute_po" | "pending_review" | "reject_and_escalate",
  "reasoning": "string"
}}
"""

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="You are a deterministic supply chain planner. Always output raw JSON conforming strictly to the requested schema."),
        HumanMessage(content=prompt)
    ])

    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        po_data = json.loads(content)
    except Exception as e:
        po_data = {
            "vendor_id": "VEND-001" if item["urgency"] == "Critical" else "VEND-002",
            "quantity": max(raw_qty, 50),
            "unit_price": 55.0 if item["urgency"] == "Critical" else 50.0,
            "total_amount": round(max(raw_qty, 50) * (55.0 if item["urgency"] == "Critical" else 50.0), 2),
            "action_type": "pending_review",
            "reasoning": f"Parsed via fallback heuristic: {str(e)}"
        }

    return {
        "selected_vendor_id": po_data.get("vendor_id"),
        "order_quantity": po_data.get("quantity", raw_qty),
        "unit_price": po_data.get("unit_price", 0.0),
        "total_amount": po_data.get("total_amount", 0.0),
        "po_draft": po_data,
        "action_type": po_data.get("action_type", "pending_review"),
        "reasoning": po_data.get("reasoning", "")
    }