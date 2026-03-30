"""
Retriever: Load FAISS vectorstore and return configured retriever.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"

# Same embedding model used in ingest.py
EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)


def load_retriever(k: int = 6):
    """
    Load the FAISS vectorstore from disk and return a retriever.

    Args:
        k: Number of top-similar chunks to return per query. Default 6.

    Returns:
        LangChain retriever instance.
    """
    if not (VECTORSTORE_DIR / "index.faiss").exists():
        raise FileNotFoundError(
            f"Vectorstore not found at {VECTORSTORE_DIR}. "
            "Run `python src/ingest.py` first."
        )

    vectorstore = FAISS.load_local(
        str(VECTORSTORE_DIR),
        EMBEDDINGS,
        allow_dangerous_deserialization=True,
    )

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )

    return retriever


if __name__ == "__main__":
    # Quick smoke test
    retriever = load_retriever()
    results = retriever.invoke("perishable item return policy")
    print(f"✅ Retriever loaded. Sample query returned {len(results)} chunks:\n")
    for doc in results:
        meta = doc.metadata
        print(f"  [{meta['doc_id']} > {meta['section']}]: {doc.page_content[:80]}…")
