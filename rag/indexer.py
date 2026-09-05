import os
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from rag.document_loaders import load_all_supplier_documents
from rag.embeddings import get_embedding_model

CHROMA_DIR = "./data/chroma_db"
CONTRACTS_DIR = "./data/raw/supplier_contracts"
COLLECTION_NAME = "supplier_agreements"

def build_vector_store() -> Chroma:
    print(f"Loading files from '{CONTRACTS_DIR}'...")
    raw_documents = load_all_supplier_documents(CONTRACTS_DIR)
    if not raw_documents:
        raise FileNotFoundError(f"No .pdf or .md files found in {CONTRACTS_DIR}")

    # Chunking: keeps entire SKU tables and policy clauses together
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "]
    )
    chunks = text_splitter.split_documents(raw_documents)
    print(f"Generated {len(chunks)} text chunks across {len(raw_documents)} loaded pages/files.")

    embeddings = get_embedding_model()

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR
    )

    # Clean rebuild
    existing = vectorstore.get()
    if existing and existing.get("ids"):
        print(f"Clearing {len(existing['ids'])} existing entries from '{COLLECTION_NAME}' collection...")
        vectorstore.delete(ids=existing["ids"])

    print("Embedding chunks via Mistral ('mistral-embed') and indexing into ChromaDB...")
    vectorstore.add_documents(chunks)
    print(f"ChromaDB persistent store updated successfully at '{CHROMA_DIR}'.")
    return vectorstore

# Alias so app.main can import it
index_procurement_documents = build_vector_store

if __name__ == "__main__":
    build_vector_store()