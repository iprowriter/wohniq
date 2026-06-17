# ADR-0007 — Direct provider SDK over an agent framework (LangChain/LangGraph)

**Status:** Accepted · **Date:** 2026-06-16 · **Relates to:** ADR-0001 (LLM does language, code does logic), ADR-0004 (Gemini + structured output)

## Context

WohnIQ's LLM usage is three **single-shot, stateless** calls: parse a query (`parser.v1`), read scam text (`scam_text.v1`), and write an explanation (`explain.v1`). Each is one request in, one validated object out — no conversation state, no tool-calling loops, no multi-step planning. A natural question is whether to build this on an agent framework like LangChain/LangGraph instead of calling the provider SDK directly through our own thin client (`core/llm.py`, T2.1).

LangGraph is an *orchestration* framework for stateful, cyclic, multi-actor agent workflows (plan → act → observe → loop, shared state, checkpoints). LangChain adds provider-agnostic wrappers, prompt templates, and output parsers. These solve a problem shape — complex agentic flow — that WohnIQ deliberately does not have (per ADR-0001, the LLM is a stateless language component; deterministic code owns orchestration and ranking).

## Decision

Call the Gemini SDK **directly**, behind our own minimal client (`generate_structured` in `core/llm.py`). Do **not** adopt LangChain or LangGraph.

Provider portability is achieved by our own abstraction boundary, not a framework: the **injectable `transport`** and the single `CHAT_MODEL` constant. Switching providers means writing one new transport function (call the other SDK, return a `RawResponse`); the parser/scam/explain callers, which only know `generate_structured`, are untouched.

## Alternatives considered

- **LangChain (chains + provider abstraction):** rejected — heavy dependency tree, fast-moving/breaking API, and it hides the validation/retry/fallback logic that is the whole point of our client. Provider-swapping (its main relevant benefit) we already get from the transport boundary in ~10 lines.
- **LangGraph (stateful agent graph):** rejected for now — built for looping, stateful, tool-calling agents; using it for three stateless calls is over-engineering. Would be the *right* choice if WohnIQ grew a conversational/agentic feature (see below).

## Consequences

- **+** Transparency: the reliability logic is readable in one small file — strong portfolio signal and easy to debug.
- **+** Fewer dependencies and far less version churn; smaller attack/maintenance surface.
- **+** Portability preserved via the transport seam, without framework lock-in.
- **+** Keeps us honest to ADR-0001 — we didn't build an agent, so we don't carry an agent framework.
- **−** If we later add a genuinely agentic feature (multi-step planning, tool loops, conversation memory), we'd hand-roll more orchestration than a framework would give us. Mitigation: that's the trigger to introduce LangGraph, at which point our `generate_structured` calls become nodes in a graph — the current design doesn't preclude it.
- **−** We forgo LangChain's prebuilt integrations (loaders, output parsers); acceptable, since our needs are met by Pydantic + the SDK's structured output.
