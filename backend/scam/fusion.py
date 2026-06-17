"""Risk fusion (T3.4) — combine all signals into an explained score (SPEC F7 AC3).

Takes the contributing signals from every source (rules, images, LLM text) and fuses
them into a single 0–100 risk score, a Low/Caution/High band, and the list of signals
that drove it — so the UI can always show *why*.

Combination is a weighted **noisy-OR**: risk = 1 − ∏(1 − severityᵢ·weightₛₒᵤᵣ꜀ₑ). This
is bounded [0,1], naturally rises as more independent signals fire, and never lets a
single signal claim absolute certainty (source weights < 1). It's explainable, which
is the point — every point of the score traces to a listed signal.

Safeguard (see the photo-reuse discussion): a listing whose *only* signal is photo
reuse is likely the genuine "victim" whose photos were copied, so it's capped at
Caution. Attributing reuse to the newer listing via `created_at` is an orchestrator
concern (it knows the matched listing) and is applied before fusion by omitting the
photo-reuse signal for the original.
"""

from __future__ import annotations

from dataclasses import dataclass

from scam.signals import Signal

# Source weights (<1 so no single signal => certainty). Text is fuzzier than a hard rule.
SOURCE_WEIGHTS = {"rule": 0.9, "image": 0.85, "llm": 0.85}

HIGH_THRESHOLD = 70
CAUTION_THRESHOLD = 40
PHOTO_REUSE_CEILING = 60  # photo-reuse-alone can't exceed Caution


@dataclass
class RiskResult:
    score: int  # 0..100
    band: str  # "low" | "caution" | "high"
    signals: list[Signal]


def _clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, x))


def _band(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= CAUTION_THRESHOLD:
        return "caution"
    return "low"


def fuse(
    signals: list[Signal],
    *,
    source_weights: dict[str, float] | None = None,
) -> RiskResult:
    """Fuse contributing signals into a risk score, band, and the signal list."""
    weights = source_weights or SOURCE_WEIGHTS

    product = 1.0
    for s in signals:
        contribution = _clamp(s.severity * weights.get(s.source, 1.0))
        product *= 1.0 - contribution
    score = round((1.0 - product) * 100)

    # Safeguard: photo-reuse on its own tops out at Caution (likely the victim).
    names = {s.name for s in signals}
    if names and names <= {"photo_reuse"}:
        score = min(score, PHOTO_REUSE_CEILING)

    return RiskResult(score=score, band=_band(score), signals=list(signals))
