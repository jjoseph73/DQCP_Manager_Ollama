"""
ChromaDB vector store wrapper for the DQCP knowledge base.
"""
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


class VectorStore:
    def __init__(self, config: dict):
        self._config = config
        kn = config["knowledge"]
        self._chroma_path = kn["chroma_path"]
        self._collection_name = kn["collection_name"]
        self._embedding_model_name = kn["embedding_model"]
        self._top_k = kn.get("top_k_results", 5)

        Path(self._chroma_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._chroma_path)
        self._model = SentenceTransformer(self._embedding_model_name)
        self._collection = self.get_or_create_collection()

    def get_or_create_collection(self) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[dict]) -> None:
        """
        Add text chunks to the collection.

        Each chunk must have: text, metadata (dict), id (str).
        """
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = self._model.encode(texts, show_progress_bar=False).tolist()
        self._collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[c["metadata"] for c in chunks],
        )

    def delete_by_source(self, source_file: str) -> None:
        """Delete all chunks where metadata.source_file == source_file."""
        results = self._collection.get(
            where={"source_file": source_file},
            include=["metadatas"],
        )
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)

    def query(
        self, question: str, top_k: int = None, doc_type_filter: str = None
    ) -> list[dict]:
        """Retrieve top-k similar chunks for a question."""
        k = top_k or self._top_k
        embedding = self._model.encode([question], show_progress_bar=False).tolist()

        where = None
        if doc_type_filter and doc_type_filter.lower() not in ("", "all"):
            where = {"doc_type": doc_type_filter}

        query_kwargs = dict(
            query_embeddings=embedding,
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            query_kwargs["where"] = where

        results = self._collection.query(**query_kwargs)

        chunks = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, distances):
            chunks.append({"text": doc, "metadata": meta, "distance": dist})
        return chunks

    def list_sources(self) -> list[dict]:
        """Return a list of unique sources with chunk counts and metadata."""
        results = self._collection.get(include=["metadatas"])
        metas = results.get("metadatas", [])

        source_map: dict[str, dict] = {}
        for meta in metas:
            src = meta.get("source_file", "unknown")
            if src not in source_map:
                source_map[src] = {
                    "source_file": src,
                    "doc_type": meta.get("doc_type", "unknown"),
                    "ingested_at": meta.get("ingested_at", ""),
                    "chunk_count": 0,
                }
            source_map[src]["chunk_count"] += 1

        return list(source_map.values())

    def get_stats(self) -> dict:
        """Return aggregate stats: total chunks, unique sources, doc types."""
        sources = self.list_sources()
        total_chunks = sum(s["chunk_count"] for s in sources)
        doc_types = list({s["doc_type"] for s in sources})
        return {
            "total_chunks": total_chunks,
            "unique_sources": len(sources),
            "doc_types": doc_types,
        }
