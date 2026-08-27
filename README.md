# AutoStock-AI: Autonomous Inventory Replenishment & Supplier Negotiation

## AutoStock-AI is an end-to-end agentic supply-chain intelligence system. It monitors live warehouse stock levels, detects impending stockouts, cross-references multi-vendor contracts and SLA policies using Hybrid RAG, and utilizes a fine-tuned, domain-specific Large Language Model to draft and validate deterministic Purchase Orders (POs) within enterprise governance constraints.

## 1. Project Setup

### Environment Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## 2. Dataset gathering and Fine-tuning Llama 3.2 model

### Fine-Tuning Progress & Milestones

Fine-tuning has shifted from resource-intensive full-parameter updates to lightweight, modular, and compute-efficient adaptation across language and vision models:

- **Parameter-Efficient Fine-Tuning (PEFT):** Methods like **LoRA** and **QLoRA** enable domain adaptation on standard hardware. Freezing core weights and training low-rank adapter matrices cuts VRAM usage by over 70% with minimal loss in task accuracy.
- **Preference Optimization:** Complex RLHF pipelines have largely transitioned to direct objective methods like **DPO (Direct Preference Optimization)** and **ORPO**, simplifying task alignment, safety steering, and style control without dedicated reward models.
- **Multimodal Integration:** Adapter-based fine-tuning efficiently aligns vision encoders with language backbones, enabling specialized capabilities such as visual reasoning, dial/gauge reading, and structured document extraction.
- **Curated & Synthetic Instruction Tuning:** Focus has moved from data volume to data quality. Distillation and filtered synthetic datasets allow compact models to match much larger baselines on specialized reasoning tasks.

Fine-tuning now prioritizes targeted edge deployment, low latency, and rapid adapter switching over costly full-model retraining.

## 3. Gathering Knowledge-base and Establishing the RAG pipeline.

### RAG Pipeline Summary

Implemented a production-grade Hybrid Retrieval-Augmented Generation (RAG) system designed to evaluate supplier agreements, pricing tiers, and internal procurement policies deterministically[cite: 1, 5].

### Core Architecture & Workflow

- **Multi-Format Ingestion:** Standardizes PDF contracts via PyMuPDF and Markdown policy files, automatically extracting alphanumeric product codes (`\bSKU-\d{4}\b`) and tagging metadata (`supplier_id`, `document_type`, `skus`)[cite: 5].
- **Section-Aware Chunking:** Uses `RecursiveCharacterTextSplitter` (1,200 characters, 200 overlap) with section boundaries to keep full pricing tables and legal clauses intact[cite: 5].
- **Persistent Vector Index:** Converts chunks into 1,024-dimensional dense vectors using Mistral's `mistral-embed` endpoint and persists them locally in ChromaDB (`supplier_agreements` collection).
- **Hybrid Retrieval & RRF:** Merges sparse **BM25 keyword search** (60% weight for exact SKU matching) and **dense semantic search** (40% weight for policy context) via custom Reciprocal Rank Fusion ($c=60$) alongside optional vendor-level metadata filtering[cite: 1, 4].

### Validation

Verified through automated `pytest` test suites, confirming high recall on exact SKU queries (`SKU-1001`), conceptual policy limits ($5,000 threshold), and vendor-scoped lookups[cite: 1, 4].

## 4. Establishing the Agentic Pipeline & API Summary

AutoStock-AI features an autonomous, multi-agent procurement and inventory replenishment system built on a cyclic **LangGraph** state machine and exposed via **FastAPI** with interactive **Swagger UI** documentation.

### Core Agent Pipeline

1. **Inventory Surveillance (`inventory_monitor`)**: Scans SQLite warehouse stock, computes real-time runway days, and flags/prioritizes critical stockout risks.
2. **Context Aggregation (`supplier_matcher`)**: Queries hybrid RAG retrieval layers to fetch vendor contract terms, MOQs, lead times, and organizational spending rules.
3. **Reasoning & PO Generation (`po_generator`)**: Integrates a locally fine-tuned model served via vLLM to evaluate vendor constraints, apply lead-time overrides for critical items, and output valid JSON purchase order drafts.
4. **Policy Enforcement Gate (`human_review`)**: Evaluates financial compliance, auto-executing eligible orders while routing transactions exceeding the $5,000 threshold to a persistent `pending_review` queue.

