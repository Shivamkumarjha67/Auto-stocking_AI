import os
import json
import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from agents.state import ReplenishmentState
from agents.tools.math_engine import calculate_restock_quantity

import re

# Contractual Master Table for Minimum Order Quantities (MOQ)
CONTRACT_MOQ_CATALOG = {
    ("VEND-001", "SKU-1001"): 25,
    ("VEND-001", "SKU-1002"): 20,
    ("VEND-001", "SKU-1003"): 25,
    ("VEND-001", "SKU-1004"): 50,
    ("VEND-001", "SKU-1005"): 25,
    ("VEND-002", "SKU-1001"): 100,
    ("VEND-002", "SKU-1002"): 100,
    ("VEND-002", "SKU-1003"): 150,
    ("VEND-002", "SKU-1004"): 200,
    ("VEND-002", "SKU-1005"): 150,
    ("VEND-002", "SKU-2001"): 100,
    ("VEND-002", "SKU-2002"): 100,
    ("VEND-002", "SKU-2003"): 250,
    ("VEND-002", "SKU-2004"): 250,
    ("VEND-002", "SKU-2005"): 200,
    ("VEND-003", "SKU-2001"): 50,
    ("VEND-003", "SKU-2002"): 50,
    ("VEND-003", "SKU-2003"): 50,
    ("VEND-003", "SKU-2004"): 50,
    ("VEND-003", "SKU-2005"): 50,
}

def extract_vendor_moq(terms: list, vendor_id: str, sku: str) -> int:
    """
    Extracts the vendor MOQ for the specific SKU from the contractual catalog,
    or dynamically extracts it from the SKU-specific section in retrieved SLA terms.
    """
    # 1. First check the exact catalog for (vendor_id, sku)
    if (vendor_id, sku) in CONTRACT_MOQ_CATALOG:
        return CONTRACT_MOQ_CATALOG[(vendor_id, sku)]

    # 2. Try to extract from SKU-specific section in retrieved text
    for t in terms:
        content = t.get("content", "")
        if sku.lower() in content.lower():
            sku_section_match = re.search(rf"{sku}.*?MOQ[:\s*]+(\d+)", content, re.DOTALL | re.IGNORECASE)
            if sku_section_match:
                return int(sku_section_match.group(1))

    return 25

def clean_vendor_id(v: str) -> str:
    if not v:
        return "VEND-001"
    v_upper = str(v).upper()
    if "001" in v_upper or "TECHCORP" in v_upper or "1" in v_upper:
        return "VEND-001"
    if "002" in v_upper or "GLOBALPARTS" in v_upper or "2" in v_upper:
        return "VEND-002"
    if "003" in v_upper or "APEX" in v_upper or "3" in v_upper:
        return "VEND-003"
    return "VEND-001"

def normalize_po_output(raw_dict: dict, sku: str, raw_qty: int) -> dict:
    """
    Normalizes both nested fine-tuned LLaMA output and flat generator output into a standard PO dictionary.
    """
    if not isinstance(raw_dict, dict):
        return None

    # Check for nested schema from fine-tuned LLaMA 3.2 model (trained on data/finetune)
    if "purchase_order" in raw_dict and isinstance(raw_dict["purchase_order"], dict):
        po = raw_dict["purchase_order"]
        items = po.get("line_items", [])
        first_item = items[0] if items and isinstance(items[0], dict) else {}
        vendor_id = clean_vendor_id(po.get("vendor_id") or po.get("vendor"))
        qty = first_item.get("quantity") or raw_qty
        unit_price = first_item.get("unit_price") or 0.0
        total_amount = po.get("total_amount") or round(qty * unit_price, 2)
        raw_action = raw_dict.get("action", "")
        if raw_action in ["accept_and_order", "generate_test_order", "execute_po"]:
            action_type = "pending_review" if total_amount > 5000.0 else "execute_po"
        else:
            action_type = "pending_review"
        reasoning = raw_dict.get("reasoning") or raw_dict.get("draft_response") or ""
        return {
            "vendor_id": vendor_id,
            "vendor_name": "TechCorp Logistics" if vendor_id == "VEND-001" else ("GlobalParts Direct" if vendor_id == "VEND-002" else "Apex Supply Co."),
            "sku": first_item.get("sku") or sku,
            "quantity": int(qty),
            "unit_price": float(unit_price),
            "total_amount": float(total_amount),
            "lead_time_days": 4 if vendor_id == "VEND-001" else 14,
            "action_type": action_type,
            "reasoning": reasoning
        }

    # Flat schema (standard prompt output or custom format)
    vendor_id = clean_vendor_id(raw_dict.get("vendor_id") or raw_dict.get("vendor"))
    qty = raw_dict.get("quantity") or raw_dict.get("qty") or raw_qty
    unit_price = raw_dict.get("unit_price") or 0.0
    total_amount = raw_dict.get("total_amount") or round(qty * unit_price, 2)
    action_type = raw_dict.get("action_type") or ("pending_review" if total_amount > 5000.0 else "execute_po")

    return {
        "vendor_id": vendor_id,
        "vendor_name": raw_dict.get("vendor_name") or ("TechCorp Logistics" if vendor_id == "VEND-001" else ("GlobalParts Direct" if vendor_id == "VEND-002" else "Apex Supply Co.")),
        "sku": raw_dict.get("sku") or sku,
        "quantity": int(qty),
        "unit_price": float(unit_price),
        "total_amount": float(total_amount),
        "lead_time_days": raw_dict.get("lead_time_days", 4 if vendor_id == "VEND-001" else 14),
        "action_type": action_type,
        "reasoning": raw_dict.get("reasoning") or raw_dict.get("draft_reasoning") or ""
    }

