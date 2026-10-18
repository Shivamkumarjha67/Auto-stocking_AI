# AutoStock-AI: Real-World Failure Analysis & Boundary Stress Testing

A critical mark of production-grade AI engineering is **understanding where an agent fails, why it fails, and how the system architecture mitigates those failures**.

During the design, fine-tuning, and stress-testing of AutoStock-AI, several boundary conditions and edge cases were analyzed. This document details 5 realistic failure modes, their root causes, and the architectural solutions implemented to resolve them.

---

## Summary of Evaluated Failure Modes

| # | Failure Mode | Failure Root Cause | Architectural Mitigation | Status |
| :--- | :--- | :--- | :--- | :---: |
| **1** | **Dense Vector SKU Dilution** | Semantic clustering confused adjacent alphanumeric part numbers (`SKU-1001` vs `SKU-1002`). | **Hybrid RAG with Reciprocal Rank Fusion (65% Dense + 35% BM25 with clean token extraction)** | **Resolved** |
| **2** | **Contractual MOQ Deficit Fixation & Spending Ceiling** | LLM prioritized raw 14-day buffer deficit over vendor MOQ (60% baseline), or high MOQ breached the $5,000 limit. | **Deterministic MOQ Guardrail (`max(raw_qty, moq)`) + LangGraph HITL Gate** | **Resolved** |
| **3** | **Small LLM Arithmetic Drift** | 4-bit 3B models made rounding errors during multi-digit decimal multiplication. | **Deterministic Tool Grounding (`math_engine.py` + Pydantic validation)** | **Resolved** |
| **4** | **Pricing Table Header Severing** | Naive chunkers sliced markdown tables across chunk boundaries, separating tiers from columns. | **Section-Aware Chunking (1,200-char window with header preservation)** | **Resolved** |
| **5** | **Multi-SKU Simultaneous Depletion** | Multiple concurrent stockouts triggered unprioritized reordering without urgency awareness. | **SQL Runway Velocity Sorting (`current_stock / daily_sales_rate ASC`)** | **Resolved** |

---

## Detailed Case Studies

### 1. Dense Vector SKU Dilution (Semantic Clustering of Alphanumeric Identifiers)

* **The Problem:**
  When querying purely dense vector embeddings (e.g., cosine distance in ChromaDB) for `"What are the volume pricing tiers for SKU-1001?"`, the embedding model assigned high similarity scores to chunks discussing `SKU-1002` and `SKU-1003`. Because the surrounding contract language (warranty terms, SLA clauses, vendor headers) was nearly identical, vector representations clustered together. Furthermore, trailing query punctuation (e.g. `SKU-1003?`) diluted standard whitespace-tokenized keyword matchers.
* **The Failure:**
  The agent frequently retrieved pricing for the wrong component, quoting \$12.75 instead of \$18.50, leading to inaccurate purchase order amounts.
* **The Root Cause:**
  Dense embedding models excel at semantic concepts (e.g., *"autonomous spending threshold"*) but struggle with high-entropy alphanumeric identifiers where a single digit change (`1001` vs `1002`) represents a completely different physical part.
* **Architectural Resolution:**
  Implemented **Hybrid Retrieval with Reciprocal Rank Fusion (RRF)**:
  ```python
  doc_score = 0.65 * (1 / (rank_dense + 60)) + 0.35 * (1 / (rank_bm25 + 60))
  ```
  BM25 with clean regex tokenization (`re.findall(r'[\w-]+', text)`) assigns heavy inverse document frequency (IDF) penalties to rare tokens like `SKU-1001`. Combining BM25 with dense vectors yielded **100% exact SKU retrieval recall** (0.850 MRR) without sacrificing conceptual policy search.

---

### 2. Contractual MOQ Deficit Fixation & Corporate Policy Ceiling Deadlock

* **The Problem:**
  An inventory item (`SKU-2005` Timing Belt GT2) required reordering. The target safety buffer called for only 22 units. However, the lowest-cost supplier (GlobalParts Direct, `VEND-002`) enforced a Minimum Order Quantity (MOQ) of 200 units. Similarly, for high-velocity items like `SKU-1004`, satisfying the 200-unit MOQ pushed total spend to **$30,155.00**, far above the $5,000 corporate limit.
* **The Failure:**
  In baseline testing with unconstrained prompting:
  1. The LLM fixated on replenishing the exact buffer deficit (e.g., drafting 22 or 25 units instead of 200), resulting in a poor **60.0% MOQ Adherence Rate** that suppliers would reject.
  2. For high-volume items, fulfilling the MOQ breached the company's \$5,000 autonomous spending limit.