### FastAPI & Swagger Integration

The compiled workflow is deployed as a RESTful service exposing key operational endpoints:

- `GET /health`: Validates system uptime and engine readiness.
- `POST /trigger-replenishment`: Executes the end-to-end multi-agent replenishment loop on demand.
- `POST /approve-po`: Enables Human-in-the-Loop (HITL) resolution to approve, modify, or reject pending orders.
- `GET /docs`: Interactive Swagger interface for live payload testing and workflow inspection.

## 5. Project Directory Structure

```text
autostock-ai/
├── data/
│   ├── raw/
│   │   ├── procurement_clean_unique.jsonl    # Master unstructured dataset for LLM training
│   │   └── supplier_contracts/               # PDF & Markdown agreements and SLAs
│   │       ├── internal_procurement_policy.md
│   │       ├── vendor_techcorp_pricing_sla.md
│   │       ├── vendor_globalparts_pricing_sla.md
│   │       ├── vendor_apex_pricing_sla.md
│   │       ├── vendor_techcorp_msa.pdf
│   │       ├── vendor_globalparts_pricing.pdf
│   │       └── vendor_apex_sla.pdf
│   ├── finetune/
│   │   ├── train.jsonl                       # Training split (90%)
│   │   └── val.jsonl                         # Validation split (10%)
│   ├── mock_db/
│   │   ├── schema.sql                        # SQLite DDL for inventory, vendors, and catalog
│   │   ├── seed_data.sql                     # Seed records (10 SKUs, 3 vendors, 20 catalog rows)
│   │   └── warehouse.db                      # Generated SQLite database
│   └── chroma_db/                            # Persistent ChromaDB vector index
│
├── finetuning/
│   ├── dataset_generator/
│   │   └── split_dataset.py                  # Seeded train/val split script
│   ├── train.py                              # Unsloth QLoRA fine-tuning & 16-bit merge script
│   └── evaluate.py                           # Pydantic schema validation & arithmetic check script
│
├── models/                                   # Git-ignored model artifacts
│   ├── adapters/                             # LoRA weights & adapter configurations
│   └── merged_16bit/                         # Merged standalone safetensors weights
│
├── rag/
│   ├── __init__.py                           # Exported modules
│   ├── document_loaders.py                   # Ingestion pipeline for .pdf (PyMuPDF) and .md
│   ├── embeddings.py                         # Mistral AI embeddings interface (mistral-embed)
│   ├── indexer.py                            # Section-preserving chunker and ChromaDB indexer
│   └── hybrid_retriever.py                   # Reciprocal Rank Fusion (BM25 + Dense) retriever
│
├── agents/
│   ├── __init__.py
│   ├── state.py                              # LangGraph TypedDict state definitions
│   ├── graph.py                              # State graph workflow compilation & routing
│   ├── nodes/
│   │   ├── inventory_monitor.py              # Scans DB for reorder triggers (Current Stock <= ROP)
│   │   ├── supplier_matcher.py               # Evaluates RAG supplier pricing & SLA terms
│   │   ├── po_generator.py                   # Executes fine-tuned model for structured PO drafting
│   │   └── human_review.py                   # Approval pause gate for orders > $5,000
│   └── tools/
│       ├── erp_sql_tool.py                   # Deterministic SQL inventory/catalog queries
│       └── math_engine.py                    # Margin & total purchase value validator
│
├── tests/
│   ├── test_rag_retrieval.py                 # Hybrid retrieval precision & filter unit tests
│   └── test_agent_graph.py                   # End-to-end LangGraph state machine execution tests
│
└── generate_sample_contracts.py              # ReportLab synthetic PDF generator
```
