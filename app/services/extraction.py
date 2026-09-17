"""
Stage 1: document -> structured fields.

Uses the cheap, fast Lightning model because this stage runs on every page of
every uploaded document. Volume is high and each individual call is low-stakes,
so we optimize for cost/latency here and save reasoning depth for the
reconciliation stage (see reconciliation.py) where it actually matters.
"""
from app.config import settings
from app.models.schemas import DocumentType, ExtractedDocument, LineItem
from app.services.token_factory_client import chat_completion_json

_EXTRACTION_SYSTEM_PROMPT = """You are a document field extractor for accounts payable \
processing. Given the raw text of an invoice, purchase order, or contract, extract \
structured fields. Return ONLY a JSON object, no markdown, no preamble, matching this shape:

{
  "vendor_name": string or null,
  "document_number": string or null,
  "date": string or null (ISO 8601 if determinable),
  "due_date": string or null,
  "total_amount": number or null,
  "payment_terms": string or null,
  "line_items": [
    {"description": string, "quantity": number, "unit_price": number, "total": number}
  ]
}

Extract only what is explicitly present in the text. Do not infer or estimate values
that are not stated. If a field is not present, use null."""


def extract_document(
    document_id: str,
    document_type: DocumentType,
    raw_text: str,
) -> ExtractedDocument:
    """Extract structured fields from a single document's raw text.

    For multi-page documents, callers should chunk by page and merge results
    (see utils/chunking.py) rather than sending an entire long document in one
    call — this keeps each extraction call small, fast, and cheap.
    """
    user_prompt = f"Document type: {document_type.value}\n\nRaw text:\n{raw_text}"

    result = chat_completion_json(
        model=settings.nebius_extraction_model,
        system_prompt=_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    line_items = [
        LineItem(
            description=item.get("description", ""),
            quantity=float(item.get("quantity") or 0),
            unit_price=float(item.get("unit_price") or 0),
            total=float(item.get("total") or 0),
        )
        for item in result.get("line_items", [])
    ]

    return ExtractedDocument(
        document_id=document_id,
        document_type=document_type,
        vendor_name=result.get("vendor_name"),
        document_number=result.get("document_number"),
        date=result.get("date"),
        due_date=result.get("due_date"),
        total_amount=result.get("total_amount"),
        payment_terms=result.get("payment_terms"),
        line_items=line_items,
        raw_text=raw_text,
    )