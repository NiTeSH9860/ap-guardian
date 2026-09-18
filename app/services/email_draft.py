"""
Stage 4: draft the resolution email/note based on reconciliation findings.

Deliberately does NOT send anything automatically — drafts are returned for human
review/edit/send. For a hackathon demo this is both the safer design and the
better demo beat: it shows judgment rather than a system that fires off emails
on its own.
"""
from app.config import settings
from app.models.schemas import DraftEmail, ReconciliationResult
from app.services.token_factory_client import chat_completion_json

_DRAFT_SYSTEM_PROMPT = """You are an accounts payable specialist drafting a professional, \
concise email or internal note about invoice discrepancies. Be specific and reference the \
exact numbers involved. Be firm but courteous if writing to a vendor. Return ONLY a JSON \
object: {"subject": string, "body": string}"""


def draft_resolution(result: ReconciliationResult, to_vendor: bool = True) -> DraftEmail:
    if not result.discrepancies:
        raise ValueError("No discrepancies to draft a resolution for")

    findings_text = "\n".join(
        f"- [{d.severity.value.upper()}] {d.summary}: {d.explanation}"
        for d in result.discrepancies
    )
    audience = "the vendor" if to_vendor else "internal AP approval reviewers"
    user_prompt = (
        f"Write a draft addressed to {audience} regarding invoice {result.invoice_id}.\n\n"
        f"Findings:\n{findings_text}"
    )

    output = chat_completion_json(
        model=settings.nebius_reconciliation_model,
        system_prompt=_DRAFT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.4,
    )

    return DraftEmail(
        to_vendor=to_vendor,
        subject=output.get("subject", f"Discrepancies found on invoice {result.invoice_id}"),
        body=output.get("body", ""),
        related_discrepancies=[d.summary for d in result.discrepancies],
    )