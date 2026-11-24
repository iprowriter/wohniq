"""Offline scam wording check (ADR-0018): phrases, negations, and the whole catalogue."""

from __future__ import annotations

import pytest

from data.synthetic import generate_catalogue
from scam.detector import assess_listing
from scam.signals import Signal
from scam.wording import merge, wording_signals


def names(text: str) -> set[str]:
    return {s.name for s in wording_signals(text)}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Please pay via Western Union.", {"off_platform_payment"}),
        ("Zahlung per Paysafecard oder Amazon-Gutschein.", {"off_platform_payment"}),
        ("You pay through the link I send.", {"off_platform_payment"}),
        ("Transfer the deposit before the viewing.", {"payment_before_viewing"}),
        ("Bitte überweisen Sie die Kaution vorab.", {"payment_before_viewing"}),
        ("Die Besichtigung ist erst nach Eingang der Miete möglich.", {"payment_before_viewing"}),
        ("A viewing is possible after payment.", {"payment_before_viewing"}),
        ("I will send the keys by DHL.", {"landlord_unavailable"}),
        ("Den Schlüssel schicke ich Ihnen per Post.", {"landlord_unavailable"}),
        ("The first to confirm secures it, decide today.", {"urgency_pressure"}),
    ],
)
def test_phrases(text, expected):
    assert names(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "We never ask for Western Union or any transfer before you have seen the flat.",
        "Bitte keine Überweisung vor der Besichtigung.",
        "Beware of scams: never transfer money before a viewing.",
        "Keys are handed over in person. We don't post keys.",
        "No payment before signing. Viewing first, then the contract.",
        "Rent by standing order after signing. We never accept cash or crypto.",
    ],
)
def test_negated_mentions_dont_count(text):
    assert names(text) == set()


def test_abroad_counts_only_when_nobody_shows_the_flat():
    assert names("I'm currently abroad and can't show the flat.") == {"landlord_unavailable"}
    assert names("I'm currently abroad; my property manager Herr Schulz shows the flat.") == set()
    assert (
        names(
            "Ich wohne im Ausland, aber meine Schwester zeigt die Wohnung, und den Vertrag "
            "unterschreiben wir persönlich."
        )
        == set()
    )


def test_evidence_quotes_the_sentence():
    [sig] = wording_signals("Lovely flat. Please pay via MoneyGram. Thanks!")
    assert sig.source == "rule" and sig.evidence == '"Please pay via MoneyGram."'


def test_merge_keeps_the_stronger_signal_once():
    rule = [Signal("off_platform_payment", 0.85, "rule", "a")]
    llm = [
        Signal("off_platform_payment", 0.95, "llm", "b"),
        Signal("urgency_pressure", 0.4, "llm", "c"),
    ]
    merged = {s.name: s for s in merge(rule, llm)}
    assert merged["off_platform_payment"].severity == 0.95 and len(merged) == 2


def test_detector_uses_wording_without_the_llm():
    result = assess_listing(
        listing_id="x",
        kiez="Mitte",
        eur_per_m2=15.0,
        anmeldung_possible=True,
        median_eur_per_m2=15.0,
        mad_eur_per_m2=1.0,
        phashes=[],
        photo_corpus=[],
        contact_text="Transfer the deposit via Western Union before the viewing.",
        skip_text=True,
    )
    assert result.band == "high"
    assert {s.name for s in result.signals} == {"off_platform_payment", "payment_before_viewing"}


def test_whole_catalogue_honest_texts_are_clean_and_wording_scams_fire():
    for x in generate_catalogue():
        found = names(f"{x.description}\n{x.contact_text}")
        if not x.is_scam:
            assert found == set(), (x.contact_text, found)
        elif x.scam_type in ("advance_fee", "overseas_landlord", "fake_platform"):
            assert found - {"urgency_pressure"}, x.contact_text
        elif x.scam_type in ("photo_reuse", "subtle"):
            assert found == set()  # nothing in the words: caught (or not) by other signals
