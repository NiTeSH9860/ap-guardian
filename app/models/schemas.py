"""
Shared data contracts between pipeline stages. Keeping these explicit (rather than
passing raw dicts between services) is what makes the citation/grounding guarantee
enforceable: every discrepancy finding must carry a SourceSpan back to real text.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    CONTRACT = "contract"


class SourceSpan(BaseModel):
    """Points back to the exact text a claim is grounded in — never a paraphrase."""
    document_id: str
    document_type: DocumentType
    quote: str = Field(..., description="Exact substring from the source document")
    page: Optional[int] = None


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float
    source: Optional[SourceSpan] = None


class ExtractedDocument(BaseModel):
    """Output of the extraction stage (Nemotron-3.5-Lightning)."""
    document_id: str
    document_type: DocumentType
    vendor_name: Optional[str] = None
    document_number: Optional[str] = None  # invoice #, PO #, contract #
    date: Optional[str] = None
    due_date: Optional[str] = None
    total_amount: Optional[float] = None
    line_items: list[LineItem] = Field(default_factory=list)
    payment_terms: Optional[str] = None
    raw_text: str = ""


class DiscrepancySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiscrepancyType(str, Enum):
    PRICE_MISMATCH = "price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    UNAUTHORIZED_FEE = "unauthorized_fee"
    DUPLICATE_BILLING = "duplicate_billing"
    EXPIRED_TERMS = "expired_terms"
    MISSING_PO_MATCH = "missing_po_match"
    OTHER = "other"


class Discrepancy(BaseModel):
    """A single finding from the reconciliation stage (Nemotron-3-Ultra).
    Every discrepancy must cite at least one SourceSpan — this is enforced
    downstream by reconciliation.validate_grounding().
    """
    type: DiscrepancyType
    severity: DiscrepancySeverity
    summary: str
    explanation: str
    invoice_citation: Optional[SourceSpan] = None
    contract_or_po_citation: Optional[SourceSpan] = None
    suggested_action: str


class ReconciliationResult(BaseModel):
    invoice_id: str
    matched_po_id: Optional[str] = None
    matched_contract_id: Optional[str] = None
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    overall_risk: DiscrepancySeverity = DiscrepancySeverity.LOW
    vendor_check: Optional[dict] = None


class DraftEmail(BaseModel):
    to_vendor: bool
    subject: str
    body: str
    related_discrepancies: list[str] = Field(default_factory=list)