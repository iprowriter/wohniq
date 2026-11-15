# ADR-0014 — Area-aware search: Berlin areas are a hard filter, with a labelled nearby fallback

**Status:** Accepted · **Date:** 2026-11-14 · Amends [ADR-0008](0008-offline-commute-estimate.md) decision 6

## Context

`SearchCriteria` had no area field. "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow"
parsed to just `quiet_priority=true`; the districts were dropped and users got flats from the
other side of the city (reproduced: "a quiet flat in Mitte" returned Lichtenberg, Spandau,
Treptow and Schöneberg but not a single Mitte flat; "Xberg or Friedrichshain" returned
Neukölln). Two related gaps: an empty result page never said *why* (usually the budget), and
every explanation read "A strong match for your search." with no reason.

## Decision

1. **A gazetteer, in code** (`search/areas.py`, stdlib only): the 12 Bezirke, all 96
   Ortsteile, and common Kiez names and nicknames ("P'berg", "Xberg", "SO36", "Fhain",
   "Kreuzkölln", "Kollwitzkiez", …). Matching folds case, umlauts (ö/oe/o), ß, hyphens and
   apostrophes, missing spaces ("Prenzlauerberg") and small typos in long names.
2. **A bare name means the Ortsteil.** "Mitte" is central Mitte, not Wedding or Moabit;
   "Pankow" is not Prenzlauer Berg. Whole districts are selected by their compound name
   ("Friedrichshain-Kreuzberg") or explicitly ("Bezirk Mitte", "Mitte district"). This is
   how Berliners talk, and the strict reading is what makes "only these areas" trustworthy.
3. **Context decides the role of a mention**: *want* (filter to it), *avoid* ("not
   Neukölln", "anywhere but Marzahn" → `excluded_areas`) or *work* ("I work in Mitte" →
   commute target, never a living area). List continuations inherit the role.
   Workplace wording: work/office/job/employer, commute to, study/university/college/PhD,
   internship/apprenticeship/Ausbildung/trainee, teacher/lecturer (within three words of
   the place), teach/teaching (four: "I teach at a school in Neukölln") and "student
   at/in". Deliberately *not* workplace words: "school" alone ("near a good school in
   Pankow" is a family choosing where to live) and "student" describing the flat ("a
   student room in Mitte").
4. **Parser: the LLM extracts, code reconciles** (`parser.v2`). The model returns
   `areas`/`excluded_areas`; a validator canonicalises them; `merge_areas` unions them with
   the deterministic scan and removes workplace/avoided areas. A nickname the model misses
   still filters; a workplace the model misfiles never does. The work location follows
   the keyword parser's rule (`parse_rules.resolve_workplace`), shared so both paths
   decide the same way: the model's `work_location` is dropped when it is a Berlin area
   the text doesn't describe as a workplace, and if the model missed a workplace area the
   text does name ("internship in Mitte"), that area is added. Only areas the text
   explicitly calls a workplace are added — not a loose "near X" landmark, where the
   model's judgement is kept ("close to Görlitzer Park" is not a workplace).
5. **Areas are a hard filter** in retrieval (SQL `WHERE kiez IN … OR district IN …`; the
   demo repository applies the same semantics in Python, and a test checks both agree on all
   demo listings).
6. **Nearby fallback, clearly labelled.** Only if *nothing* matches inside the requested
   areas do we show the closest matching listings within `NEARBY_MAX_KM` = 6 km of a
   requested area's centre (≈ the adjacent Ortsteile). Each card says "Near Mitte · 1.9 km",
   the area factor scores ≤ 0.4 (always a caveat), and a notice explains why. If nothing is
   within 6 km, the page says so and names the closest area that has matches rather than
   silently stretching "nearby".
7. **Budget diagnosis** (`search/diagnostics.py`). When the budget empties the results (no
   listing matching everything else is within budget), a `budget_too_low` notice gives the
   cheapest price and a recommended minimum (rounded up to €10), plus a budget that would
   show ~3 options. **High-risk listings are ignored** for this: a price-bait scam must never
   set the recommended budget. If some requested areas are entirely above budget while
   others have results, that is reported too. The UI offers one-click "Search with €X"
   (request field `max_warm_rent` overrides the parsed budget).
8. **Explanations say why** (`explain.v2`). Each ranking factor carries a short highlight;
   the summary names the strongest ones ("A strong match: in Lichtenberg, €471 under your
   €1.000 budget and a quiet Kiez with little nightlife.") and admits the main trade-off
   (", but Mitte is lively, with lots of nightlife"). Generic grade-only summaries fail
   validation, so the LLM is re-prompted and the template is the fallback.

### Amendment to ADR-0008 decision 6

ADR-0008 accepted the keyword parser reading "quiet flat near Mitte" as a work location.
That is reversed **for names that are Berlin areas**: "near Mitte" is where the user wants to
live (an area), unless the text says it's the workplace ("I work near Mitte", "commute to
Mitte"). Landmarks that aren't areas ("near Alexanderplatz") are still work locations.

The rule applies to both parser paths. (Update, 2026-11-14, after review: it was first
enforced only in the keyword parser; with Gemini it depended on the model following the
prompt, and a model answer of `work_location: "Mitte"` still produced a commute to Mitte.
`merge_areas` now applies the same function to the model's answer. A follow-up closed
the reverse gap: a workplace area the model missed is now added from the text, so "doing an
internship in Mitte" gets commute times to Mitte whether or not the model returned it.)

Side effect, also intended: text that *does* name a workplace area is now understood by the
keyword parser ("I work in Mitte", "my office is in Kreuzberg", "good commute to Mitte");
before, it produced no work location and therefore no commute.

## Alternatives considered

- **Soft area boost instead of a filter.** Rejected: it reproduces the bug whenever other
  factors outweigh the boost, which is exactly what users complained about.
- **Bare "Mitte" = Bezirk Mitte.** Rejected as the default (returns Wedding for "Mitte"),
  kept available as "Bezirk Mitte".
- **Geocoding area names / point-in-polygon on LOR outlines.** More precise, but listings
  already carry Kiez and Bezirk, and the outlines only cover Bezirksregionen, not Ortsteile.
  The approximate Ortsteil centres are used only to order and label nearby results.

## Consequences

- \+ Results respect the requested areas in both live and demo mode; every result is
  labelled in-area or nearby with a distance.
- \+ Empty pages explain themselves and offer a concrete budget.
- − The gazetteer is hand-maintained; new nicknames need an alias (one line + a test).
- − Distances are from approximate Ortsteil centres (±~1 km), fine for "nearby" ordering,
  not for precise geometry.
- − Up to two extra retrievals per search when results are empty or areas+budget are set
  (bounded at 500 rows; the query embedding is computed once per request).