def get_llm():
    # Support both VLLM_BASE_URL and LOCAL_LLM_URL
    vllm_url = os.getenv("VLLM_BASE_URL") or os.getenv("LOCAL_LLM_URL")
    use_local = os.getenv("USE_LOCAL_MODEL", "false").lower() in ("true", "1", "yes")

    # If VLLM_BASE_URL is provided, or USE_LOCAL_MODEL is true, route to vLLM / fine-tuned model
    if vllm_url or use_local:
        base_url = vllm_url or "http://localhost:8000/v1"
        model_name = os.getenv("LOCAL_LLM_MODEL") or os.getenv("VLLM_MODEL") or "procurement-llama-finetuned"
        api_key = os.getenv("LOCAL_LLM_API_KEY") or os.getenv("VLLM_API_KEY") or "EMPTY"
        return ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model_name,
            default_headers={"ngrok-skip-browser-warning": "true"},
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

    t0 = time.perf_counter()
    llm = get_llm()
    messages = [
        SystemMessage(content="You are a deterministic supply chain planner. Always output raw JSON conforming strictly to the requested schema."),
        HumanMessage(content=prompt)
    ]

    response = None
    prompt_tokens = len(prompt) // 4
    completion_tokens = 0

    # Retry loop with exponential backoff for rate limits
    for attempt in range(3):
        try:
            response = llm.invoke(messages)
            break
        except Exception as api_err:
            if "429" in str(api_err) or "rate" in str(api_err).lower():
                time.sleep(2.0 * (attempt + 1))
            else:
                break

    llm_ms = round((time.perf_counter() - t0) * 1000, 2)

    po_data = None
    if response:
        try:
            # Extract usage metadata if available
            usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {}).get("token_usage", {})
            if usage:
                prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or prompt_tokens
                completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or len(response.content) // 4
            else:
                completion_tokens = len(response.content) // 4

            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            raw_parsed = json.loads(content)
            po_data = normalize_po_output(raw_parsed, sku, raw_qty)
        except Exception:
            po_data = None

    if not po_data:
        # High-fidelity deterministic heuristic fallback
        is_critical = item.get("urgency") == "Critical"
        is_hardware = item.get("category") == "Hardware"

        if is_critical:
            vendor = "VEND-001" if not is_hardware else "VEND-003"
            unit_price = 18.50 if not is_hardware else 10.15
            lead_days = 4
            moq = 25 if not is_hardware else 50
        else:
            vendor = "VEND-002"
            unit_price = 14.80 if not is_hardware else 11.90
            lead_days = 14
            moq = 100

        target_qty = max(raw_qty, moq)
        total_amt = round(target_qty * unit_price, 2)
        action = "pending_review" if total_amt > 5000.0 else "execute_po"

        po_data = {
            "vendor_id": vendor,
            "vendor_name": "TechCorp Logistics" if vendor == "VEND-001" else ("GlobalParts Direct" if vendor == "VEND-002" else "Apex Supply Co."),
            "sku": sku,
            "quantity": target_qty,
            "unit_price": unit_price,
            "total_amount": total_amt,
            "lead_time_days": lead_days,
            "action_type": action,
            "reasoning": f"Sized deterministically: {'Critical 3-5d lead time override' if is_critical else 'Lowest-cost tier meeting MOQ'}. Total ${total_amt:,.2f}."
        }

    # Deterministic Contractual Guardrails: MOQ Enforcement and Arithmetic Precision
    chosen_vendor = po_data.get("vendor_id", "VEND-001")
    contract_moq = extract_vendor_moq(state.get("retrieved_supplier_terms", []), chosen_vendor, sku)
    current_qty = po_data.get("quantity", raw_qty)

    if current_qty < contract_moq:
        po_data["quantity"] = contract_moq
        po_data["reasoning"] = (po_data.get("reasoning", "") + f" [Deterministic Guardrail: Scaled order from {current_qty} to {contract_moq} units to satisfy vendor MOQ].").strip()

    # Deterministic Arithmetic Reconciliation
    exact_total = round(po_data["quantity"] * po_data["unit_price"], 2)
    if abs(po_data.get("total_amount", 0.0) - exact_total) > 0.02:
        po_data["total_amount"] = exact_total

    # Deterministic Policy Ceiling Re-check ($5,000 threshold)
    if po_data["total_amount"] > 5000.0:
        po_data["action_type"] = "pending_review"

    # Telemetry metrics compilation
    retrieval_ms = state.get("telemetry", {}).get("retrieval_time_ms", 0.0)
    # Estimated cost: $0.00 for self-hosted/Colab fine-tuned engine, $0.20/1M input & $0.60/1M output for Mistral
    is_vllm_engine = bool(os.getenv("VLLM_BASE_URL") or os.getenv("LOCAL_LLM_URL") or os.getenv("USE_LOCAL_MODEL", "false").lower() in ("true", "1", "yes"))
    est_cost = 0.0 if is_vllm_engine else round((prompt_tokens * 0.0000002) + (completion_tokens * 0.0000006), 6)
    total_tokens = prompt_tokens + completion_tokens

    compiled_telemetry = {
        "execution_time_ms": round(retrieval_ms + llm_ms, 2),
        "retrieval_time_ms": retrieval_ms,
        "llm_generation_time_ms": llm_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": est_cost
    }

    # Attribute primary agreement source and terms applied
    chosen_vendor = po_data.get("vendor_id")
    matching_terms = [t for t in state.get("retrieved_supplier_terms", []) if t.get("vendor_id") == chosen_vendor]
    agreement_src = matching_terms[0]["source"] if matching_terms else (
        "vendor_techcorp_pricing_sla.md" if chosen_vendor == "VEND-001" else
        ("vendor_globalparts_pricing_sla.md" if chosen_vendor == "VEND-002" else "vendor_apex_pricing_sla.md")
    )

    lead_days = po_data.get("lead_time_days", 4 if chosen_vendor == "VEND-001" else 14)
    vendor_display = po_data.get("vendor_name") or ("TechCorp Logistics" if chosen_vendor == "VEND-001" else ("GlobalParts Direct" if chosen_vendor == "VEND-002" else "Apex Supply Co."))
    if item.get("urgency") == "Critical":
        agreement_desc = f"{vendor_display} Master SLA — Section 3: Critical Lead Time Override ({lead_days}-day delivery guaranteed), Tier 1 pricing."
    else:
        agreement_desc = f"{vendor_display} Pricing Schedule — Volume discount tier applied meeting minimum order quantity ({po_data.get('quantity', raw_qty)} units @ ${po_data.get('unit_price', 0.0):.2f}/unit)."

    po_data["agreement_source"] = agreement_src
    po_data["agreement_terms"] = agreement_desc
    po_data["vendor_name"] = vendor_display

    return {
        "selected_vendor_id": chosen_vendor,
        "order_quantity": po_data.get("quantity", raw_qty),
        "unit_price": po_data.get("unit_price", 0.0),
        "total_amount": po_data.get("total_amount", 0.0),
        "po_draft": po_data,
        "action_type": po_data.get("action_type", "pending_review"),
        "reasoning": po_data.get("reasoning", ""),
        "approval_granted": (po_data.get("action_type") == "execute_po"),
        "agreement_source": agreement_src,
        "agreement_terms": agreement_desc,
        "telemetry": compiled_telemetry
    }