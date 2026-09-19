from fastapi import APIRouter, HTTPException

from app.models.schemas import DraftEmail, ReconciliationResult
from app.services import email_draft, reconciliation, retrieval, store, vendor_check

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


@router.post("/{invoice_document_id}", response_model=ReconciliationResult)
async def run_reconciliation(invoice_document_id: str):
    """
    The core demo endpoint: given an already-uploaded invoice, retrieve its
    matching PO/contract context, run the discrepancy reasoning (Nemotron-3-Ultra),
    optionally check vendor legitimacy via Tavily, and return grounded findings.
    """
    invoice = store.get_document(invoice_document_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice document not found")

    context = retrieval.find_matching_context(invoice)

    result = reconciliation.reconcile(
        invoice=invoice,
        po_chunks=context["po_chunks"],
        contract_chunks=context["contract_chunks"],
    )

    if invoice.vendor_name:
        result.vendor_check = vendor_check.check_vendor_legitimacy(invoice.vendor_name)

    store.save_result(result)
    return result


@router.get("/{invoice_document_id}", response_model=ReconciliationResult)
async def get_reconciliation(invoice_document_id: str):
    result = store.get_result(invoice_document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No reconciliation result yet for this invoice")
    return result


@router.post("/{invoice_document_id}/draft", response_model=DraftEmail)
async def draft_email(invoice_document_id: str, to_vendor: bool = True):
    result = store.get_result(invoice_document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run reconciliation before drafting a resolution")
    if not result.discrepancies:
        raise HTTPException(status_code=400, detail="No discrepancies found — nothing to draft")

    return email_draft.draft_resolution(result, to_vendor=to_vendor)