import os
import pytest
from rag.hybrid_retriever import HybridSupplierRetriever

@pytest.fixture(scope="module")
def retriever():
    return HybridSupplierRetriever()

def test_sku_exact_retrieval(retriever):
    """Verifies BM25 retrieves exact SKU pricing specifications."""
    results = retriever.retrieve("What is the MOQ and pricing tiers for SKU-1001?")
    assert len(results) > 0
    combined_text = " ".join([d.page_content for d in results])
    assert "SKU-1001" in combined_text
    assert "Optical Sensor" in combined_text

def test_policy_conceptual_retrieval(retriever):
    """Verifies semantic embeddings retrieve internal procurement limits."""
    results = retriever.retrieve("What is the maximum dollar limit for autonomous purchase orders?")
    assert len(results) > 0
    combined_text = " ".join([d.page_content for d in results])
    assert "$5,000" in combined_text or "5,000" in combined_text

def test_vendor_metadata_filter(retriever):
    """Verifies supplier-specific metadata filtering."""
    results = retriever.retrieve(
        query="What are the late delivery penalties?",
        supplier_id="VEND-001"
    )
    assert len(results) > 0
    for doc in results:
        assert doc.metadata.get("supplier_id") == "VEND-001"