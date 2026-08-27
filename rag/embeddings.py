import os
from langchain_mistralai import MistralAIEmbeddings

def get_embedding_model() -> MistralAIEmbeddings:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError(
            "Environment variable MISTRAL_API_KEY is not set. "
            "Set it via `$env:MISTRAL_API_KEY='your_key'` in PowerShell."
        )
    return MistralAIEmbeddings(model="mistral-embed", api_key=api_key)