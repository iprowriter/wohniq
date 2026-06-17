"""Unit tests for risk fusion (pure, no DB/API)."""

from scam.fusion import PHOTO_REUSE_CEILING, RiskResult, fuse
from scam.signals import Signal


def _sig(name, severity, source):
    return Signal(name=name, severity=severity, source=source, evidence="…")


def test_no_signals_is_zero_low():
    r = fuse([])
    assert r.score == 0 and r.band == "low"


def test_single_strong_rule_is_high_but_not_certain():
    r = fuse([_sig("price_below_market", 1.0, "rule")])
    assert r.score == 90  # severity 1.0 × weight 0.9
    assert r.band == "high"


def test_stacking_signals_raises_score():
    one = fuse([_sig("price_below_market", 0.6, "rule")]).score
    two = fuse(
        [_sig("price_below_market", 0.6, "rule"), _sig("no_anmeldung", 0.6, "rule")]
    ).score
    assert two > one  # noisy-OR is monotonic


def test_full_scam_is_high():
    r = fuse([
        _sig("price_below_market", 1.0, "rule"),
        _sig("no_anmeldung", 0.6, "rule"),
        _sig("off_platform_payment", 0.9, "llm"),
        _sig("photo_reuse", 0.9, "image"),
    ])
    assert r.band == "high"
    assert r.score >= 95
    assert len(r.signals) == 4  # contributing signals preserved


def test_photo_reuse_alone_capped_at_caution():
    r = fuse([_sig("photo_reuse", 0.9, "image")])
    assert r.score <= PHOTO_REUSE_CEILING
    assert r.band == "caution"  # the genuine victim is never marked High


def test_photo_reuse_with_other_signals_not_capped():
    r = fuse([
        _sig("photo_reuse", 0.9, "image"),
        _sig("price_below_market", 1.0, "rule"),
    ])
    assert r.score > PHOTO_REUSE_CEILING
    assert r.band == "high"


def test_band_thresholds():
    # A mid-severity single rule lands in caution.
    r = fuse([_sig("no_anmeldung", 0.6, "rule")])
    assert r.band == "caution"
