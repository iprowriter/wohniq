"""Central LLM client — the one place every Gemini *text* call goes through.

Per AGENTS.md golden rule 2, no raw model output reaches business logic. This module
enforces that: it asks Gemini for JSON constrained to a Pydantic schema, validates the
response, re-prompts once on failure, falls back to a caller-supplied default if it
still fails, and logs prompt id/version, token counts, latency, and the outcome
(observability, SPEC §8).

Design note: the actual Gemini call is isolated behind an injectable `transport`, and
the SDK is imported lazily inside it. That keeps the validation/retry/fallback logic
unit-testable without the network or the SDK installed.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from core.logging import get_logger

logger = get_logger(__name__)

# Gemini Flash chat model. If the API rejects this id, update it here (model ids
# evolve); this is the single place it's referenced.
CHAT_MODEL = "gemini-2.5-flash"

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the model output can't be validated and no fallback was given."""


@dataclass
class RawResponse:
    """What a transport returns: the raw text plus token accounting."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class LLMResult(Generic[T]):
    data: T
    raw: str
    prompt_id: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    attempts: int
    used_fallback: bool


Transport = Callable[[str, str, type[BaseModel], float], RawResponse]


def _call_gemini(system: str, user: str, schema: type[BaseModel], temperature: float) -> RawResponse:
    """Real transport: one structured-output call to Gemini. SDK imported lazily."""
    from google import genai
    from google.genai import types

    from core.config import settings

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")

    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
    )
    resp = client.models.generate_content(model=CHAT_MODEL, contents=user, config=config)
    usage = resp.usage_metadata
    return RawResponse(
        text=resp.text or "",
        tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
        tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
    )


def generate_structured(
    *,
    prompt_id: str,
    system: str,
    user: str,
    schema: type[T],
    temperature: float = 0.2,
    fallback: Callable[[], T] | None = None,
    max_retries: int = 1,
    transport: Transport | None = None,
) -> LLMResult[T]:
    """Call the LLM and return a validated `schema` instance.

    On a validation failure, re-prompts up to `max_retries` times with the error
    appended. If still invalid, uses `fallback()` when provided, else raises LLMError.
    """
    send = transport or _call_gemini
    start = time.perf_counter()
    current_user = user
    last_error: ValidationError | None = None

    for attempt in range(1, max_retries + 2):  # initial try + max_retries
        raw = send(system, current_user, schema, temperature)
        try:
            data = schema.model_validate_json(raw.text)
        except ValidationError as exc:
            last_error = exc
            logger.warning("llm prompt=%s attempt=%d invalid: %s", prompt_id, attempt, exc)
            current_user = (
                f"{user}\n\nYour previous response failed validation:\n{exc}\n"
                "Return ONLY valid JSON matching the schema."
            )
            continue

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "llm prompt=%s model=%s tokens_in=%d tokens_out=%d latency_ms=%.0f "
            "attempts=%d fallback=False",
            prompt_id,
            CHAT_MODEL,
            raw.tokens_in,
            raw.tokens_out,
            latency_ms,
            attempt,
        )
        return LLMResult(
            data=data,
            raw=raw.text,
            prompt_id=prompt_id,
            tokens_in=raw.tokens_in,
            tokens_out=raw.tokens_out,
            latency_ms=latency_ms,
            attempts=attempt,
            used_fallback=False,
        )

    latency_ms = (time.perf_counter() - start) * 1000
    if fallback is not None:
        logger.warning(
            "llm prompt=%s using fallback after %d attempts (latency_ms=%.0f)",
            prompt_id,
            max_retries + 1,
            latency_ms,
        )
        return LLMResult(
            data=fallback(),
            raw="",
            prompt_id=prompt_id,
            tokens_in=0,
            tokens_out=0,
            latency_ms=latency_ms,
            attempts=max_retries + 1,
            used_fallback=True,
        )

    raise LLMError(
        f"{prompt_id}: invalid LLM output after {max_retries + 1} attempts: {last_error}"
    )
