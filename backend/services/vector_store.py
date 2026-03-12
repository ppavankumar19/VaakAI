import os
from pathlib import Path

import chromadb

_chroma_client: chromadb.PersistentClient | None = None


def _get_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
    return _chroma_client


def _collection_name(session_id: str) -> str:
    # ChromaDB collection names: alphanumeric + underscores, max 63 chars
    return "s_" + session_id.replace("-", "")[:32]


def embed_chunks(session_id: str, chunks: list) -> None:
    """
    Store transcript chunks in ChromaDB for RAG Q&A (P2 feature).
    chunks: list of {text, start_ms, end_ms, chunk_index}
    """
    if not chunks:
        return

    client = _get_client()
    collection = client.get_or_create_collection(name=_collection_name(session_id))

    ids = [f"{session_id}_{c['chunk_index']}" for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {"session_id": session_id, "start_ms": c["start_ms"], "end_ms": c["end_ms"]}
        for c in chunks
    ]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)


def search(session_id: str, query: str, n_results: int = 5) -> list:
    """
    Retrieve the top-n most relevant transcript chunks for a query.
    Returns list of {text, start_ms, end_ms}.
    """
    client = _get_client()

    try:
        collection = client.get_collection(name=_collection_name(session_id))
    except Exception:
        return []

    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    return [
        {
            "text": doc,
            "start_ms": meta.get("start_ms", 0),
            "end_ms": meta.get("end_ms", 0),
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]
