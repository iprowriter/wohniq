"""Explanation layer (explain.v1) — grounded rationale from the ranking breakdown (F4).

The LLM writes the prose, but ONLY from the structured factor breakdown the ranker
produced — so every claim traces to a real number and nothing is invented (ADR-0001,
SPEC F4). If the model fails validation, a deterministic template assembles an
explanation from the same factors, so the UI always has one. Prompt mirrors
docs/system_prompts.md (explain.v1).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.llm import Transport, generate_structured
from search.explain_rules import select_reasons_and_caveats, summary_lead
from search.ranking import RankingResult

EXPLAIN_PROMPT_ID = "explain.v1"

EXPLAIN_SYSTEM = """\
You explain to a Berlin apartment seeker why a specific listing fits what they asked \
for. You are given a structured breakdown of how this listing scored on each factor. \
Write ONLY from those factors.

Rules:
- Output ONLY the JSON object (summary, reasons, caveats). No prose outside it.
- Every reason and caveat MUST reference a concrete value from the breakdown \
(minutes, euros, counts, nightlife level). Do NOT invent facts not present in the input.
- Focus on the meaningful factors: budget, commute, quiet, amenities. Ignore internal \
relevance scores.
- Be warm but factual. No marketing fluff, no exclamation marks.
- If a factor scored poorly (over budget, long commute, lively area when quiet was \
wanted), state it honestly in caveats — do not hide trade-offs.
- summary: 1-2 sentences. reasons: 2-4 items. caveats: 0-2 items.
"""


class Explanation(BaseModel):
    summary: str
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


def _factor_tuples(result: RankingResult) -> list[tuple[str, float, float, str]]:
    return [(f.name, f.score, f.weight, f.detail) for f in result.factors]


def _breakdown_text(result: RankingResult) -> str:
    lines = [f"Overall match score: {result.total:.2f}", "Factors:"]
    for f in result.factors:
        if f.name == "relevance":
            continue
        lines.append(f"- {f.name}: {f.detail} (score {f.score:.2f})")
    return "\n".join(lines)


def template_fallback(result: RankingResult) -> Explanation:
    """Deterministic explanation from the same breakdown (no LLM)."""
    reasons, caveats = select_reasons_and_caveats(_factor_tuples(result))
    return Explanation(
        summary=f"{summary_lead(result.total)} for your search.",
        reasons=reasons or ["Matches your search."],
        caveats=caveats,
    )


def explain(result: RankingResult, *, transport: Transport | None = None) -> Explanation:
    """Generate a grounded explanation for a ranked listing."""
    return generate_structured(
        prompt_id=EXPLAIN_PROMPT_ID,
        system=EXPLAIN_SYSTEM,
        user=_breakdown_text(result),
        schema=Explanation,
        temperature=0.5,
        fallback=lambda: template_fallback(result),
        transport=transport,
    ).data
