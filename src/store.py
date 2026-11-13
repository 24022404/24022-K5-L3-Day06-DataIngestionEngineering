"""Step 3: embeddings (local Sentence Transformers) + persistent Chroma vector store."""
from __future__ import annotations

import hashlib

import chromadb

from config import CHROMA_DIR, EMBED_MODEL


class Embedder:
    """Real semantic embeddings. If the model cannot load we fail loudly (no mock fallback)."""

    def __init__(self, model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> list[list[float]]:
        # Same processing for documents and queries: no prefix, L2-normalized.
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                 show_progress_bar=False)
        return vecs.tolist()


def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client, name: str):
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"},
                                           embedding_function=None)


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def upsert_chunks(col, chunks: list[dict], vectors: list[list[float]]) -> dict:
    """Idempotent load: deterministic IDs + upsert, so re-loading the same version never
    duplicates. IDs that no longer exist in the new chunk set (document changed) are deleted."""
    ids = [c["id"] for c in chunks]
    metas = [{**c["metadata"], "text_hash": text_hash(c["text"])} for c in chunks]
    before = col.count()
    for i in range(0, len(ids), 500):
        col.upsert(ids=ids[i:i + 500], documents=[c["text"] for c in chunks[i:i + 500]],
                   embeddings=vectors[i:i + 500], metadatas=metas[i:i + 500])
    stale = sorted(set(col.get(include=[])["ids"]) - set(ids))
    if stale:
        col.delete(ids=stale)
    return {"count_before": before, "count_after": col.count(), "stale_deleted": len(stale)}


def query(col, vector: list[float], k: int, where: dict | None = None) -> list[dict]:
    res = col.query(query_embeddings=[vector], n_results=k, where=where,
                    include=["documents", "metadatas", "distances"])
    return [{"id": i, "text": d, "metadata": m, "score": round(1 - dist, 4)}
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0],
                                     res["metadatas"][0], res["distances"][0])]
