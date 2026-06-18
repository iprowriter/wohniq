"""Detector orchestration — assemble all signal sources and fuse (M3).

Ties together the three sources for one listing — rule signals (price, Anmeldung),
the photo-duplicate signal, and the LLM text signals — and fuses them into a
RiskResult. The data-gathering (Kiez stats, photo corpus) is the caller's job (the
eval and, later, the search/scoring pipeline); this function takes facts, so it's
easy to test with a fake text transport.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.llm import Transport
from scam.fusion import RiskResult, fuse
from scam.photo_dups import duplicate_photo_signal
from scam.signals import rule_signals
from scam.text_signals import analyze_text, to_signals


def assess_listing(
    *,
    listing_id: str,
    kiez: str,
    eur_per_m2: float,
    anmeldung_possible: bool,
    median_eur_per_m2: float,
    mad_eur_per_m2: float,
    phashes: Iterable[str | None],
    photo_corpus: Iterable[tuple[str, str | None]],
    contact_text: str,
    skip_text: bool = False,
    text_transport: Transport | None = None,
) -> RiskResult:
    """Run all signal sources for one listing and fuse them into a risk result."""
    signals = rule_signals(
        kiez=kiez,
        eur_per_m2=eur_per_m2,
        anmeldung_possible=anmeldung_possible,
        median_eur_per_m2=median_eur_per_m2,
        mad_eur_per_m2=mad_eur_per_m2,
    )

    dup = duplicate_photo_signal(listing_id=listing_id, phashes=phashes, corpus=photo_corpus)
    if dup is not None:
        signals.append(dup)

    if not skip_text:
        signals += to_signals(analyze_text(contact_text, transport=text_transport))

    return fuse(signals)
