"""Offline scam wording check (ADR-0018): known scam phrases in English and German.

The LLM text pass (scam_text.v1) reads tone and intent; this reads only the classic, crisp
phrases, so the scams they give away are caught without Gemini or a network. It works per
sentence and skips a sentence whose trigger is negated ("we never ask for Western Union",
"keine Überweisung vor der Besichtigung"). "I'm abroad" alone doesn't count when someone else
shows the flat or the contract is signed in person.

Signals use the LLM pass's names (off_platform_payment, payment_before_viewing,
landlord_unavailable, urgency_pressure) with source "rule"; the detector keeps the stronger
of the two when both fire, so nothing is counted twice. It never outputs a verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from scam.signals import Signal

_FLAGS = re.IGNORECASE

# Negation cues that, before a trigger in the same sentence, cancel it.
_NEGATION = re.compile(
    r"\b(never|no|not|don'?t|do not|won'?t|without|nie|niemals|kein\w*|nicht|ohne)\b"
    r"|beware|warn\w*|vorsicht|achtung",
    _FLAGS,
)

_PAY = r"(pay\w*|transfer\w*|send\w*|wire\w*|überweis\w*|zahl\w*|bezahl\w*|schick\w*)"
_MONEY = r"(deposit|kaution|rent|miete|first month|monatsmiete|fee|gebühr|money|geld|payment)"
_VIEWING = r"(viewing|view the flat|see the flat|besichtigung|besichtigen|vertragsunterzeichnung)"
_KEYS = r"(keys?|schlüssel\w*)"
_POST = (
    r"(by post|by mail|mail you|courier|dhl|ups|fedex|per post|zuschick\w*|versend\w*"
    r"|schicke\w*|post)"
)


@dataclass(frozen=True)
class Pattern:
    signal: str
    severity: float
    regex: re.Pattern


PATTERNS: tuple[Pattern, ...] = (
    # Money outside a normal contract: wire services, crypto, gift cards, payment links.
    Pattern(
        "off_platform_payment",
        0.85,
        re.compile(
            r"western\s*union|moneygram|bitcoin|\bbtc\b|\busdt\b|crypto|krypto|gift\s*cards?"
            r"|paysafecard|amazon[-\s]?gutschein|payment link|pay through the link|"
            r"(über|via|per) (den|einen) link|treuhand(service)?|escrow",
            _FLAGS,
        ),
    ),
    # Money first, viewing later (or never).
    Pattern(
        "payment_before_viewing",
        0.8,
        re.compile(
            rf"{_PAY}.{{0,60}}\b(before|prior to|vor)\b.{{0,30}}{_VIEWING}"
            rf"|{_MONEY}.{{0,40}}\b(vorab|im voraus|in advance|upfront|up front)\b"
            rf"|\b(vorab|im voraus|in advance|upfront)\b.{{0,40}}{_MONEY}"
            rf"|{_VIEWING}.{{0,50}}\b(after|once|nach|erst nach)\b.{{0,40}}"
            rf"(payment|zahlung|überweisung|eingang|you pay|paid)"
            rf"|{_MONEY}.{{0,40}}required before|reservation fee|reservierungsgebühr",
            _FLAGS,
        ),
    ),
    # Keys sent instead of handed over.
    Pattern(
        "landlord_unavailable",
        0.8,
        re.compile(rf"{_KEYS}.{{0,60}}{_POST}|{_POST}.{{0,40}}{_KEYS}", _FLAGS),
    ),
    # Manufactured urgency tied to paying.
    Pattern(
        "urgency_pressure",
        0.3,
        re.compile(
            r"first to (pay|transfer|confirm)|decide today|act today|heute noch|"
            r"wer zuerst (zahlt|überweist)|won'?t last",
            _FLAGS,
        ),
    ),
)

# "Landlord abroad" on its own is only suspicious when nobody shows the flat.
_ABROAD = re.compile(
    r"\b(i am|i'm|i live|currently|zur zeit|derzeit|ich bin|ich wohne|living)\b.{0,40}"
    r"\b(abroad|overseas|im ausland|in (london|spain|spanien|england|usa|dubai|nigeria))\b"
    r"|\bmoved to (london|spain|the us|dubai)\b",
    _FLAGS,
)
_CANT_SHOW = re.compile(
    r"(can'?t|cannot|unable to|not able to|kann (sie|die wohnung) nicht|nicht zeigen)",
    _FLAGS,
)
_SOMEONE_SHOWS = re.compile(
    r"\b(agent|property manager|hausverwaltung|verwalter|makler|sister|brother|mother|"
    r"father|friend|neighbou?r|schwester|bruder|mutter|vater|freund\w*|nachbar\w*|"
    r"colleague|kollege\w*|herr|frau)\b.{0,40}\b(show|shows|zeigt|handles|führt)\b"
    r"|sign\w* in person|persönlich unterschreib\w*|vertrag.{0,30}persönlich",
    _FLAGS,
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def _negated(sentence: str, start: int) -> bool:
    return bool(_NEGATION.search(sentence[:start]))


def _quote(sentence: str) -> str:
    return sentence if len(sentence) <= 160 else sentence[:157] + "…"


def wording_signals(text: str) -> list[Signal]:
    """Scam phrases found in the listing text, at most one signal per kind."""
    if not text or not text.strip():
        return []
    found: dict[str, Signal] = {}
    sentences = _sentences(text)
    for sentence in sentences:
        for p in PATTERNS:
            m = p.regex.search(sentence)
            if m and not _negated(sentence, m.start()) and p.signal not in found:
                found[p.signal] = Signal(p.signal, p.severity, "rule", f'"{_quote(sentence)}"')

    # Abroad + can't show, and nobody else shows it or signs in person.
    whole = " ".join(sentences)
    if "landlord_unavailable" not in found and not _SOMEONE_SHOWS.search(whole):
        for sentence in sentences:
            m = _ABROAD.search(sentence)
            if (
                m
                and not _negated(sentence, m.start())
                and (_CANT_SHOW.search(whole) or "off_platform_payment" in found)
            ):
                found["landlord_unavailable"] = Signal(
                    "landlord_unavailable", 0.6, "rule", f'"{_quote(sentence)}"'
                )
                break
    return list(found.values())


def merge(rule_signals: list[Signal], llm_signals: list[Signal]) -> list[Signal]:
    """Keep the stronger of a rule and an LLM signal with the same name."""
    by_name: dict[str, Signal] = {}
    for s in [*rule_signals, *llm_signals]:
        if s.name not in by_name or s.severity > by_name[s.name].severity:
            by_name[s.name] = s
    return list(by_name.values())
