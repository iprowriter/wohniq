"""Tests for explain(): LLM path (fake transport) and deterministic fallback."""

from core.llm import RawResponse
from search.explanation import Explanation, explain, template_fallback
from search.ranking import FactorScore, RankingResult


def _result() -> RankingResult:
    return RankingResult(
        total=0.82,
        factors=[
            FactorScore("relevance", 0.8, 1.0, "semantic match 80%"),
            FactorScore("budget", 0.8, 1.5, "€150 under budget"),
            FactorScore("commute", 0.7, 2.0, "18 min to work"),
            FactorScore("quiet", 0.1, 1.0, "high nightlife"),
        ],
    )


def _transport_returning(*texts):
    calls = iter(texts)

    def transport(system, user, schema, temperature):
        return RawResponse(text=next(calls), tokens_in=20, tokens_out=12)

    return transport


def test_llm_path_returns_explanation():
    raw = (
        '{"summary": "A strong fit near your work.", '
        '"reasons": ["18 min to work", "€150 under budget"], '
        '"caveats": ["lively area, though you wanted quiet"]}'
    )
    out = explain(_result(), transport=_transport_returning(raw))
    assert isinstance(out, Explanation)
    assert out.summary.startswith("A strong fit")
    assert "18 min to work" in out.reasons


def test_falls_back_to_template_on_bad_output():
    out = explain(_result(), transport=_transport_returning("nope", "still nope"))
    # Template fallback is grounded in the same breakdown:
    assert "€150 under budget" in out.reasons or "18 min to work" in out.reasons
    assert "high nightlife" in out.caveats
    assert "match" in out.summary.lower() or "fit" in out.summary.lower()


def test_template_fallback_excludes_relevance():
    out = template_fallback(_result())
    assert all("semantic match" not in r for r in out.reasons)
