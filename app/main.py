import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import documents, reconcile

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="AP Guardian",
    description=(
        "Autonomous accounts payable reconciliation agent. "
        "Powered by NVIDIA Nemotron models served on Nebius Token Factory."
    ),
    version="0.1.0",
)

# Wide-open CORS is fine for a hackathon demo; scope this down before real use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(reconcile.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "extraction_model": settings.nebius_extraction_model,
        "reconciliation_model": settings.nebius_reconciliation_model,
    }