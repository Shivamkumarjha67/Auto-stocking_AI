from agents.state import ReplenishmentState
from rag.hybrid_retriever import HybridSupplierRetriever

retriever = HybridSupplierRetriever()

def supplier_matcher_node(state: ReplenishmentState) -> dict:
    item = state.get("active_item")
    if not item:
        return {}

    sku = item["sku"]
    # 1. Retrieve contract terms for SKU
    contract_docs = retriever.retrieve(f"What are the volume pricing tiers, lead times, and MOQs for {sku}?", top_k=4)
    # 2. Retrieve internal policy constraints
    policy_docs = retriever.retrieve("autonomous purchase order spending limit and runway rules", top_k=2)

    terms = [
        {"source": d.metadata.get("source"), "content": d.page_content, "vendor_id": d.metadata.get("supplier_id")}
        for d in contract_docs
    ]
    policy_text = "\n".join([d.page_content for d in policy_docs])

    return {
        "retrieved_supplier_terms": terms,
        "procurement_policy_context": policy_text
    }