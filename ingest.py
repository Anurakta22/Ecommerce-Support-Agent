"""
Ingestion pipeline: Load policy docs → chunk → embed → save FAISS index.

Run: python src/ingest.py
"""
import os
import re
import sys

from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
POLICIES_DIR = ROOT_DIR / "policies"
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"

# ── Embedding model ────────────────────────────────────────────────────────
EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter from a markdown string.
    Returns (metadata_dict, body_without_frontmatter).
    """
    metadata = {}
    body = text

    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    match = pattern.match(text)
    if match:
        fm_block = match.group(1)
        body = text[match.end():]
        for line in fm_block.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip()

    return metadata, body


def load_and_chunk_policies() -> list[Document]:
    """
    Load all .md files, parse frontmatter, split on ## headers,
    then apply secondary RecursiveCharacterTextSplitter.
    """
    md_files = list(POLICIES_DIR.glob("*.md"))
    if not md_files:
        print(f"❌ No .md files found in {POLICIES_DIR}")
        sys.exit(1)

    # Primary splitter: on ## headers
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("##", "section")],
        strip_headers=False,
    )

    # Secondary splitter: handle oversized sections
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        length_function=len,
    )

    all_chunks: list[Document] = []

    for md_file in sorted(md_files):
        raw_text = md_file.read_text(encoding="utf-8")

        # Parse frontmatter
        fm, body = parse_frontmatter(raw_text)
        doc_id = fm.get("doc_id", md_file.stem)
        title = fm.get("title", md_file.stem)
        category = fm.get("category", "unknown")
        region = fm.get("region", "global")

        # Primary split on ## headers
        header_chunks = header_splitter.split_text(body)

        # Secondary split + attach metadata
        for chunk in header_chunks:
            section_name = chunk.metadata.get("section", "Overview")

            sub_chunks = char_splitter.split_text(chunk.page_content)
            for sub in sub_chunks:
                all_chunks.append(
                    Document(
                        page_content=sub,
                        metadata={
                            "doc_id": doc_id,
                            "title": title,
                            "section": section_name,
                            "category": category,
                            "region": region,
                            "source": str(md_file.name),
                        },
                    )
                )

    return all_chunks


def build_vectorstore(chunks: list[Document]) -> None:
    """Embed chunks and save FAISS index to disk."""
    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📦 Embedding {len(chunks)} chunks …")
    vectorstore = FAISS.from_documents(chunks, EMBEDDINGS)
    vectorstore.save_local(str(VECTORSTORE_DIR))
    print(f"✅ Indexed {len(chunks)} chunks into vectorstore/")


def main():
    print(f"📂 Loading policies from: {POLICIES_DIR}")
    chunks = load_and_chunk_policies()

    if not chunks:
        print("❌ No chunks produced. Check policy file content.")
        sys.exit(1)

    # Show sample chunk for verification
    sample = chunks[0]
    print("\n── Sample chunk ──────────────────────────────")
    print(f"  doc_id  : {sample.metadata['doc_id']}")
    print(f"  section : {sample.metadata['section']}")
    print(f"  category: {sample.metadata['category']}")
    print(f"  region  : {sample.metadata['region']}")
    print(f"  content : {sample.page_content[:120]}…")
    print("──────────────────────────────────────────────\n")

    build_vectorstore(chunks)


if __name__ == "__main__":
    main()
