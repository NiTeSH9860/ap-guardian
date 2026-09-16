# AP Guardian

**An autonomous accounts payable reconciliation agent.**

Upload an invoice, and AP Guardian cross-checks it against the matching purchase order and
vendor contract, flags discrepancies a human reviewer would likely miss, and drafts the
resolution email — with every finding cited back to the exact source clause or line item.

Built for the **Nebius x NVIDIA Global AI Hackathon** — Best Apps and Agents track.

## Why this exists

Accounts payable teams manually cross-reference invoices against POs and contracts all day.
Price creep, duplicate billing, unauthorized fees, and expired-contract terms routinely slip
through. AP Guardian automates the tedious cross-referencing and reserves human judgment for
the actual approve/reject decision.

## How it uses Nebius Token Factory + NVIDIA Nemotron

This project deliberately routes across model sizes rather than calling one model once:

| Stage | Model | Why |
|---|---|---|
| Document field extraction (runs on every page, high volume) | `nvidia/Nemotron-3_5-Lightning` | Cheap and fast — this step runs many times per document set, so cost/latency matter more than max reasoning depth. |
| Discrepancy reasoning (runs once per invoice, low volume) | `nvidia/Nemotron-3-Ultra` | This is the one call per invoice that actually matters — worth spending reasoning effort and tokens on, since it drives the final decision. |
| Vendor legitimacy check (optional) | Tavily web search | Cross-references vendor details against public sources as a lightweight fraud signal. |

Both models are served via **Nebius Token Factory**'s OpenAI-compatible endpoint, so switching
models is a one-line config change (see `app/config.py`).

## Architecture

```
Invoice/PO/Contract (PDF/image)
        │
        ▼
 [Extraction service]  ──▶ Nemotron-3.5-Lightning ──▶ structured fields (vendor, line items, amounts, dates)
        │
        ▼
 [Retrieval service]   ──▶ vector store ──▶ matching PO + relevant contract clauses
        │
        ▼
 [Reconciliation service] ──▶ Nemotron-3-Ultra ──▶ discrepancy report, cited to source spans
        │
        ▼
 [Drafting service]    ──▶ vendor follow-up email / internal approval draft (human-approved before sending)
```

## Repo layout

```
app/
  main.py                    FastAPI app entrypoint
  config.py                  Settings / environment config
  models/schemas.py          Pydantic request/response models
  services/
    token_factory_client.py  Thin client wrapping Nebius Token Factory's OpenAI-compatible API
    extraction.py            Document → structured fields (Lightning model)
    retrieval.py             Vector store indexing + retrieval of matching PO/contract
    reconciliation.py        Discrepancy reasoning (Ultra model), citation-grounded
    email_draft.py           Drafts the resolution email/approval request
    vendor_check.py          Optional Tavily-based vendor legitimacy check
  routers/
    documents.py             Upload/ingest endpoints
    reconcile.py             Run reconciliation, fetch results
  utils/
    pdf_parser.py            PDF/text extraction helpers
    chunking.py               Chunking + span tracking for citations
data/sample_docs/            Synthetic sample invoices/POs/contracts for demo + testing
tests/                       Unit tests
frontend/                    Minimal UI (upload + discrepancy dashboard)
```

## Setup

1. **Clone and install dependencies**

   ```bash
   git clone https://github.com/NiTeSH9860/ap-guardian.git
   cd ap-guardian
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Fill in:
   - `NEBIUS_API_KEY` — from your Nebius Token Factory console
   - `NEBIUS_BASE_URL` — Token Factory's OpenAI-compatible base URL
   - `TAVILY_API_KEY` — optional, only needed for the vendor legitimacy check

3. **Run the API**

   ```bash
   uvicorn app.main:app --reload
   ```

   The API will be live at `http://localhost:8000`. Interactive docs at `/docs`.

4. **Run the frontend**

   See `frontend/README.md`.

5. **Run tests**

   ```bash
   pytest
   ```

## Demo flow

1. Upload a sample invoice + matching PO + contract from `data/sample_docs/`.
2. AP Guardian extracts structured fields from all three.
3. It retrieves the matching PO/contract for the invoice.
4. Nemotron-3-Ultra reasons over the set and flags discrepancies (price mismatch, unauthorized
   fees, duplicate billing, expired terms), each cited to the source line/clause.
5. A draft vendor email or internal approval note is generated for human review.

## What was built during the submission period

*(Fill this in if this project existed before the hackathon submission window opened —
required by the rules. If built entirely during the window, note that instead.)*

## License

MIT — see `LICENSE`.