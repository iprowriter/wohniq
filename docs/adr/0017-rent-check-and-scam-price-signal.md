# ADR-0017 — Rent check against the Mietspiegel, and the scam price signal that uses it

**Status:** Accepted · **Date:** 2026-11-24 · Amends [ADR-0002](0002-hybrid-scam-detection.md)

## Context

With the Berlin data in place (ADR-0016), every listing and any address can be checked against
the Berliner Mietspiegel 2026 and the rent brake (§ 556d BGB: at most the local comparable
rent + 10 %). Two problems showed up when the 100 synthetic listings met the real index:

1. **Rents.** The generator prices from Kiez *asking* rents (about €10–22/m²); the Mietspiegel
   reflects existing contracts (about €6–14/m²). 76 of 77 honest pre-2014 listings came out
   above the limit (median 1.65 ×), so "Only fair rents" would show almost nothing. The
   "price-bait" scams, priced 45–60 % under the asking rate, sat at 0.85–1.24 × the *lowest*
   index value: not suspicious at all against the index.
2. **Scam signals.** The price check compared with the Kiez median of our own (inflated) listings,
   so lowering honest rents to fair levels would have flagged them as "too cheap". And photo
   reuse fired on any single shared photo: the 100 listings share 141 stock photos, so every
   listing had the signal and none could show "Low risk" (93 Caution, 7 High).

## Decision

1. **Rent maths** (`backend/berlin/rent.py`, pure): the table row from location class,
   building age (East/West for 1973–1990) and size; the checklist netted per group, each net
   group moving 20 % of the way to the range edge (No. 10.3; the brochure's own example,
   €7.30 → €7.75, is a test); rent-brake limit = comparable rent × 1.1; new builds (2014 or
   later, standing in for "first let after 1 Oct 2014") have no limit; an energy value ticks
   the energy boxes and replaces the insulation item; items the brochure excludes for a
   building age are ignored; the −€0.33 deduction for flats up to 1949 without heating/bath.
   The exemptions and "not legal advice" text always travel with a verdict.
2. **Listings get an estimate**: features unknown, so comparable rent = index mean, labelled
   as an estimate. The listing is matched to the nearest real address in its district; its
   location class, planning area, nearest station and "Around this flat" all come from that
   one point (fixes the earlier build's "Kreuzberg" title over a "Mitte" profile).
3. **The user's own rent check runs in the browser**: `/rent/index` serves the table,
   checklist (with English labels) and constants; the flat's rent and features are never
   sent to the server. The Python module is the reference implementation the browser one is
   tested against.
4. **Rent overrides** (`data/berlin/fair_rents.py` → `data/demo/rent_overrides.json`,
   committed synthetic-listing data like `risk.json`): about 45 % of honest pre-2014
   listings get a fair rent inside their range, and every price-bait scam goes 35–55 % below
   the index's lower end. Chosen by a hash of the id; the generator applies them by id, so
   ids, photos and labels don't change. Result: 30 within the limit, 58 above, 8 new builds,
   4 below the index.
5. **Scam price signal against the index** (`price_below_index`): fires at ≥ 15 % below the
   lowest index value for the flat, full strength at 45 %. The Kiez-median check remains the
   fallback when a flat has no index row or the Berlin data is missing.
6. **Photo reuse needs ≥ 4 photos shared with one other listing.** A copied listing takes the
   whole set (5 of 5); honest listings share at most 3 stock photos by chance. Photos spread
   over several listings don't add up.

## Results (offline, rules + photos, no LLM)

| | Before | After |
|---|---|---|
| Risk bands | 0 Low · 93 Caution · 7 High | 88 Low · 8 Caution · 4 High |
| Scams caught (High) | 6 of 15 | 4 of 15 |
| Honest/hard-negative listings at High | 1 | 0 |
| Honest/hard-negative listings at Low | 0 of 85 | 82 of 85 |

The 6 scams now at Low are the advance-fee and overseas-landlord ones, which only their
wording gives away; they were "caught" before by an accidental photo match. The next step adds
an offline wording check for them (owner decision, Stop 2 of the previous build).

## Alternatives considered

- **Keep the Kiez-median price check** and lower rents anyway: flags fair listings as
  price bait (13 of them in the earlier build's measurement).
- **Leave the rents as generated**: true to asking-rent reality, but makes the rent check
  useless for demonstration ("only fair rents" ≈ empty).
- **Generator computes fair rents itself**: would make the generator depend on the Berlin build,
  so listings would differ between machines with and without it.

## Consequences

- \+ The rent verdict and the scam price signal use the same official yardstick.
- \+ "Low risk" is reachable again; no honest listing is flagged High.
- − Fewer scams reach High offline until the wording check lands (next step).
- − Re-running `fair_rents.py` after a rent-table change needs `--apply-db`, `make score` and
  `export_demo_data`, in that order.
