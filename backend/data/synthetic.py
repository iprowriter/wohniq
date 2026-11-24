"""Pure synthetic-listing generation — no database, no third-party deps.

Deliberately stdlib-only so the generation logic is unit-testable without a DB or
network (the DB write lives in seed_listings.py). Generation is fully deterministic
for a given seed, so listings, prices, ids, and the scam labels reproduce exactly —
which the eval harness (M3) relies on.

Produces three kinds of listing:
  * legit            — normal listings across the Kiez/price range.
  * scam             — labeled, one of SCAM_TYPES, with the linguistic/price/photo
                       signals the detector is meant to catch (is_scam=True).
  * hard negative    — legit listings that *look* suspicious (very cheap, or a
                       landlord who's abroad) but are genuine. is_scam=False; these
                       keep the eval set from being trivially separable.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from data.kieze import KIEZE, Kiez

ROOM_CHOICES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
ROOM_WEIGHTS = [10, 12, 26, 14, 20, 8, 10]

SCAM_TYPES = ["price_bait", "advance_fee", "overseas_landlord", "photo_reuse"]

_ADJ = ["Bright", "Cozy", "Spacious", "Modern", "Charming", "Sunny", "Quiet", "Renovated"]
_FEATURES = [
    "Altbau with high ceilings and parquet floors",
    "recently renovated with a fitted kitchen",
    "quiet courtyard-facing bedroom",
    "balcony facing a leafy garden",
    "bright living room with large windows",
]
_TRANSIT = [
    "Two minutes to the U-Bahn",
    "Well connected by tram and bus",
    "Short walk to the S-Bahn",
    "Several U-Bahn lines nearby",
]
_FIRST = ["Anna", "Lukas", "Sophie", "Max", "Marie", "Jonas", "Laura", "Felix", "Mia", "Paul"]
_LAST = ["Müller", "Schmidt", "Weber", "Fischer", "Becker", "Wagner", "Hoffmann", "Schulz"]
_STREETS = [
    "Stargarder", "Boxhagener", "Torstraße", "Kastanienallee", "Sonnenallee",
    "Bergmannstraße", "Weserstraße", "Schönhauser Allee", "Kantstraße", "Turmstraße",
]
_DOMAINS = ["gmail.com", "web.de", "gmx.de", "mail.com"]

_LEGIT_CONTACT = [
    "Viewings this weekend — please bring your SCHUFA and last three payslips.",
    "Happy to arrange a viewing. Standard contract, deposit due on signing.",
    "Looking for a reliable long-term tenant. Anmeldung is no problem here.",
]


def _rooms_str(rooms: float) -> str:
    return str(int(rooms)) if float(rooms).is_integer() else str(rooms)


def _det_uuid(rng) -> uuid.UUID:
    """Seed-deterministic UUID (uuid4() uses os.urandom and would break reproducibility)."""
    return uuid.UUID(int=rng.getrandbits(128), version=4)


@dataclass
class SyntheticListing:
    id: uuid.UUID
    title: str
    description: str
    address: str
    kiez: str
    district: str
    lat: float
    lng: float
    rooms: float
    size_m2: int
    kaltmiete_eur: int
    nebenkosten_eur: int
    deposit_eur: int
    furnished: bool
    available_from: date
    floor: int
    total_floors: int
    anmeldung_possible: bool
    contact_name: str
    contact_email: str
    contact_phone: str
    contact_text: str
    photo_set_id: uuid.UUID
    is_scam: bool = False
    scam_type: str | None = None
    is_hard_negative: bool = False  # manifest-only; not a DB column
    year_built: int | None = None  # derived from the id (year_built_for), not from rng

    @property
    def warmmiete_eur(self) -> int:
        return self.kaltmiete_eur + self.nebenkosten_eur

    @property
    def eur_per_m2(self) -> float:
        return self.kaltmiete_eur / self.size_m2


# Building-age mix for the synthetic stock: roughly Berlin's rental housing (old Altbau,
# post-war, GDR/West-Berlin 1970s–80s, little 2002–2013, a recent new-build wave). Bands
# follow the Mietspiegel 2026 building-age rows; 2014+ new builds are rent-brake exempt.
_BUILD_BANDS: tuple[tuple[int, int, float], ...] = (
    (1870, 1918, 0.24),
    (1919, 1949, 0.13),
    (1950, 1964, 0.13),
    (1965, 1972, 0.08),
    (1973, 1990, 0.17),
    (1991, 2001, 0.10),
    (2002, 2013, 0.04),
    (2014, 2024, 0.11),
)


# Rent overrides set against the Mietspiegel (data/berlin/fair_rents.py, ADR-0017): some
# honest listings at fair rents, price-bait scams below the index. Applied by id, after
# generation, so nothing else changes. Missing file = the generator's own prices.
OVERRIDES_PATH = Path(__file__).parent / "demo" / "rent_overrides.json"


def _rent_overrides() -> dict[str, dict]:
    try:
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def year_built_for(listing_id: uuid.UUID) -> int:
    """Deterministic building year from the listing id.

    Hash-based on purpose: it consumes nothing from the generator's rng, so adding it left
    every other field (and every scam label) of the seeded listings unchanged.
    """
    digest = hashlib.sha256(listing_id.bytes).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    v = int.from_bytes(digest[8:16], "big") / 2**64
    edge = 0.0
    for start, end, weight in _BUILD_BANDS:
        edge += weight
        if u < edge:
            return start + int(v * (end - start + 1))
    start, end, _ = _BUILD_BANDS[-1]
    return start + int(v * (end - start + 1))


def _make_listing(
    rng, ref: date, *, scam_type: str | None = None, hard_negative: str | None = None
) -> SyntheticListing:
    kiez: Kiez = rng.choice(KIEZE)
    rooms = rng.choices(ROOM_CHOICES, weights=ROOM_WEIGHTS, k=1)[0]
    size_m2 = max(18, round(rooms * rng.uniform(18, 26) + rng.uniform(-5, 8)))

    # Base cold rent from the Kiez rate, with per-listing variation.
    base = kiez.cold_eur_per_m2 * rng.uniform(0.9, 1.15)
    kalt = round(base * size_m2)
    if scam_type == "price_bait":
        kalt = round(kalt * rng.uniform(0.40, 0.55))  # implausibly cheap
    elif hard_negative == "cheap":
        kalt = round(kalt * rng.uniform(0.68, 0.78))  # cheap but plausible

    nebenkosten = round(size_m2 * rng.uniform(2.8, 3.6))
    deposit = 3 * kalt  # Kaution capped at 3× cold rent

    first, last = rng.choice(_FIRST), rng.choice(_LAST)
    adj = rng.choice(_ADJ)
    rs = _rooms_str(rooms)

    title = f"{adj} {rs}-room in {kiez.name}"
    description = (
        f"{adj} {rs}-room apartment in {kiez.name}, {size_m2} m². "
        f"{rng.choice(_FEATURES).capitalize()}. {rng.choice(_TRANSIT)}."
    )
    anmeldung = True
    contact_text = rng.choice(_LEGIT_CONTACT)

    if scam_type == "price_bait":
        contact_text = (
            "Incredible price for this area — it won't last! Several people are "
            "interested, so the first to confirm secures it today."
        )
        if rng.random() < 0.5:
            anmeldung = False
            contact_text += " Unfortunately Anmeldung is not possible at this address."
    elif scam_type == "advance_fee":
        contact_text = (
            "To reserve the flat, please transfer the Kaution by bank wire before the "
            "viewing. Once I receive the payment I will send the keys by courier."
        )
        if rng.random() < 0.5:
            anmeldung = False
    elif scam_type == "overseas_landlord":
        contact_text = (
            "I am currently abroad for work and cannot show the flat in person. After "
            "you send the first month plus deposit via Western Union, I will DHL the "
            "keys to you."
        )
    elif scam_type == "photo_reuse":
        contact_text = "Lovely flat, available now. Message me for more details."
    elif hard_negative == "cheap":
        description += " Priced slightly below market — we want a quick, reliable Nachmieter."
        contact_text = "Genuine quick handover wanted. Standard contract, viewings on request."
    elif hard_negative == "travel":
        contact_text = (
            "I work abroad, but my local agent handles all viewings. Deposit is due "
            "only after you sign in person — no upfront payments of any kind."
        )

    return SyntheticListing(
        id=_det_uuid(rng),
        title=title,
        description=description,
        address=f"{rng.choice(_STREETS)} {rng.randint(1, 180)}, "
        f"{rng.randint(10115, 13599)} Berlin",
        kiez=kiez.name,
        district=kiez.district,
        lat=round(kiez.lat + rng.uniform(-0.012, 0.012), 6),
        lng=round(kiez.lng + rng.uniform(-0.012, 0.012), 6),
        rooms=rooms,
        size_m2=size_m2,
        kaltmiete_eur=kalt,
        nebenkosten_eur=nebenkosten,
        deposit_eur=deposit,
        furnished=rng.random() < 0.25,
        available_from=ref + timedelta(days=rng.randint(0, 90)),
        floor=rng.randint(0, 6),
        total_floors=rng.randint(4, 8),
        anmeldung_possible=anmeldung,
        contact_name=f"{first} {last}",
        contact_email=f"{first.lower()}.{last.lower()}@{rng.choice(_DOMAINS)}",
        contact_phone=f"+49 30 {rng.randint(1000000, 9999999)}",
        contact_text=contact_text,
        photo_set_id=_det_uuid(rng),
        is_scam=scam_type is not None,
        scam_type=scam_type,
        is_hard_negative=hard_negative is not None,
    )


def generate_listings(
    count: int = 100,
    *,
    seed: int = 42,
    scam_ratio: float = 0.15,
    hard_negative_ratio: float = 0.08,
    reference_date: date | None = None,
    apply_overrides: bool = True,
) -> list[SyntheticListing]:
    """Generate `count` listings deterministically for `seed`.

    `scam_ratio` of them are labeled scams; `hard_negative_ratio` are legit-but-tricky.
    """
    rng = random.Random(seed)
    ref = reference_date or date.today()

    n_scam = round(count * scam_ratio)
    n_hard = round(count * hard_negative_ratio)
    n_legit = count - n_scam - n_hard

    # Balance scam types (and hard-negative kinds) round-robin so every detector
    # signal gets enough positive examples — random choice left some types starved.
    specs: list[tuple[str, str | None]] = []
    specs += [("scam", SCAM_TYPES[i % len(SCAM_TYPES)]) for i in range(n_scam)]
    specs += [("hard", ("cheap", "travel")[i % 2]) for i in range(n_hard)]
    specs += [("legit", None)] * n_legit
    rng.shuffle(specs)

    listings: list[SyntheticListing] = []
    for kind, sub in specs:
        if kind == "scam":
            listings.append(_make_listing(rng, ref, scam_type=sub))
        elif kind == "hard":
            listings.append(_make_listing(rng, ref, hard_negative=sub))
        else:
            listings.append(_make_listing(rng, ref))

    # Resolve photo-reuse scams: point them at a genuine listing's photo set.
    genuine = [x for x in listings if not x.is_scam]
    for listing in listings:
        if listing.scam_type == "photo_reuse" and genuine:
            listing.photo_set_id = rng.choice(genuine).photo_set_id

    overrides = _rent_overrides() if apply_overrides else {}
    for listing in listings:
        listing.year_built = year_built_for(listing.id)
        override = overrides.get(str(listing.id))
        if override:
            listing.kaltmiete_eur = override["kaltmiete_eur"]
            listing.deposit_eur = 3 * listing.kaltmiete_eur  # Kaution: 3x cold rent
    return listings


def manifest_entry(listing: SyntheticListing) -> dict:
    """Flat, JSON-serializable label record for the eval harness (M3)."""
    return {
        "id": str(listing.id),
        "kiez": listing.kiez,
        "rooms": listing.rooms,
        "size_m2": listing.size_m2,
        "kaltmiete_eur": listing.kaltmiete_eur,
        "warmmiete_eur": listing.warmmiete_eur,
        "is_scam": listing.is_scam,
        "scam_type": listing.scam_type,
        "is_hard_negative": listing.is_hard_negative,
    }


# --- The 40 extra listings (ADR-0018) ---------------------------------------------------
# Appended to the original 100 (which stay byte-identical): scams whose *wording* gives them
# away, in English and German; two subtle scams with no telltale phrase; three more photo
# copies; and honest listings that use the same words innocently, so the offline wording
# check is tested against both sides. Its own seed, so the first 100 never change.

EXTRA_SEED = 4242
EXTRA_COUNT = 40

_EXTRA_SCAM_TEXTS: dict[str, tuple[str, ...]] = {
    "advance_fee": (
        "To secure the flat, please transfer the deposit of {deposit} € before the viewing. "
        "After payment I send you the contract by email.",
        "Bitte überweisen Sie die Kaution vorab, danach schicke ich Ihnen den Schlüssel per "
        "Post.",
        "Payment of the first month is required before we can arrange a viewing. Many people "
        "are interested, so please act today.",
        "Send the reservation fee by bank transfer and I will hold the apartment for you; a "
        "viewing is possible after payment.",
        "Die Besichtigung ist erst nach Eingang der ersten Monatsmiete möglich. Wir "
        "akzeptieren auch Bitcoin.",
    ),
    "overseas_landlord": (
        "I moved to London for work and can't show the flat. My lawyer will send the keys by "
        "DHL once you pay the deposit.",
        "Ich bin zur Zeit beruflich in Spanien und kann die Wohnung nicht zeigen. Die "
        "Schlüssel schicke ich Ihnen nach Zahlung per DHL.",
        "I'm abroad as a volunteer right now. Pay via MoneyGram and the keys will arrive by "
        "courier within two days.",
        "Currently living overseas. Transfer the first rent and deposit through Western Union, "
        "then I mail you the keys.",
    ),
    "fake_platform": (
        "Booking is handled by a secure payment service: you pay through the link I send, and "
        "the money is held until you have the keys.",
        "Die Zahlung läuft sicher über einen Treuhandservice, ich sende Ihnen den Link. Danach "
        "erhalten Sie den Schlüssel per Post.",
    ),
    "photo_reuse": (
        "Available now. Write me on WhatsApp for more photos and details.",
        "Wohnung sofort frei. Melden Sie sich per Nachricht für weitere Infos.",
        "Great flat, just renovated. Message me if interested.",
    ),
    "subtle": (
        "Nice flat, available immediately. Send me your phone number and I'll call you back.",
        "Schöne Wohnung, ab sofort frei. Schreiben Sie mir Ihre E-Mail, ich melde mich.",
    ),
}

# Honest listings that use the scam words innocently (negated, or someone shows the flat).
_EXTRA_TRICKY_TEXTS: tuple[str, ...] = (
    "Please note: we never ask for Western Union or any transfer before you have seen the "
    "flat. Viewings every Saturday.",
    "Ich wohne im Ausland, aber meine Schwester zeigt die Wohnung, und den Vertrag "
    "unterschreiben wir persönlich. Keine Vorauszahlung.",
    "Kaution erst nach Vertragsunterzeichnung, Schlüsselübergabe persönlich vor Ort.",
    "Keys are handed over in person at the flat. We don't post keys.",
    "Many applicants, so we decide after the viewings next week. No payment before signing.",
    "I'm currently abroad for work; my property manager Herr Schulz shows the flat and you "
    "sign the contract in person.",
    "Rent is paid by standing order after the contract is signed. We never accept cash or "
    "crypto.",
    "Beware of scams: never transfer money before a viewing. We are a registered "
    "Hausverwaltung.",
    "Bitte keine Überweisung vor der Besichtigung. Wir lernen Sie gern persönlich kennen.",
    "Viewing first, then the contract, then the deposit into a rent deposit account "
    "(Mietkautionskonto).",
)


def generate_extra_listings(
    base: list[SyntheticListing],
    *,
    seed: int = EXTRA_SEED,
    reference_date: date | None = None,
) -> list[SyntheticListing]:
    """The 40 extra listings. `base` is the original 100 (photo copies take a genuine set)."""
    rng = random.Random(seed)
    ref = reference_date or date.today()
    specs: list[tuple[str, str | None, str]] = []
    for scam_type, texts in _EXTRA_SCAM_TEXTS.items():
        specs += [("scam", scam_type, t) for t in texts]
    specs += [("hard", "wording", t) for t in _EXTRA_TRICKY_TEXTS]
    n_plain = EXTRA_COUNT - len(specs)
    specs += [("legit", None, "")] * n_plain
    rng.shuffle(specs)

    genuine = [x for x in base if not x.is_scam]
    out: list[SyntheticListing] = []
    for kind, sub, text in specs:
        x = _make_listing(rng, ref)  # honest base: Kiez, size, price, contact
        if kind == "scam":
            x.is_scam, x.scam_type = True, sub
            x.contact_text = text.format(deposit=x.deposit_eur)
            if sub == "photo_reuse":
                x.photo_set_id = rng.choice(genuine).photo_set_id  # the whole set
        elif kind == "hard":
            x.is_hard_negative = True
            x.contact_text = text
        out.append(x)
    return out


def generate_catalogue(
    *, reference_date: date | None = None, apply_overrides: bool = True
) -> list[SyntheticListing]:
    """The full demo catalogue: the original 100 listings (seed 42) plus the 40 extras."""
    base = generate_listings(
        100, seed=42, reference_date=reference_date, apply_overrides=apply_overrides
    )
    extra = generate_extra_listings(base, reference_date=reference_date)
    overrides = _rent_overrides() if apply_overrides else {}
    for x in extra:
        x.year_built = year_built_for(x.id)
        override = overrides.get(str(x.id))
        if override:
            x.kaltmiete_eur = override["kaltmiete_eur"]
            x.deposit_eur = 3 * x.kaltmiete_eur
    return base + extra
