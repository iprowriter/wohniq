"""Central LLM client — the one place every Gemini *text* call goes through.

Per AGENTS.md golden rule 2, no raw model output reaches business logic. This module
enforces that: it asks Gemini for JSON constrained to a Pydantic schema, validates the
response, re-prompts once on failure, falls back to a caller-supplied default if it
still fails, and logs prompt id/version, token counts, latency, and the outcome
(observability, SPEC §8).

Design note: the actual Gemini call is isolated behind an injectable `transport`, and
the SDK is imported lazily inside it. That keeps the validation/retry/fallback logic
unit-testable without the network or the SDK installed.

Speed (ADR-0022): a caller may pass `timeout_s`; when the model hasn't answered by then,
or the service itself fails (quota, retired model, network), the fallback answers. The
model id and thinking budget are settings (GEMINI_CHAT_MODEL, GEMINI_THINKING_BUDGET).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Default chat model; the live value is `settings.gemini_chat_model` (see chat_model()).
CHAT_MODEL = "gemini-2.5-flash"

# Gemini calls run here so a caller can stop waiting after `timeout_s`; a call that
# overruns finishes in the background and its answer is dropped.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")

# Set when the model rejected the thinking setting, so we stop sending it.
_thinking_unsupported = False

T = TypeVar("T", bound=BaseModel)


def chat_model() -> str:
    return settings.gemini_chat_model.strip() or CHAT_MODEL


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


def _call_gemini(
    system: str, user: str, schema: type[BaseModel], temperature: float
) -> RawResponse:
    """Real transport: one structured-output call to Gemini. SDK imported lazily."""
    global _thinking_unsupported
    from google import genai
    from google.genai import errors, types

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")

    client = genai.Client(api_key=settings.gemini_api_key)
    budget = settings.gemini_thinking_budget
    use_thinking = budget >= 0 and not _thinking_unsupported

    def config(with_thinking: bool) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            thinking_config=(
                types.ThinkingConfig(thinking_budget=budget) if with_thinking else None
            ),
        )

    try:
        resp = client.models.generate_content(
            model=chat_model(), contents=user, config=config(use_thinking)
        )
    except errors.ClientError as exc:
        # Some models can't switch thinking off; drop the setting once and carry on.
        if not (use_thinking and exc.code == 400 and "thinking" in str(exc).lower()):
            raise
        _thinking_unsupported = True
        logger.warning("llm model=%s rejects thinking_budget; sending without it", chat_model())
        resp = client.models.generate_content(
            model=chat_model(), contents=user, config=config(False)
        )
    usage = resp.usage_metadata
    return RawResponse(
        text=resp.text or "",
        tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
        tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
    )


def _send_within(
    send: Transport,
    deadline: float | None,
    system: str,
    user: str,
    schema: type[BaseModel],
    temperature: float,
) -> RawResponse:
    """One transport call, abandoned (FutureTimeout) once `deadline` has passed."""
    if deadline is None:
        return send(system, user, schema, temperature)
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise FutureTimeout()
    return _POOL.submit(send, system, user, schema, temperature).result(timeout=remaining)


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
    timeout_s: float | None = None,
) -> LLMResult[T]:
    """Call the LLM and return a validated `schema` instance.

    On a validation failure, re-prompts up to `max_retries` times with the error
    appended. If still invalid, uses `fallback()` when provided, else raises LLMError.
    The fallback also answers when the service fails or `timeout_s` passes.
    """
    if transport is None and settings.demo_mode:
        # Offline demo mode: never reach Gemini; go straight to the deterministic path.
        if fallback is None:
            raise LLMError(f"{prompt_id}: offline demo mode and no fallback provided")
        logger.info("llm prompt=%s offline demo mode -> fallback (no network)", prompt_id)
        return _fallback_result(prompt_id, fallback, 0.0, 0)

    send = transport or _call_gemini
    start = time.perf_counter()
    deadline = start + timeout_s if timeout_s is not None else None
    current_user = user
    last_error: Exception | None = None
    attempt = 0

    for attempt in range(1, max_retries + 2):  # initial try + max_retries
        try:
            raw = _send_within(send, deadline, system, current_user, schema, temperature)
        except FutureTimeout:
            last_error = TimeoutError(f"no answer within {timeout_s:g}s")
            logger.warning(
                "llm prompt=%s attempt=%d timed out after %.0f ms",
                prompt_id,
                attempt,
                (time.perf_counter() - start) * 1000,
            )
            break
        except Exception as exc:  # service error: quota, retired model, network, no key
            last_error = exc
            # The type and status only: the message can echo the request (ADR-0012).
            logger.warning(
                "llm prompt=%s attempt=%d service error %s %s",
                prompt_id,
                attempt,
                type(exc).__name__,
                getattr(exc, "code", ""),
            )
            break
        try:
            data = schema.model_validate_json(raw.text)
        except ValidationError as exc:
            last_error = exc
            # Log where validation failed, not the values: model output can echo the
            # user's query (ADR-0012).
            logger.warning(
                "llm prompt=%s attempt=%d invalid: %d error(s) at %s",
                prompt_id,
                attempt,
                exc.error_count(),
                [".".join(str(p) for p in e["loc"]) for e in exc.errors()],
            )
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
            chat_model(),
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
            "llm prompt=%s using fallback after %d attempt(s) (latency_ms=%.0f)",
            prompt_id,
            attempt,
            latency_ms,
        )
        return _fallback_result(prompt_id, fallback, latency_ms, attempt)

    raise LLMError(f"{prompt_id}: no valid LLM output after {attempt} attempt(s): {last_error}")


def _fallback_result(
    prompt_id: str, fallback: Callable[[], T], latency_ms: float, attempts: int
) -> LLMResult[T]:
    return LLMResult(
        data=fallback(),
        raw="",
        prompt_id=prompt_id,
        tokens_in=0,
        tokens_out=0,
        latency_ms=latency_ms,
        attempts=attempts,
        used_fallback=True,
    )
