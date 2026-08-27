# AutoStock-AI: Autonomous Inventory Replenishment & Negotiation

AutoStock-AI is an agentic replenishment engine that monitors stock levels, checks supplier contract constraints via RAG, and uses a fine-tuned domain-specific LLM to draft and validate Purchase Orders (POs).

---

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

## 4. Establishing the Agentic System.
