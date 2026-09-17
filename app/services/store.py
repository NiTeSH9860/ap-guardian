"""
In-memory store for extracted documents and reconciliation results.

Deliberately simple: a hackathon demo runs for one session against one presenter's
machine, so a persistent database is unnecessary complexity. Swap this for
Postgres/Redis if you take the project further after the hackathon.
"""
from app.models.schemas import ExtractedDocument, ReconciliationResult

_documents: dict[str, ExtractedDocument] = {}
_results: dict[str, ReconciliationResult] = {}


def save_document(document: ExtractedDocument) -> None:
    _documents[document.document_id] = document


def get_document(document_id: str) -> ExtractedDocument | None:
    return _documents.get(document_id)


def list_documents() -> list[ExtractedDocument]:
    return list(_documents.values())


def save_result(result: ReconciliationResult) -> None:
    _results[result.invoice_id] = result


def get_result(invoice_id: str) -> ReconciliationResult | None:
    return _results.get(invoice_id)