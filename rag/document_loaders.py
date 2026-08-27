import os
import re
import glob
from typing import List
import pymupdf
from langchain_core.documents import Document

def extract_sku_mentions(text: str) -> List[str]:
    """Extracts SKU patterns like SKU-1001 or SKU-2005."""
    return list(set(re.findall(r"\bSKU-\d{4}\b", text)))

def infer_vendor_id(filename: str) -> str:
    """Derives vendor ID from filename."""
    lower = filename.lower()
    if "techcorp" in lower:
        return "VEND-001"
    if "globalparts" in lower:
        return "VEND-002"
    if "apex" in lower:
        return "VEND-003"
    return "INTERNAL"

def load_supplier_file(file_path: str) -> List[Document]:
    filename = os.path.basename(file_path)
    vendor_id = infer_vendor_id(filename)
    doc_type = "policy" if "policy" in filename.lower() else "pricing_sla"
    documents: List[Document] = []

    # Markdown Loading
    if file_path.endswith(".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            skus = extract_sku_mentions(content)
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": filename,
                        "supplier_id": vendor_id,
                        "document_type": doc_type,
                        "skus": ",".join(skus)
                    }
                )
            )

    # PDF Loading
    elif file_path.endswith(".pdf"):
        doc = pymupdf.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if not text:
                continue
            skus = extract_sku_mentions(text)
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": filename,
                        "supplier_id": vendor_id,
                        "document_type": doc_type,
                        "page": page_num + 1,
                        "skus": ",".join(skus)
                    }
                )
            )
        doc.close()

    return documents

def load_all_supplier_documents(directory: str = "data/raw/supplier_contracts") -> List[Document]:
    all_docs = []
    file_paths = glob.glob(os.path.join(directory, "*.md")) + glob.glob(os.path.join(directory, "*.pdf"))
    for path in file_paths:
        all_docs.extend(load_supplier_file(path))
    return all_docs