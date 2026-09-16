"""
Stage 2: given an invoice, retrieve its matching PO and the relevant contract clauses.

In-memory, numpy-based vector index — no external vector DB dependency. This was
swapped in for chromadb, which had a real Python 3.14 compatibility problem at
build time (it depended on a Pydantic v1 shim internally that breaks on 3.14),
and dependency-install risk is exactly the kind of thing you don't want to be
debugging the night before a hackathon submission deadline.

For a single-session demo, an in-memory list is genuinely sufficient — no
persistence, no server, no extra install surface. If you take this past the
hackathon and need multi-session persistence or scale beyond what fits in
memory, swap this for a real vector DB (chromadb once its 3.14 support has
settled, pgvector, Qdrant) — the index_document()/find_matching_context()
interface below is intentionally the only thing callers depend on, so that
swap stays contained to this one file.
"""
import numpy as np
from openai import OpenAI

from app.config import settings
from app.models.schemas import ExtractedDocument

# Each entry: id, embedding, text, document_id, document_type, vendor_name.
# A list is fine at hackathon scale (dozens to low hundreds of chunks) — this
# is a linear scan, not an ANN index. Replace with a real vector DB before
# this needs to hold more than a few thousand chunks.
_index: list[dict] = []

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    # Lazy-loaded, same pattern as token_factory_client.py — importing this
    # module should never require an API key to already be configured.
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)
    return _client


def _embed(texts: list[str]) -> list[np.ndarray]:
    response = _get_client().embeddings.create(
        model=settings.nebius_embedding_model, input=texts
    )
    return [np.array(item.embedding, dtype=np.float32) for item in response.data]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def index_document(document: ExtractedDocument) -> None:
    """Add a document's chunks to the index, tagged with metadata so retrieval
    can filter by document type (only search contracts/POs, not invoices).
    """
    chunks = _chunk_text(document.raw_text)
    if not chunks:
        return
    embeddings = _embed(chunks)
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        _index.append(
            {
                "id": f"{document.document_id}::{i}",
                "embedding": embedding,
                "text": chunk,
                "document_id": document.document_id,
                "document_type": document.document_type.value,
                "vendor_name": document.vendor_name or "",
            }
        )


def find_matching_context(
    invoice: ExtractedDocument, top_k: int = 5
) -> dict[str, list[str]]:
    """Retrieve the most relevant PO and contract chunks for a given invoice.

    Matching is done by semantic similarity of vendor name + line items rather
    than requiring exact document-number matches — real AP data is messy (PO
    numbers get mistyped, contracts get renamed), so this is more robust than
    a strict key lookup.
    """
    query = (
        f"Vendor: {invoice.vendor_name}. "
        f"Line items: {', '.join(li.description for li in invoice.line_items)}"
    )
    query_embedding = _embed([query])[0]

    po_hits = _search(query_embedding, document_type="purchase_order", top_k=top_k)
    contract_hits = _search(query_embedding, document_type="contract", top_k=top_k)

    return {
        "po_chunks": [hit["text"] for hit in po_hits],
        "contract_chunks": [hit["text"] for hit in contract_hits],
    }


def _search(query_embedding: np.ndarray, document_type: str, top_k: int) -> list[dict]:
    candidates = [entry for entry in _index if entry["document_type"] == document_type]
    scored = [
        (entry, _cosine_similarity(query_embedding, entry["embedding"]))
        for entry in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [entry for entry, _score in scored[:top_k]]


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple sliding-window chunker. Good enough for hackathon-scale documents;
    swap for a semantic/section-aware chunker if you have time in week 3.
    """
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks