import os
import re
from typing import List, Optional, Dict
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from langchain_core.documents import Document
from rag.embeddings import get_embedding_model

class HybridSupplierRetriever:
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        if not os.path.exists(persist_directory):
            raise RuntimeError(
                f"Chroma directory '{persist_directory}' does not exist. "
                "Run `python -m rag.indexer` first to generate the index."
            )
            
        self.embeddings = get_embedding_model()
        self.vectorstore = Chroma(
            collection_name="supplier_agreements",
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )
        
        db_data = self.vectorstore.get()
        all_docs = [
            Document(page_content=text, metadata=meta)
            for text, meta in zip(db_data["documents"], db_data["metadatas"])
        ]
        
        if not all_docs:
            raise ValueError("No records found inside Chroma collection 'supplier_agreements'.")

        self.bm25_retriever = BM25Retriever.from_documents(all_docs)

    def _reciprocal_rank_fusion(
        self,
        bm25_docs: List[Document],
        dense_docs: List[Document],
        weights: tuple = (0.35, 0.65),
        c: int = 60
    ) -> List[Document]:
        bm25_weight, dense_weight = weights
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        for rank, doc in enumerate(bm25_docs):
            key = doc.page_content
            doc_map[key] = doc
            doc_scores[key] = doc_scores.get(key, 0.0) + bm25_weight * (1 / (rank + c))

        for rank, doc in enumerate(dense_docs):
            key = doc.page_content
            doc_map[key] = doc
            doc_scores[key] = doc_scores.get(key, 0.0) + dense_weight * (1 / (rank + c))

        sorted_keys = sorted(doc_scores.keys(), key=lambda k: doc_scores[k], reverse=True)
        return [doc_map[k] for k in sorted_keys]

    def retrieve(self, query: str, supplier_id: Optional[str] = None, top_k: int = 4) -> List[Document]:
        if supplier_id:
            dense_retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": top_k * 2, "filter": {"supplier_id": supplier_id}}
            )
            return dense_retriever.invoke(query)[:top_k]
        
        dense_retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k * 2})
        dense_docs = dense_retriever.invoke(query)

        # Preprocess BM25 query: isolate high-entropy alphanumeric tokens (e.g. SKU-1003) to eliminate stopword noise
        sku_matches = re.findall(r"SKU-\d{4}", query)
        bm25_query = f"{sku_matches[0]} pricing tiers MOQ lead time" if sku_matches else query

        self.bm25_retriever.k = top_k * 2
        bm25_docs = self.bm25_retriever.invoke(bm25_query)

        fused_docs = self._reciprocal_rank_fusion(bm25_docs, dense_docs, weights=(0.35, 0.65))
        return fused_docs[:top_k]