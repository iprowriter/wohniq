"""Query parser (parser.v1) — free text → validated SearchCriteria (F1).

Runs the prompt through the central LLM client (structured output + validation +
one re-prompt), and falls back to the deterministic keyword extractor if the model
still can't produce valid output. The prompt mirrors docs/system_prompts.md
(parser.v2); keep the two in sync and bump the version when behavior changes.

Areas get a deterministic second opinion (`merge_areas`): the model's list is unioned
with the gazetteer scan of the raw text, so a nickname the model missed ("P'berg")
still filters, and a workplace or an avoided area never becomes a place to live.
"""

from __future__ import annotations

from core.llm import Transport, generate_structured
from search.areas import canonical_areas
from search.criteria import SearchCriteria
from search.parse_rules import extract_areas, extract_criteria, resolve_workplace

PARSER_PROMPT_ID = "parser.v2"

PARSER_SYSTEM = """\
You convert a person's free-text description of the Berlin apartment they want into \
structured search criteria.

Rules:
- Extract only what the user actually stated or clearly implied. If a field is not \
stated, leave it null (or false for the boolean priority flags, [] for amenities). \
NEVER invent a budget, room count, or size.
- "budget of 1500" with no qualifier -> max_warm_rent = 1500 (assume warm/all-in \
unless they say cold/kalt).
- Map amenity wishes to these canonical tags ONLY: cafes, parks, supermarket, \
nightlife, gym. Drop anything that doesn't map and capture it in notes instead.
- "quiet", "calm", "not too loud", "residential" -> quiet_priority = true.
- "good transport", "close to U-Bahn", "easy commute" -> transport_priority = true.
- work_location is where they WORK or study: a place name or landmark only (e.g. \
"Alexanderplatz"). Do not geocode.
- areas: every Berlin district, neighbourhood or Kiez where they want to LIVE, as \
written or by its usual name, including nicknames (e.g. "Mitte", "Prenzlauer Berg" for \
"P'berg"/"Prenzlauerberg", "Kreuzberg" for "Xberg"/"SO36", "Neukölln", "Kreuzkölln"). \
"in X", "near X", "around X" where X is a Berlin area -> areas. Keep every area of a \
list ("Mitte, Spandau or Treptow" -> 3 areas). Never put the workplace here.
- excluded_areas: areas they do NOT want ("not Neukölln", "anywhere but Marzahn").
- Preserve genuine ambiguity in notes rather than guessing (e.g. "somewhere I can \
bike to work" -> notes: "wants bikeable commute").

Examples:
"I work near Alexanderplatz, budget €1,500, want a quiet neighborhood, good public \
transport, cafes nearby"
-> {"max_warm_rent": 1500, "min_rooms": null, "min_size_m2": null, \
"work_location": "Alexanderplatz", "transport_priority": true, "quiet_priority": true, \
"desired_amenities": ["cafes"], "furnished": null, "areas": [], "excluded_areas": [], \
"notes": null}

"a quiet flat in Mitte, Spandau, Lichtenberg, Treptow, not Neukölln, max 1.2k"
-> {"max_warm_rent": 1200, "min_rooms": null, "min_size_m2": null, \
"work_location": null, "transport_priority": false, "quiet_priority": true, \
"desired_amenities": [], "furnished": null, \
"areas": ["Mitte", "Spandau", "Lichtenberg", "Treptow"], "excluded_areas": ["Neukölln"], \
"notes": null}

"2 bedroom around 60m2 in a lively area with bars, furnished"
-> {"max_warm_rent": null, "min_rooms": 2, "min_size_m2": 60, "work_location": null, \
"transport_priority": false, "quiet_priority": false, \
"desired_amenities": ["nightlife"], "furnished": true, "areas": [], \
"excluded_areas": [], "notes": null}

"I work in Mitte, looking for a 2-room in P'berg"
-> {"max_warm_rent": null, "min_rooms": 2, "min_size_m2": null, "work_location": "Mitte", \
"transport_priority": false, "quiet_priority": false, "desired_amenities": [], \
"furnished": null, "areas": ["Prenzlauer Berg"], "excluded_areas": [], "notes": null}
"""


def keyword_fallback(text: str) -> SearchCriteria:
    """Deterministic fallback used when the LLM can't return valid criteria."""
    return SearchCriteria(**extract_criteria(text))


def merge_areas(criteria: SearchCriteria, text: str) -> SearchCriteria:
    """Reconcile the model's places with the deterministic gazetteer scan of `text`.

    wanted   = model areas ∪ text areas
    excluded = model exclusions ∪ text exclusions
    An area the text only names as the workplace ("I work in Mitte") or as one to avoid
    is removed from `wanted` even if the model put it there. The work location follows
    the keyword parser's rule (`resolve_workplace`): the model's is dropped if it's a
    Berlin area the text doesn't describe as a workplace ("quiet 2-room near Mitte"), and
    if the model missed a workplace the text names ("internship in Mitte"), it's added.
    """
    want, avoid, work = extract_areas(text)
    excluded = canonical_areas([*criteria.excluded_areas, *avoid])
    wanted = [
        a
        for a in canonical_areas([*criteria.areas, *want])
        if a not in excluded and (a in want or a not in work)
    ]
    return criteria.model_copy(
        update={
            "areas": wanted,
            "excluded_areas": excluded,
            "work_location": resolve_workplace(criteria.work_location, work),
        }
    )


def parse_query(text: str, *, transport: Transport | None = None) -> SearchCriteria:
    """Parse a free-text apartment request into validated SearchCriteria."""
    result = generate_structured(
        prompt_id=PARSER_PROMPT_ID,
        system=PARSER_SYSTEM,
        user=text,
        schema=SearchCriteria,
        temperature=0.2,
        fallback=lambda: keyword_fallback(text),
        transport=transport,
    )
    return merge_areas(result.data, text)
