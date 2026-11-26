# ADR-0018 — Offline scam wording check, and 40 extra listings to test it

**Status:** Accepted · **Date:** 2026-11-24 · Amends [ADR-0002](0002-hybrid-scam-detection.md)

## Context

After ADR-0017 the rules and photo signals no longer flag honest listings, but without Gemini
(offline demo mode, or no API key) the advance-fee and overseas-landlord scams reach only "Low":
only their wording gives them away, and that was the LLM pass's job. The project owner asked
for an offline check of the classic phrases, and for more listings, including honest ones that
use the same words innocently, so the check is tested from both sides.

## Decision

1. **`scam/wording.py`**: English and German patterns for four signals: off-platform payment
   (Western Union, MoneyGram, crypto, gift cards, payment links, escrow), payment before
   viewing ("Kaution vorab", "viewing after payment", "reservation fee"), keys sent by post or
   courier, and payment-linked urgency (weak, 0.3). Sentence by sentence; a negation before
   the trigger in the same sentence cancels it ("we never ask for…", "keine Überweisung vor…",
   "beware of scams"). "I'm abroad" counts only if nobody else shows the flat and the contract
   isn't signed in person. Evidence quotes the sentence.
2. **Same names as the LLM pass, source "rule"**. The detector always runs the wording check;
   when the LLM pass runs too, a signal both find is kept once, at the stronger severity.
3. **40 extra listings** (`generate_extra_listings`, own seed 4242, appended by
   `generate_catalogue()`; the original 100 are unchanged): 16 scams (5 advance-fee, 4
   overseas-landlord, 2 fake payment platform, 3 photo copies, 2 subtle with no telltale
   phrase), 10 honest listings using the scam words innocently, 14 plain honest. New photo
   sets reuse already-downloaded photos, at most 2 shared with any other set
   (`assign_from_existing`), so no Pexels key is needed and honest listings never look like
   a copy. `make seed-extra` adds them to a seeded database.

## Results (140 listings, rules + photos + wording, no LLM)

| | |
|---|---|
| Scams caught (High) | 23 of 31 (precision 100 %, recall 74 %) |
| Honest listings at High | 0 of 109 |
| Tricky-but-honest listings at Low | 18 of 18 |
| Bands | 105 Low · 12 Caution · 23 High |

Missed by design: the 6 photo copies stay at Caution (photo reuse alone is capped there, since
the listing may be the original), and the 2 subtle scams have nothing in the text to find.
The patterns were written while looking at this set, so the figures are optimistic for unseen
wording; the LLM pass remains the general reader.

## Alternatives considered

- **Keyword list without negation handling**: flags the honest "we never ask for Western Union".
- **A small trained text classifier**: more general, but opaque and trained on our own synthetic
  texts; the explainable-signal rule of ADR-0002 favours readable patterns.

## Consequences

- \+ Offline demo mode explains the common scams with quoted evidence.
- − Patterns need upkeep as wording changes; new scam phrasings go to the LLM pass first.
- − Embeddings for the 40 new listings need Gemini (`make embed`); until then live semantic
  search ranks them lexically only.
