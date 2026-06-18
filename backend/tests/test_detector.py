"""Tests for assess_listing wiring (fake text transport; no DB/network).

Verifies the full signal assembly + fusion produces sensible verdicts on a clear
scam and a clean listing. Runs locally (needs pydantic).
"""

from core.llm import RawResponse
from scam.detector import assess_listing


def _text_transport(json_text):
    def transport(system, user, schema, temperature):
        return RawResponse(text=json_text, tokens_in=10, tokens_out=5)

    return transport


_SCAMMY = (
    '{"off_platform_payment": {"present": true, "quote": "wire transfer", "confidence": 0.9}, '
    '"landlord_unavailable": {"present": true, "quote": "I am abroad", "confidence": 0.8}, '
    '"urgency_pressure": {"present": false}, "no_registration_offered": {"present": false}, '
    '"payment_before_viewing": {"present": false}, "language_assessment": "evasive"}'
)
_CLEAN = (
    '{"off_platform_payment": {"present": false}, "landlord_unavailable": {"present": false}, '
    '"urgency_pressure": {"present": false}, "no_registration_offered": {"present": false}, '
    '"payment_before_viewing": {"present": false}, "language_assessment": "normal"}'
)


def test_clear_scam_is_high():
    result = assess_listing(
        listing_id="scam",
        kiez="Mitte",
        eur_per_m2=9.0,  # ~50% below
        anmeldung_possible=False,
        median_eur_per_m2=18.0,
        mad_eur_per_m2=2.0,
        phashes=["ffffffffffffffff"],
        photo_corpus=[("victim", "ffffffffffffffff")],
        contact_text="wire the deposit, I am abroad",
        text_transport=_text_transport(_SCAMMY),
    )
    assert result.band == "high"


def test_clean_listing_is_low():
    result = assess_listing(
        listing_id="ok",
        kiez="Mitte",
        eur_per_m2=17.5,  # at market
        anmeldung_possible=True,
        median_eur_per_m2=18.0,
        mad_eur_per_m2=2.0,
        phashes=["0123456789abcdef"],
        photo_corpus=[("ok", "0123456789abcdef")],  # only its own
        contact_text="Viewings on the weekend, bring your SCHUFA.",
        text_transport=_text_transport(_CLEAN),
    )
    assert result.band == "low"
    assert result.score == 0


def test_skip_text_uses_only_rule_and_image():
    result = assess_listing(
        listing_id="x",
        kiez="Mitte",
        eur_per_m2=9.0,
        anmeldung_possible=False,
        median_eur_per_m2=18.0,
        mad_eur_per_m2=2.0,
        phashes=[None],
        photo_corpus=[],
        contact_text="anything",
        skip_text=True,  # no LLM call
    )
    # price (50% below) + no_anmeldung still fire.
    names = {s.name for s in result.signals}
    assert names == {"price_below_market", "no_anmeldung"}
