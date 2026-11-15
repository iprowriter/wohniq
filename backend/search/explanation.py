"""Explanation layer (explain.v1) — grounded rationale from the ranking breakdown (F4).

The LLM writes the prose, but ONLY from the structured factor breakdown the ranker
produced — so every claim traces to a real number and nothing is invented (ADR-0001,
SPEC F4). If the model fails validation, a deterministic template assembles an
explanation from the same factors, so the UI always has one. Prompt mirrors
docs/system_prompts.md (explain.v2).

v2: the summary must say *why* it's a match — naming the strongest matched criteria
with their values — instead of a bare "A strong match for your search." The model
also sees the listing facts and the hard requirements it meets (rooms, size,
furnished), and a summary that only grades the match fails validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from core.llm import Transport, generate_structured
from search.explain_rules import (
    GENERIC_SUMMARY,
    MatchContext,
    compose_summary,
    requirement_reasons,
    select_reasons_with_requirements,
)
from search.ranking import RankingResult, euro

EXPLAIN_PROMPT_ID = "explain.v2"

EXPLAIN_SYSTEM = """\
You explain to a Berlin apartment seeker why a specific listing fits what they asked \
for. You are given a structured breakdown of how this listing scored on each factor. \
Write ONLY from those factors.

Rules:
- Output ONLY the JSON object (summary, reasons, caveats). No prose outside it.
- Every reason and caveat MUST reference a concrete value from the breakdown \
(minutes, euros, counts, nightlife level). Do NOT invent facts not present in the input.
- Focus on the meaningful factors: area, budget, commute, quiet, amenities, and the \
requirements met (rooms, size, furnished). Ignore internal relevance scores.
- summary: say WHY it matches — name the 1-3 strongest matched criteria with their \
values (e.g. "A strong match: in Lichtenberg as you asked, €471 under your €1.000 \
budget, in a quiet Kiez."). Write euro amounts like the breakdown does (€1.000). \
Never write only "A strong match for your search".
- If the area factor says the listing is NOT in the areas they asked for, the summary \
must say it is nearby/outside those areas and how far.
- Be warm but factual. No marketing fluff, no exclamation marks.
- If a factor scored poorly (over budget, long commute, lively area when quiet was \
wanted), state it honestly in caveats — do not hide trade-offs.
- summary: 1-2 sentences. reasons: 2-4 items. caveats: 0-2 items.
"""


class Explanation(BaseModel):
    summary: str
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def _must_give_context(cls, value: str) -> str:
        if GENERIC_SUMMARY.match(value):
            raise ValueError(
                "summary only grades the match; name the criteria it matches and their values"
            )
        return value


def _factor_tuples(result: RankingResult) -> list[tuple[str, float, float, str]]:
    return [(f.name, f.score, f.weight, f.detail) for f in result.factors]


def _listing_line(ctx: MatchContext) -> str | None:
    parts = []
    if ctx.rooms is not None:
        parts.append(f"{ctx.rooms:g} rooms")
    if ctx.size_m2 is not None:
        parts.append(f"{ctx.size_m2} m²")
    if ctx.warm_rent is not None:
        parts.append(f"{euro(ctx.warm_rent)} warm")
    if ctx.kiez:
        parts.append(f"in {ctx.kiez}")
    return f"Listing: {', '.join(parts)}" if parts else None


def _breakdown_text(result: RankingResult, context: MatchContext | None = None) -> str:
    lines = [f"Overall match score: {result.total:.2f}"]
    if context is not None:
        listing = _listing_line(context)
        if listing:
            lines.append(listing)
    lines.append("Factors:")
    for f in result.factors:
        if f.name == "relevance":
            continue
        lines.append(f"- {f.name}: {f.detail} (score {f.score:.2f})")
    met = requirement_reasons(context)
    if met:
        lines.append("Requirements met:")
        lines.extend(f"- {reason}" for reason, _ in met)
    return "\n".join(lines)


def _default_reason(result: RankingResult) -> str:
    area = next((f for f in result.factors if f.name == "area"), None)
    if area is not None and area.highlight:
        return f"Among the closest flats we have {area.highlight}"
    return "Matches the description in your search."


def template_fallback(result: RankingResult, context: MatchContext | None = None) -> Explanation:
    """Deterministic explanation from the same breakdown (no LLM)."""
    reasons, caveats = select_reasons_with_requirements(_factor_tuples(result), context)
    highlights = [(f.name, f.score, f.weight, f.detail, f.highlight) for f in result.factors]
    return Explanation(
        summary=compose_summary(result.total, highlights, context),
        reasons=reasons or [_default_reason(result)],
        caveats=caveats,
    )


def explain(
    result: RankingResult,
    context: MatchContext | None = None,
    *,
    transport: Transport | None = None,
) -> Explanation:
    """Generate a grounded explanation for a ranked listing."""
    return generate_structured(
        prompt_id=EXPLAIN_PROMPT_ID,
        system=EXPLAIN_SYSTEM,
        user=_breakdown_text(result, context),
        schema=Explanation,
        temperature=0.5,
        fallback=lambda: template_fallback(result, context),
        transport=transport,
    ).data
