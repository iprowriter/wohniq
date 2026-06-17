"""Query parser (parser.v1) — free text → validated SearchCriteria (F1).

Runs the prompt through the central LLM client (structured output + validation +
one re-prompt), and falls back to the deterministic keyword extractor if the model
still can't produce valid output. The prompt mirrors docs/system_prompts.md
(parser.v1); keep the two in sync and bump the version when behavior changes.
"""

from __future__ import annotations

from core.llm import Transport, generate_structured
from search.criteria import SearchCriteria
from search.parse_rules import extract_criteria

PARSER_PROMPT_ID = "parser.v1"

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
- work_location is a place name or landmark only (e.g. "Alexanderplatz"). Do not \
geocode.
- Preserve genuine ambiguity in notes rather than guessing (e.g. "somewhere I can \
bike to work" -> notes: "wants bikeable commute").

Examples:
"I work near Alexanderplatz, budget €1,500, want a quiet neighborhood, good public \
transport, cafes nearby"
-> {"max_warm_rent": 1500, "min_rooms": null, "min_size_m2": null, \
"work_location": "Alexanderplatz", "transport_priority": true, "quiet_priority": true, \
"desired_amenities": ["cafes"], "furnished": null, "notes": null}

"2 bedroom around 60m2 in a lively area with bars, furnished"
-> {"max_warm_rent": null, "min_rooms": 2, "min_size_m2": 60, "work_location": null, \
"transport_priority": false, "quiet_priority": false, \
"desired_amenities": ["nightlife"], "furnished": true, "notes": null}
"""


def keyword_fallback(text: str) -> SearchCriteria:
    """Deterministic fallback used when the LLM can't return valid criteria."""
    return SearchCriteria(**extract_criteria(text))


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
    return result.data
