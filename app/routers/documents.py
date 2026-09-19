import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import DocumentType, ExtractedDocument
from app.services import extraction, retrieval, store
from app.utils.pdf_parser import extract_text

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=ExtractedDocument)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
):
    """
    Upload a single invoice, PO, or contract. Extracts structured fields
    (Nemotron-3.5-Lightning) and indexes the document for retrieval if it's a
    PO or contract — invoices are reconciled against the index, not indexed
    into it, since we retrieve *from* POs/contracts *for* an invoice.
    """
    raw_bytes = await file.read()
    try:
        raw_text = extract_text(raw_bytes, file.filename or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in file")

    document_id = str(uuid.uuid4())
    extracted = extraction.extract_document(document_id, document_type, raw_text)
    store.save_document(extracted)

    if document_type in (DocumentType.PURCHASE_ORDER, DocumentType.CONTRACT):
        retrieval.index_document(extracted)

    return extracted


@router.get("/{document_id}", response_model=ExtractedDocument)
async def get_document(document_id: str):
    document = store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("", response_model=list[ExtractedDocument])
async def list_documents():
    return store.list_documents()