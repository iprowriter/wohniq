# ADR-0001 — Ranking is deterministic; the LLM never scores or orders

**Status:** Accepted · **Date:** 2026-06-15

## Context

WohnIQ ranks listings against parsed user criteria across several factors (commute, budget fit, quiet, amenities, neighborhood). A tempting shortcut is to hand the LLM the candidate listings and ask it to rank them. LLMs are unreliable at consistent ordering and arithmetic: the same input can yield different orders, scores don't add up, and the logic is opaque. This project is also a portfolio piece whose central claim is *good engineering judgment* — and the clearest signal of that judgment is using the model only where it's strong.

## Decision

Ranking is a **deterministic scoring function implemented in code**. Each factor produces a normalized sub-score with documented, configurable weights; the total determines order. The function is pure: same input → same output. The LLM is excluded from the ranking and scoring path entirely. The LLM's roles are limited to parsing queries (`parser.v1`), reading fuzzy scam text (`scam_text.v1`), and writing explanations from the already-computed breakdown (`explain.v1`).

## Alternatives considered

- **LLM-as-ranker:** rejected — non-reproducible, unexplainable, weak at math, and exactly the anti-pattern a reviewer would flag.
- **LLM re-rank on top of deterministic shortlist:** deferred — possible future nuance for tie-breaks, but adds non-determinism for marginal benefit; not worth it for v1.

## Consequences

- **+** Reproducible, testable, inspectable ordering; every result ships a per-factor breakdown.
- **+** Explanations are trustworthy because they're generated *from* the same numbers that produced the rank.
- **+** Strong portfolio signal: clean separation of language (LLM) vs. logic (code).
- **−** We must hand-design and tune the scoring function and weights (mitigated: weights are configurable and covered by a ranking sanity eval).
- This decision is load-bearing for ADR-0004 (structured I/O) and the SPEC's F3/F4 acceptance criteria.
