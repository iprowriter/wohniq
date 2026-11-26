"""Address search keys, shared by the build (stored keys) and queries (typed text).

"Choriner Straße 41", "choriner str. 41" and "Choriner Strasse 41" all become
"choriner str 41", so a prefix match on the key finds the address however it's typed.
"""

from __future__ import annotations

import re

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "é": "e", "è": "e"})
_STRASSE = re.compile(r"(strasse|str\b\.?)")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def search_key(text: str) -> str:
    """Lowercase, umlauts folded, 'Straße'/'Str.' → 'str', punctuation → single spaces."""
    t = text.lower().translate(_UMLAUTS)
    t = _STRASSE.sub("str ", t)
    t = _NON_WORD.sub(" ", t)
    # "Str" written as its own word after a compound ("Karl-Marx- Str") folds into it.
    return re.sub(r"\s+", " ", t).strip()


def address_key(street: str, house_number: str) -> str:
    return search_key(f"{street} {house_number}")


def clean_house_number(raw: str) -> str:
    """'004A' → '4A', '010' → '10' (the register pads numbers to three digits)."""
    m = re.fullmatch(r"0*(\d+)(.*)", raw.strip())
    return f"{m[1]}{m[2]}" if m else raw.strip()
