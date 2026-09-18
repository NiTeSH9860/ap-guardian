"""
Optional add-on: cross-reference a vendor against public web sources as a
lightweight fraud/legitimacy signal. Not required for the core pipeline — this
exists mainly to give the reconciliation step one more independent signal, and
as a clean, honest shot at the hackathon's separate "Best Use of Tavily" prize.

Skips silently if TAVILY_API_KEY is not configured, so the rest of the app works
fine without it.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def check_vendor_legitimacy(vendor_name: str) -> dict | None:
    if not settings.tavily_api_key or not vendor_name:
        return None

    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warning("tavily-python not installed; skipping vendor check")
        return None

    client = TavilyClient(api_key=settings.tavily_api_key)
    query = f"{vendor_name} company registration legitimacy reviews"
    response = client.search(query=query, max_results=5)

    results = response.get("results", [])
    return {
        "query": query,
        "sources_checked": len(results),
        "summary": [
            {"title": r.get("title"), "url": r.get("url")} for r in results
        ],
        # NOTE: this returns raw signals for a human reviewer, not an automated
        # verdict — a hackathon-scope fraud "score" would be more theater than
        # substance without real verification data behind it.
    }