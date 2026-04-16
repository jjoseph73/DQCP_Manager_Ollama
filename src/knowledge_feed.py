"""
Knowledge base ingestion — loads documents and inserts chunks into ChromaDB.
"""
import shutil
from datetime import datetime, timezone
from pathlib import Path

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.vector_store import VectorStore

TMP_DIR = Path("/tmp/dqcp_ingestion")

EXTENSION_MAP = {
    ".pdf": ("pdf", PyPDFLoader),
    ".docx": ("doc", Docx2txtLoader),
    ".md": ("doc", TextLoader),
    ".txt": ("doc", TextLoader),
    ".sql": ("sql", TextLoader),
    ".py": ("code", TextLoader),
}


def ingest_documents(uploaded_files: list, config: dict, vector_store: VectorStore) -> dict:
    """
    Ingest a list of uploaded Streamlit file objects into ChromaDB.

    Returns per-file summary: {filename: {chunks_added, chunks_replaced, doc_type, status}}
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    kn = config["knowledge"]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=kn["chunk_size"],
        chunk_overlap=kn["chunk_overlap"],
    )

    summary = {}

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        suffix = Path(filename).suffix.lower()

        if suffix not in EXTENSION_MAP:
            summary[filename] = {
                "chunks_added": 0,
                "chunks_replaced": 0,
                "doc_type": "unknown",
                "status": f"Unsupported file type: {suffix}",
            }
            continue

        doc_type, LoaderClass = EXTENSION_MAP[suffix]
        tmp_path = TMP_DIR / filename

        try:
            # Save uploaded bytes to temp file
            tmp_path.write_bytes(uploaded_file.read())

            # Load documents
            if suffix in (".sql", ".py"):
                loader = LoaderClass(str(tmp_path), encoding="utf-8", autodetect_encoding=True)
            elif suffix == ".txt" or suffix == ".md":
                loader = LoaderClass(str(tmp_path), encoding="utf-8", autodetect_encoding=True)
            else:
                loader = LoaderClass(str(tmp_path))

            documents = loader.load()
            chunks_doc = splitter.split_documents(documents)

            ingested_at = datetime.now(timezone.utc).isoformat()

            # Delete existing chunks for this source
            existing = vector_store.list_sources()
            replaced = next(
                (s["chunk_count"] for s in existing if s["source_file"] == filename), 0
            )
            if replaced:
                vector_store.delete_by_source(filename)

            # Build chunk dicts
            chunks = []
            for i, doc in enumerate(chunks_doc):
                chunks.append({
                    "id": f"{filename}::chunk::{i}",
                    "text": doc.page_content,
                    "metadata": {
                        "source_file": filename,
                        "doc_type": doc_type,
                        "ingested_at": ingested_at,
                        "chunk_index": i,
                    },
                })

            vector_store.add_chunks(chunks)

            summary[filename] = {
                "chunks_added": len(chunks),
                "chunks_replaced": replaced,
                "doc_type": doc_type,
                "status": "success",
            }

        except Exception as e:
            summary[filename] = {
                "chunks_added": 0,
                "chunks_replaced": 0,
                "doc_type": doc_type,
                "status": f"Error: {e}",
            }
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return summary
