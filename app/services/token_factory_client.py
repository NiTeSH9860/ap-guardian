"""
Thin wrapper around Nebius Token Factory's OpenAI-compatible endpoint.

Token Factory exposes an OpenAI-compatible API, so we use the official `openai`
SDK pointed at Nebius's base URL rather than hand-rolling HTTP calls. This is the
ONLY file that talks to the network for model inference — every other service
calls through here, which keeps model-routing logic auditable in one place.
"""
import json
import logging
from typing import Any, Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
        )
    return _client


def chat_completion(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """
    Single entry point for every model call in the app.

    `model` is always passed in explicitly by the caller (extraction.py passes the
    Lightning model, reconciliation.py passes the Ultra model) rather than being a
    global default — this is what makes the cost/latency tradeoff of the routing
    pattern visible and intentional rather than accidental.
    """
    client = get_client()

    kwargs: dict[str, Any] = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    logger.info("Calling Token Factory model=%s json_mode=%s", model, json_mode)
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def chat_completion_json(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict:
    """Convenience wrapper for calls that expect a JSON object back.

    Always instruct the model, in the system prompt, to return ONLY a JSON object
    with no markdown fences or preamble — this wrapper strips fences defensively
    but the prompt should not rely on that.
    """
    raw = chat_completion(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from model output: %s", raw[:500])
        raise