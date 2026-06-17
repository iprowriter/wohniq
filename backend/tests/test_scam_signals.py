"""Unit tests for the deterministic scam signals (pure, no DB/API)."""

from scam.signals import (
    kiez_price_stats,
    no_anmeldung,
    price_below_market,
    rule_signals,
)


def test_kiez_price_stats():
    median, mad = kiez_price_stats([10.0, 12.0, 14.0, 16.0, 18.0])
    assert median == 14.0
    assert mad == 2.0  # median of |x-14| = median(4,2,0,2,4)


def test_price_below_market_fires_when_cheap():
    sig = price_below_market("Mitte", eur_per_m2=9.0, median_eur_per_m2=18.0, mad_eur_per_m2=2.0)
    assert sig is not None
    assert sig.name == "price_below_market"
    assert sig.source == "rule"
    assert sig.severity == 1.0  # 50% below → full severity
    assert "Mitte" in sig.evidence and "%" in sig.evidence


def test_price_signal_silent_at_market_rate():
    assert price_below_market("Mitte", 17.0, 18.0, 2.0) is None  # only ~6% below


def test_price_severity_scales():
    # 30% below → severity 0.6
    sig = price_below_market("X", eur_per_m2=7.0, median_eur_per_m2=10.0, mad_eur_per_m2=1.0)
    assert sig is not None
    assert abs(sig.severity - 0.6) < 1e-9


def test_no_anmeldung():
    assert no_anmeldung(True) is None
    sig = no_anmeldung(False)
    assert sig is not None and sig.severity == 0.6 and sig.source == "rule"


def test_rule_signals_aggregates_fired_only():
    signals = rule_signals(
        kiez="Mitte",
        eur_per_m2=8.0,
        anmeldung_possible=False,
        median_eur_per_m2=18.0,
        mad_eur_per_m2=2.0,
    )
    names = {s.name for s in signals}
    assert names == {"price_below_market", "no_anmeldung"}

    clean = rule_signals(
        kiez="Mitte",
        eur_per_m2=17.0,
        anmeldung_possible=True,
        median_eur_per_m2=18.0,
        mad_eur_per_m2=2.0,
    )
    assert clean == []
