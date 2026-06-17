# ADR-0004 — Gemini Flash with validated structured output

**Status:** Accepted · **Date:** 2026-06-15

## Context

WohnIQ's LLM tasks (query parsing, scam text extraction, explanation) are short and high-volume relative to a demo. We already pay for Gemini, and its Flash tier plus free quota covers demo-scale traffic at €0 incremental (per ADR-0003's budget constraint). The engineering risk with LLMs is not capability but *reliability*: free-form text breaks downstream code. A portfolio reviewer specifically looks for how we make model output safe to consume.

## Decision

Use **Gemini Flash** as the single LLM provider for all three product prompts (`parser.v1`, `scam_text.v1`, `explain.v1`) and **Gemini embeddings** for semantic search. Every call goes through a **central LLM client** that:

1. Requests **structured JSON** (function-calling / response schema) constrained to a Pydantic model.
2. **Validates** the response against that model.
3. On failure, **re-prompts once** with the validation error, then falls back to a deterministic path defined per prompt (keyword extractor for parser; rules-only for scam; templated text for explanation).
4. **Logs** prompt id+version, token counts, latency, and validation result for observability (SPEC §8).

No raw, unvalidated model text reaches business logic or the user.

## Alternatives considered

- **OpenAI/Anthropic APIs:** rejected for v1 — would add cost; Gemini is already paid for and sufficient. Provider is abstracted behind the client, so swapping later is cheap.
- **Free-form prompting + ad-hoc JSON parsing:** rejected — brittle, the exact anti-pattern this ADR exists to prevent.
- **Local open model:** rejected — infra/memory cost on Railway free tier outweighs benefit at this scale.

## Consequences

- **+** Reliable, typed boundaries; no user-facing 500 from a bad generation.
- **+** €0 incremental; provider abstracted for future swap.
- **+** Built-in observability and per-prompt evals make AI quality measurable.
- **−** Free-tier rate limits and possible training-on-data; acceptable for synthetic, non-sensitive data (note in README). Throttle/back-off handled in the client.
- **−** Structured-output mode varies by model version; pin the model and keep the schema in sync with `docs/system_prompts.md`.
- **−** Per-result explanation calls: `/search` currently calls `explain.v1` once per returned listing, so a page of N results is N+1 Gemini calls (1 parse + N explanations). Acceptable at demo scale and within the free tier, but it's the main call-volume hotspot. **Future optimization (deferred):** batch the explanations into a single multi-listing call (or generate them concurrently / lazily on demand), reducing a page to ~2 calls. Deferred because correctness and the grounded-output guarantee come first; batching is a latency/quota optimization, not a behavior change. The central client's transport seam means this can be added without touching callers.
