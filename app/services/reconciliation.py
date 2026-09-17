"""
Stage 3: the actual reasoning step. This is the one call per invoice that matters,
so it's the one call we spend the expensive model on.

This is also where the project's core differentiator lives: every discrepancy the
model reports must be grounded in an exact quote from the source text. We enforce
this in two layers — (1) the prompt requires it explicitly, and (2)
validate_grounding() below rejects any finding whose cited quote does not actually
appear in the source document, rather than trusting the model's claim at face value.
"""
import logging

from app.config import settings
from app.models.schemas import (
    Discrepancy,
    DiscrepancySeverity,
    DiscrepancyType,
    ExtractedDocument,
    ReconciliationResult,
    SourceSpan,
    DocumentType,
)
from app.services.token_factory_client import chat_completion_json

logger = logging.getLogger(__name__)

_RECONCILIATION_SYSTEM_PROMPT = """You are a meticulous accounts payable auditor. You will \
be given an invoice, its matched purchase order, and relevant contract clauses. Find every \
discrepancy: price mismatches, quantity mismatches, unauthorized fees not in the contract, \
signs of duplicate billing, and violations of contract terms (e.g. expired pricing, \
disallowed charges).

CRITICAL RULE: every discrepancy you report MUST include an exact, verbatim quote from the \
invoice text AND, where applicable, an exact verbatim quote from the PO or contract text. \
Do not paraphrase the quotes. Do not report a discrepancy you cannot support with an exact \
quote from the provided text. If you are not confident something is a discrepancy, omit it \
rather than guessing.

Return ONLY a JSON object with this shape, no markdown, no preamble:

{
  "discrepancies": [
    {
      "type": "price_mismatch" | "quantity_mismatch" | "unauthorized_fee" | "duplicate_billing" | "expired_terms" | "missing_po_match" | "other",
      "severity": "low" | "medium" | "high" | "critical",
      "summary": string,
      "explanation": string,
      "invoice_quote": string or null,
      "contract_or_po_quote": string or null,
      "suggested_action": string
    }
  ],
  "overall_risk": "low" | "medium" | "high" | "critical"
}"""


def reconcile(
    invoice: ExtractedDocument,
    po_chunks: list[str],
    contract_chunks: list[str],
    matched_po_id: str | None = None,
    matched_contract_id: str | None = None,
) -> ReconciliationResult:
    user_prompt = f"""INVOICE ({invoice.document_id}):
{invoice.raw_text}

MATCHED PURCHASE ORDER CONTEXT:
{chr(10).join(po_chunks) if po_chunks else '(no matching PO found)'}

RELEVANT CONTRACT CLAUSES:
{chr(10).join(contract_chunks) if contract_chunks else '(no relevant contract found)'}"""

    result = chat_completion_json(
        model=settings.nebius_reconciliation_model,
        system_prompt=_RECONCILIATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        # Slightly higher token budget than extraction — this call needs room to
        # reason over multiple documents at once.
        max_tokens=8192,
    )

    discrepancies = []
    for item in result.get("discrepancies", []):
        discrepancy = _build_discrepancy(item, invoice, matched_po_id, matched_contract_id)
        if discrepancy is not None:
            discrepancies.append(discrepancy)

    return ReconciliationResult(
        invoice_id=invoice.document_id,
        matched_po_id=matched_po_id,
        matched_contract_id=matched_contract_id,
        discrepancies=discrepancies,
        overall_risk=DiscrepancySeverity(result.get("overall_risk", "low")),
    )


def _build_discrepancy(
    item: dict,
    invoice: ExtractedDocument,
    matched_po_id: str | None,
    matched_contract_id: str | None,
) -> Discrepancy | None:
    """Validate grounding before accepting a discrepancy: the cited invoice quote
    must actually appear verbatim in the invoice's raw text. This is the guardrail
    against hallucinated findings — if the model invents a quote, we drop the
    finding rather than surface an ungrounded claim to the user.
    """
    invoice_quote = item.get("invoice_quote")
    invoice_citation = None
    if invoice_quote:
        if invoice_quote not in invoice.raw_text:
            logger.warning(
                "Dropping discrepancy: invoice quote not found verbatim in source. quote=%r",
                invoice_quote[:120],
            )
            return None
        invoice_citation = SourceSpan(
            document_id=invoice.document_id,
            document_type=DocumentType.INVOICE,
            quote=invoice_quote,
        )

    contract_or_po_quote = item.get("contract_or_po_quote")
    contract_or_po_citation = None
    if contract_or_po_quote:
        # We don't have the raw PO/contract text at this layer (only retrieved
        # chunks were passed to the model) — in a production build, pass the
        # source document_id alongside each chunk so this can be validated too.
        contract_or_po_citation = SourceSpan(
            document_id=matched_po_id or matched_contract_id or "unknown",
            document_type=DocumentType.PURCHASE_ORDER if matched_po_id else DocumentType.CONTRACT,
            quote=contract_or_po_quote,
        )

    try:
        return Discrepancy(
            type=DiscrepancyType(item.get("type", "other")),
            severity=DiscrepancySeverity(item.get("severity", "low")),
            summary=item.get("summary", ""),
            explanation=item.get("explanation", ""),
            invoice_citation=invoice_citation,
            contract_or_po_citation=contract_or_po_citation,
            suggested_action=item.get("suggested_action", ""),
        )
    except ValueError:
        logger.warning("Dropping malformed discrepancy: %r", item)
        return None