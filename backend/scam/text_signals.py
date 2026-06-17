"""Scam text pass (scam_text.v1) — the LLM signal source (ADR-0002, SPEC F7 AC2).

Reads a listing's contact/description text and extracts the *fuzzy*, language-based
scam signals the rules can't: off-platform payment, landlord-abroad, urgency, no-
registration, payment-before-viewing — each as a validated structured object with a
verbatim evidence quote and a confidence. It does NOT output a verdict; `to_signals`
converts the findings into the shared `Signal` shape (source="llm") for fusion.

On invalid model output the client falls back to "no text signals" (all present=
False), so the rule + image signals still produce a score (graceful degradation).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.llm import Transport, generate_structured
from scam.signals import Signal

SCAM_TEXT_PROMPT_ID = "scam_text.v1"

SCAM_TEXT_SYSTEM = """\
You analyze the text of a Berlin rental listing (description + any landlord contact \
message) and extract specific, well-known rental-scam signals. You are ONE input to a \
larger risk engine; you do NOT output a verdict or score.

For each signal: decide if it is present; if so, quote the exact span of text \
(verbatim) and give a confidence 0..1.

Signals:
- off_platform_payment: pressure to pay via wire transfer, Western Union, MoneyGram, \
crypto, or gift cards — outside a normal viewing-then-contract process.
- landlord_unavailable: claims of being abroad / unable to show the flat in person / \
promising to mail or courier the keys.
- urgency_pressure: manufactured urgency — "many applicants", "decide today", "first \
to pay gets it".
- no_registration_offered: states or implies you cannot do Anmeldung at the address.
- payment_before_viewing: any deposit or rent demanded before an in-person viewing.
- language_assessment: one short phrase — "generic", "machine-translated", "evasive", \
or "normal".

Rules:
- Output ONLY the JSON object matching the schema. No prose.
- Base every present:true on actual text. If unsupported, present:false, quote:null.
- Do NOT infer scams from price — price is handled elsewhere. Judge the text only.
- A legitimate listing can be cheap, brief, or from a landlord who travels. Do not \
over-flag; reserve high confidence for clearly suspicious language.
"""


class TextSignal(BaseModel):
    present: bool = False
    quote: str | None = None
    confidence: float = 0.0


class ScamTextSignals(BaseModel):
    off_platform_payment: TextSignal = Field(default_factory=TextSignal)
    landlord_unavailable: TextSignal = Field(default_factory=TextSignal)
    urgency_pressure: TextSignal = Field(default_factory=TextSignal)
    no_registration_offered: TextSignal = Field(default_factory=TextSignal)
    payment_before_viewing: TextSignal = Field(default_factory=TextSignal)
    language_assessment: str = "normal"


_DESCRIPTIONS = {
    "off_platform_payment": "Off-platform payment requested",
    "landlord_unavailable": "Landlord claims to be away / cannot show the flat",
    "urgency_pressure": "Manufactured urgency",
    "no_registration_offered": "Anmeldung not possible at this address",
    "payment_before_viewing": "Payment demanded before any viewing",
}


def analyze_text(contact_text: str, *, transport: Transport | None = None) -> ScamTextSignals:
    """Extract fuzzy scam signals from a listing's text."""
    if not contact_text or not contact_text.strip():
        return ScamTextSignals()  # nothing to analyze
    return generate_structured(
        prompt_id=SCAM_TEXT_PROMPT_ID,
        system=SCAM_TEXT_SYSTEM,
        user=contact_text,
        schema=ScamTextSignals,
        temperature=0.2,
        fallback=ScamTextSignals,  # no text signals → rules/images still score
        transport=transport,
    ).data


def to_signals(result: ScamTextSignals) -> list[Signal]:
    """Convert the present text signals into the shared Signal shape for fusion."""
    signals: list[Signal] = []
    for name, description in _DESCRIPTIONS.items():
        text_signal: TextSignal = getattr(result, name)
        if text_signal.present:
            evidence = f'"{text_signal.quote}"' if text_signal.quote else description
            signals.append(
                Signal(
                    name=name,
                    severity=max(0.0, min(1.0, text_signal.confidence)),
                    source="llm",
                    evidence=evidence,
                )
            )
    return signals
