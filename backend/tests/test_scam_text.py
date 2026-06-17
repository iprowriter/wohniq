"""Tests for the scam text pass: LLM path, fallback, and Signal conversion."""

from core.llm import RawResponse
from scam.text_signals import ScamTextSignals, TextSignal, analyze_text, to_signals


def _transport_returning(*texts):
    calls = iter(texts)

    def transport(system, user, schema, temperature):
        return RawResponse(text=next(calls), tokens_in=30, tokens_out=15)

    return transport


VALID = (
    '{"off_platform_payment": {"present": true, "quote": "transfer via Western Union", '
    '"confidence": 0.9}, "landlord_unavailable": {"present": true, "quote": "I am abroad", '
    '"confidence": 0.8}, "urgency_pressure": {"present": false}, '
    '"no_registration_offered": {"present": false}, '
    '"payment_before_viewing": {"present": true, "quote": "deposit before the viewing", '
    '"confidence": 0.85}, "language_assessment": "evasive"}'
)


def test_llm_path_parses_signals():
    result = analyze_text("…scammy text…", transport=_transport_returning(VALID))
    assert result.off_platform_payment.present is True
    assert result.language_assessment == "evasive"


def test_empty_text_short_circuits():
    # No transport call needed; returns all-absent.
    result = analyze_text("   ")
    assert result.off_platform_payment.present is False


def test_falls_back_to_empty_on_bad_output():
    result = analyze_text("text", transport=_transport_returning("nope", "still nope"))
    assert isinstance(result, ScamTextSignals)
    assert all(
        not getattr(result, n).present
        for n in ("off_platform_payment", "landlord_unavailable", "payment_before_viewing")
    )


def test_to_signals_maps_present_only():
    result = analyze_text("…", transport=_transport_returning(VALID))
    signals = to_signals(result)
    names = {s.name for s in signals}
    assert names == {"off_platform_payment", "landlord_unavailable", "payment_before_viewing"}
    assert all(s.source == "llm" for s in signals)
    off = next(s for s in signals if s.name == "off_platform_payment")
    assert off.severity == 0.9
    assert "Western Union" in off.evidence


def test_to_signals_uses_description_when_no_quote():
    result = ScamTextSignals(urgency_pressure=TextSignal(present=True, confidence=0.5))
    signals = to_signals(result)
    assert signals[0].evidence == "Manufactured urgency"
