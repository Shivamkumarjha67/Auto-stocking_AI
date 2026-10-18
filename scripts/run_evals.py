import os
import sys
import json
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from agents.graph import build_autostock_agent
from rag.hybrid_retriever import HybridSupplierRetriever

def run_retrieval_benchmarks(golden_cases: List[Dict[str, Any]], retriever: HybridSupplierRetriever):
    """
    Evaluates Dense-only, BM25-only, and Hybrid (RRF) retrieval on Hit Rate@3 and MRR.
    """
    print("\n=======================================================")
    print(" 1. RUNNING RAG RETRIEVAL COMPARATIVE BENCHMARKS")
    print("=======================================================")

    results = {
        "dense": {"hits": 0, "mrr_sum": 0.0},
        "bm25": {"hits": 0, "mrr_sum": 0.0},
        "hybrid": {"hits": 0, "mrr_sum": 0.0}
    }
    total = len(golden_cases)

    # Prepare pure dense and bm25 accessors
    dense_retriever = retriever.vectorstore.as_retriever(search_kwargs={"k": 3})
    bm25_retriever = retriever.bm25_retriever
    bm25_retriever.k = 3

    import re
    for case in golden_cases:
        query = case["query"]
        target_sku = case.get("expected_sku")
        keywords = case.get("expected_retrieval_keywords", [])

        def is_match(doc_content: str) -> bool:
            # CASE-06 evaluates corporate spending policy retrieval
            if case.get("id") == "CASE-06":
                return any(k.lower() in doc_content.lower() for k in keywords)
            # SKU cases require strict part isolation
            if target_sku and "SKU-" in target_sku:
                return target_sku.lower() in doc_content.lower()
            return any(k.lower() in doc_content.lower() for k in keywords)

        # 1. Dense retrieval
        dense_docs = dense_retriever.invoke(query)
        dense_rank = None
        for idx, doc in enumerate(dense_docs[:3]):
            if is_match(doc.page_content):
                dense_rank = idx + 1
                break
        if dense_rank:
            results["dense"]["hits"] += 1
            results["dense"]["mrr_sum"] += 1.0 / dense_rank

        # 2. BM25 retrieval with SKU token isolation
        sku_matches = re.findall(r"SKU-\d{4}", query)
        bm25_query = f"{sku_matches[0]} pricing tiers MOQ lead time" if sku_matches else query
        bm25_docs = bm25_retriever.invoke(bm25_query)
        bm25_rank = None
        for idx, doc in enumerate(bm25_docs[:3]):
            if is_match(doc.page_content):
                bm25_rank = idx + 1
                break
        if bm25_rank:
            results["bm25"]["hits"] += 1
            results["bm25"]["mrr_sum"] += 1.0 / bm25_rank

        # 3. Hybrid RRF retrieval
        hybrid_docs = retriever.retrieve(query, top_k=3)
        hybrid_rank = None
        for idx, doc in enumerate(hybrid_docs[:3]):
            if is_match(doc.page_content):
                hybrid_rank = idx + 1
                break
        if hybrid_rank:
            results["hybrid"]["hits"] += 1
            results["hybrid"]["mrr_sum"] += 1.0 / hybrid_rank

    summary = {
        "Dense Only": {
            "Hit Rate@3": f"{(results['dense']['hits'] / total) * 100:.1f}%",
            "MRR": round(results["dense"]["mrr_sum"] / total, 3)
        },
        "BM25 Only": {
            "Hit Rate@3": f"{(results['bm25']['hits'] / total) * 100:.1f}%",
            "MRR": round(results["bm25"]["mrr_sum"] / total, 3)
        },
        "Hybrid RRF (AutoStock-AI)": {
            "Hit Rate@3": f"{(results['hybrid']['hits'] / total) * 100:.1f}%",
            "MRR": round(results["hybrid"]["mrr_sum"] / total, 3)
        }
    }

    print(f"{'Method':<30} | {'Hit Rate@3':<15} | {'MRR':<10}")
    print("-" * 62)
    for method, metrics in summary.items():
        print(f"{method:<30} | {metrics['Hit Rate@3']:<15} | {metrics['MRR']:<10}")

    return summary


def run_agent_decision_benchmarks(golden_cases: List[Dict[str, Any]]):
    """
    Evaluates end-to-end agent decision quality across golden cases.
    """
    print("\n=======================================================")
    print(" 2. RUNNING AGENT DECISION & GATEKEEPER BENCHMARKS")
    print("=======================================================")

    agent = build_autostock_agent()
    total = len(golden_cases)

    vendor_matches = 0
    moq_adherences = 0
    gatekeeper_correct = 0
    math_precise = 0
    latencies = []

    for case in golden_cases:
        item = case["inventory_state"]
        expected = case["expected_decision"]
        print(f"Evaluating Agent on [{case['id']}] {item['sku']}...", flush=True)

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
            "telemetry": None
        }

        t0 = time.perf_counter()
        result = agent.invoke(initial_state)
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)
        time.sleep(1.0)

        # 1. Vendor Selection
        chosen_vendor = result.get("selected_vendor_id")
        if chosen_vendor == expected["vendor_id"]:
            vendor_matches += 1

        # 2. MOQ Adherence
        qty = result.get("order_quantity", 0)
        if qty >= expected["min_quantity"]:
            moq_adherences += 1

        # 3. Gatekeeper Compliance ($5,000 threshold check)
        total_amt = result.get("total_amount", 0.0)
        action = result.get("action_type")
        if total_amt > 5000.0:
            if action == "pending_review":
                gatekeeper_correct += 1
        else:
            if action in ["execute_po", "pending_review"]:
                gatekeeper_correct += 1

        # 4. Arithmetic Precision
        unit_p = result.get("unit_price", 0.0)
        calc_total = round(qty * unit_p, 2)
        if abs(total_amt - calc_total) < 0.05:
            math_precise += 1

        print(f"[{case['id']}] SKU: {item['sku']} | Urgency: {item['urgency']} | Vendor: {chosen_vendor} (Exp: {expected['vendor_id']}) | Total: ${total_amt:,.2f} | Action: {action} | Time: {elapsed:.2f}s", flush=True)

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    agent_summary = {
        "Vendor Selection Accuracy": f"{(vendor_matches / total) * 100:.1f}%",
        "MOQ Adherence Rate": f"{(moq_adherences / total) * 100:.1f}%",
        "Policy Gatekeeper Compliance": f"{(gatekeeper_correct / total) * 100:.1f}%",
        "Arithmetic Precision": f"{(math_precise / total) * 100:.1f}%",
        "Avg Latency (s)": round(avg_latency, 2),
        "P95 Latency (s)": round(p95_latency, 2)
    }

    print("\n--- AGENT DECISION SCORECARD ---", flush=True)
    for metric, val in agent_summary.items():
        print(f"{metric:<35}: {val}", flush=True)

    return agent_summary


def main():
    cases_path = "data/eval/golden_procurement_cases.json"
    if not os.path.exists(cases_path):
        raise FileNotFoundError(f"Missing {cases_path}")

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    retriever = HybridSupplierRetriever()

    retrieval_results = run_retrieval_benchmarks(cases, retriever)
    agent_results = run_agent_decision_benchmarks(cases)

    full_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_evaluated_cases": len(cases),
        "retrieval_benchmarks": retrieval_results,
        "agent_decision_benchmarks": agent_results
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/eval_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

    print("\nBenchmark report successfully exported to 'docs/eval_benchmark_results.json'!")


if __name__ == "__main__":
    main()
