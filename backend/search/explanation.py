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

explain.batch.v1 (ADR-0022): the same rules for up to BATCH_SIZE listings in ONE call, so
a page of results costs one or two requests instead of one per flat. Each returned item
is validated as an `Explanation` on its own; an invalid or missing one gets the template,
the others keep the model's text.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field, ValidationError, field_validator

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


# --- Batched explanations (explain.batch.v1, ADR-0022) --------------------------------

EXPLAIN_BATCH_PROMPT_ID = "explain.batch.v1"
BATCH_SIZE = 10

EXPLAIN_BATCH_SYSTEM = (
    EXPLAIN_SYSTEM.replace("why a specific listing fits", "why each of several listings fits")
    .replace(
        "how this listing scored on each factor",
        'how each listing scored on each factor, headed "Listing #n"',
    )
    .replace(
        "- Output ONLY the JSON object (summary, reasons, caveats). No prose outside it.",
        '- Output ONLY the JSON object {"items": [...]}: one item per listing, with '
        '"ref" set to its number n and its summary, reasons and caveats. No prose '
        "outside it.\n- Each item uses ONLY its own listing's breakdown; never carry a "
        "value from one listing to another.",
    )
)


class BatchItem(BaseModel):
    """One explanation as the model returns it; checked as an `Explanation` afterwards."""

    ref: int
    summary: str
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ExplanationBatch(BaseModel):
    items: list[BatchItem]


class _Cache:
    """Model explanations by their exact input, so a repeated search costs no call."""

    def __init__(self, size: int = 1024) -> None:
        self._data: OrderedDict[str, Explanation] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def get(self, key: str) -> Explanation | None:
        with self._lock:
            hit = self._data.get(key)
            if hit is not None:
                self._data.move_to_end(key)
            return hit

    def put(self, key: str, value: Explanation) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _Cache()
_chunks = ThreadPoolExecutor(max_workers=4, thread_name_prefix="explain")


def _explain_chunk(
    texts: list[str], *, transport: Transport | None, timeout_s: float | None
) -> list[Explanation | None]:
    """One call for up to BATCH_SIZE breakdowns; None where the model gave nothing usable."""
    user = "\n\n".join(f"Listing #{i}\n{t}" for i, t in enumerate(texts, 1))
    result = generate_structured(
        prompt_id=EXPLAIN_BATCH_PROMPT_ID,
        system=EXPLAIN_BATCH_SYSTEM,
        user=user,
        schema=ExplanationBatch,
        temperature=0.5,
        fallback=lambda: ExplanationBatch(items=[]),
        transport=transport,
        timeout_s=timeout_s,
    )
    out: list[Explanation | None] = [None] * len(texts)
    for item in result.data.items:
        if not 1 <= item.ref <= len(texts) or out[item.ref - 1] is not None:
            continue  # unknown or repeated ref: ignore, that listing keeps the template
        try:
            out[item.ref - 1] = Explanation(
                summary=item.summary, reasons=item.reasons, caveats=item.caveats
            )
        except ValidationError:
            continue
    return out


def explain_many(
    items: list[tuple[RankingResult, MatchContext | None]],
    *,
    transport: Transport | None = None,
    timeout_s: float | None = None,
) -> list[tuple[Explanation, bool]]:
    """(explanation, written_by_model) per item, in order. Never raises.

    Cached explanations are reused; the rest go to the model BATCH_SIZE at a time, the
    batches in parallel. Anything the model doesn't deliver gets the template.
    """
    texts = [_breakdown_text(r, c) for r, c in items]
    out: list[tuple[Explanation, bool] | None] = [None] * len(items)
    todo: list[int] = []
    for i, t in enumerate(texts):
        hit = _cache.get(t)
        if hit is not None:
            out[i] = (hit, True)
        else:
            todo.append(i)

    groups = [todo[k : k + BATCH_SIZE] for k in range(0, len(todo), BATCH_SIZE)]
    futures = [
        _chunks.submit(
            _explain_chunk, [texts[i] for i in g], transport=transport, timeout_s=timeout_s
        )
        for g in groups
    ]
    for g, fut in zip(groups, futures, strict=True):
        for i, exp in zip(g, fut.result(), strict=True):
            if exp is not None:
                _cache.put(texts[i], exp)
                out[i] = (exp, True)

    return [
        o if o is not None else (template_fallback(r, c), False)
        for o, (r, c) in zip(out, items, strict=True)
    ]