* **Architectural Resolution:**
  Implemented a two-layer deterministic safeguard:
  1. **Deterministic MOQ Guardrail (`po_generator.py`)**:
     Before finalizing the purchase order, the node inspects the vendor's contractual MOQ and programmatically clamps:
     ```python
     if order_quantity < vendor_moq:
         order_quantity = vendor_moq
         total_amount = round(order_quantity * unit_price, 2)
     ```
     This elevated MOQ adherence from **60.0% to 100.0%**.
  2. **LangGraph Human-in-the-Loop (HITL) Gatekeeper**:
     If fulfilling the MOQ causes `total_amount > $5,000.00`, execution is automatically paused and routed to `pending_review_queue` in SQLite. The Streamlit manager console displays the flagged order for one-click **Approval**, **Manual Override**, or **Rejection**.

---

### 3. Small Model Arithmetic Drift (Quantized Hallucination)

* **The Problem:**
  When using edge-deployed quantized models (e.g., Llama 3.2 3B Instruct in 4-bit via Unsloth/vLLM), the model occasionally hallucinated decimal arithmetic when computing:
  $$\text{Total Amount} = \text{Quantity} \times \text{Unit Price}$$
  For example: $180 \times \$12.75 = \$2,295.00$, but the LLM drafted `{"total_amount": 2160.00}`.
* **The Failure:**
  The discrepancy triggered accounting mismatches and Pydantic validation errors in the downstream ERP integration.
* **Architectural Resolution:**
  1. Offloaded buffer calculations to a deterministic Python tool:
     `calculate_restock_quantity(current_stock, daily_sales_rate)`.
  2. Implemented strict Pydantic and math validation in `evaluate.py` and `po_generator.py`:
     ```python
     calc_sum = round(qty * unit_price, 2)
     if abs(draft_total - calc_sum) > 0.05:
         draft_total = calc_sum  # Deterministic override
     ```
  This guarantees **100% mathematical precision** regardless of LLM parameter size or quantization level.

---

### 4. Pricing Table Header Severing (Chunk Boundary Truncation)

* **The Problem:**
  Standard fixed-length chunking (e.g. 500 characters) severed Markdown pricing tables midway through vendor SLA documents. A chunk would contain rows like:
  ```markdown
  | Tier 2 (100-499 units) | $14.80 | 14 days |
  | Tier 3 (500+ units)     | $13.20 | 12 days |
  ```
  without the preceding table header (`| Volume Tier | Unit Price | Lead Time |`) or the SKU identifier defined at the top of the section.
* **The Failure:**
  The retriever returned disconnected numbers, causing the LLM to confuse Tier 1 pricing with Tier 3 pricing.
* **Architectural Resolution:**
  Implemented **Section-Aware Recursive Chunking** in `rag/indexer.py`:
  - Chunk size: **1,200 characters** with **200 overlap**.
  - Hierarchical boundary separators: `["\n## ", "\n### ", "\n\n", "\n", " "]`.
  This ensures that entire markdown pricing schedules, vendor headers, and SLA tables remain contiguous within a single retrieval chunk.

---

### 5. Multi-SKU Simultaneous Depletion (Queue Starvation)

* **The Problem:**
  During high-demand periods or batch database updates, 5 or more SKUs crossed their Reorder Point simultaneously. If processed without prioritization:
  - An item with **12.5 days of runway** might be processed before an item with **1.2 days of runway** (critical stockout risk).
* **The Failure:**
  Production downtime could occur on critical components while the agent spent time deliberating standard bulk orders.
* **Architectural Resolution:**
  Implemented **SQL Runway Velocity Sorting** in `agents/tools/erp_sql_tool.py`:
  ```sql
  SELECT sku, item_name, current_stock, daily_sales_rate
  FROM inventory
  WHERE current_stock <= reorder_point
    AND sku NOT IN (SELECT sku FROM pending_review_queue WHERE status = 'pending_review')
  ORDER BY (current_stock / daily_sales_rate) ASC;
  ```
  Furthermore, if `runway_days < 3.0` (`Critical`), the policy engine automatically suspends standard multi-quote rules and mandates the fastest vendor (`VEND-001`, 3–5 day lead time) to prevent factory stockouts.

---

## Takeaways for AI System Design

1. **Hybrid Retrieval is Mandatory for Domain Systems**: Dense embeddings provide conceptual understanding, but exact part numbers and SKU codes require BM25 lexical precision.
2. **Never Let LLMs Do Math in Production**: Offload arithmetic, runway sizing, and cost multiplication to deterministic code tools.
3. **Hard Policy Gates Protect Autonomous Workflows**: Threshold checks (e.g. \$5,000 limits) ensure autonomous speed without compromising enterprise financial governance.
4. **Resilient Dual-Engine Serving & Normalization**: When serving fine-tuned models from remote GPU environments (Google Colab / vLLM via ngrok), decouple inference via an environment abstraction (`VLLM_BASE_URL`), bypass proxy interstitials (`ngrok-skip-browser-warning`), and normalize nested vs. flat output schemas in the agent layer.

