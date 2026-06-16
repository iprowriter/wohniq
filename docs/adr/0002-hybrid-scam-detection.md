# ADR-0002 — Scam detection is a hybrid rules + pHash + LLM engine

**Status:** Accepted · **Date:** 2026-06-15

## Context

Scam/risk detection is WohnIQ's showpiece feature (SPEC F7). German rental scams have a well-known fingerprint: price far below the Kiez market, reused/stolen photos across "different" addresses, landlord "abroad", off-platform payment, manufactured urgency, and "no Anmeldung". These signals are a mix of *crisp/quantitative* (price, duplicate images, metadata) and *fuzzy/linguistic* (payment intent, evasiveness, urgency). A pure-LLM "is this a scam?" classifier would be opaque, inconsistent, costly per call, and unconvincing in a demo.

## Decision

Build a **hybrid risk engine** that fuses three sources into a single explained 0–100 score with Low/Caution/High bands:

1. **Deterministic rule signals (code, €0):** price z-score vs. Kiez+size median; metadata rules (furnished-luxury-for-cheap, suspiciously low Warmmiete, duplicate phone/email, off-platform contact push).
2. **Image signals (local pHash, €0):** perceptual-hash duplicate detection across our own listing DB to catch reused photo sets.
3. **LLM text pass (`scam_text.v1`):** extracts the fuzzy language signals as *validated structured output with verbatim evidence quotes* — not a verdict.

A transparent fusion step combines weighted signals into the score and **emits the contributing signals with their evidence**, so the UI can show *why* a listing was flagged.

## Alternatives considered

- **Single LLM classifier:** rejected — opaque, inconsistent, no free evidence, costs a call per listing, weak portfolio story.
- **Rules only:** rejected — misses the linguistic signals that distinguish a clumsy-but-legit listing from a scam.
- **Trained ML classifier only:** deferred — viable because we hold ground-truth labels (ADR-0003); we may add a small scikit-learn model as an *additional* fused signal and to report metrics, but the explainable hybrid remains the core.

## Consequences

- **+** Explainable by construction: the score carries its reasons, which is the single best demo screenshot.
- **+** Cheap: the expensive signals are local; only the text pass hits the API (Flash, free tier).
- **+** Measurable: because data is synthetic and labeled, we report precision/recall + a confusion matrix (SPEC F7 AC4).
- **−** Fusion weights need tuning and could mis-calibrate (mitigated: precision-prioritized tuning against the labeled set; don't flag legit cheap flats).
- **−** pHash needs the image bytes at seed time to compute hashes (handled in the image seeder).
