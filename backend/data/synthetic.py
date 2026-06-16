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

import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

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

    @property
    def warmmiete_eur(self) -> int:
        return self.kaltmiete_eur + self.nebenkosten_eur

    @property
    def eur_per_m2(self) -> float:
        return self.kaltmiete_eur / self.size_m2


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
