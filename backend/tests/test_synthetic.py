"""Unit tests for the pure synthetic generator.

No DB or network required — these exercise generation invariants and determinism,
so they run in CI even without Postgres. They also pin the properties the scam
detector and ranking will depend on (e.g. price_bait really is cheap).
"""

from datetime import date
from statistics import median

from data.kieze import BERLIN_BBOX, KIEZE
from data.synthetic import ROOM_CHOICES, generate_listings

REF = date(2026, 7, 1)
KIEZ_NAMES = {k.name for k in KIEZE}


def _gen(**kw):
    return generate_listings(100, seed=42, reference_date=REF, **kw)


def test_count_and_determinism():
    a = _gen()
    b = _gen()
    assert len(a) == 100
    # Same seed → identical ids and prices.
    assert [x.id for x in a] == [x.id for x in b]
    assert [x.kaltmiete_eur for x in a] == [x.kaltmiete_eur for x in b]


def test_scam_and_hard_negative_ratios():
    listings = _gen(scam_ratio=0.15, hard_negative_ratio=0.08)
    assert sum(1 for x in listings if x.is_scam) == 15
    assert sum(1 for x in listings if x.is_hard_negative) == 8
    # Hard negatives are never labeled scams.
    assert all(not x.is_scam for x in listings if x.is_hard_negative)


def test_core_invariants():
    for x in _gen():
        assert x.kaltmiete_eur > 0
        assert x.nebenkosten_eur > 0
        assert x.size_m2 >= 18
        assert x.deposit_eur == 3 * x.kaltmiete_eur
        assert x.rooms in ROOM_CHOICES
        assert x.kiez in KIEZ_NAMES
        assert BERLIN_BBOX["lat_min"] <= x.lat <= BERLIN_BBOX["lat_max"]
        assert BERLIN_BBOX["lng_min"] <= x.lng <= BERLIN_BBOX["lng_max"]
        assert x.warmmiete_eur == x.kaltmiete_eur + x.nebenkosten_eur


def test_ids_and_uuids_unique():
    listings = _gen()
    assert len({x.id for x in listings}) == len(listings)


def test_price_bait_is_actually_cheap():
    listings = _gen()
    legit = [x for x in listings if not x.is_scam and not x.is_hard_negative]
    legit_median_ppm2 = median(x.eur_per_m2 for x in legit)
    baits = [x for x in listings if x.scam_type == "price_bait"]
    assert baits, "expected at least one price_bait scam"
    for b in baits:
        assert b.eur_per_m2 < 0.7 * legit_median_ppm2


def test_photo_reuse_shares_a_photo_set():
    listings = _gen()
    reuse = [x for x in listings if x.scam_type == "photo_reuse"]
    for r in reuse:
        others = [x for x in listings if x.id != r.id and x.photo_set_id == r.photo_set_id]
        assert others, "photo_reuse listing should share its photo_set_id with another listing"


def test_payment_scams_carry_textual_signals():
    listings = _gen()
    for x in listings:
        if x.scam_type == "advance_fee":
            assert "wire" in x.contact_text.lower()
        if x.scam_type == "overseas_landlord":
            assert "western union" in x.contact_text.lower()


def test_rent_overrides_apply_by_id_and_keep_the_deposit_rule():
    import json

    from data.synthetic import OVERRIDES_PATH, generate_catalogue

    overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    raw = {str(x.id): x for x in generate_catalogue(apply_overrides=False)}
    done = {str(x.id): x for x in generate_catalogue()}
    assert overrides and set(overrides) <= set(raw)
    for listing_id, x in done.items():
        if listing_id in overrides:
            assert x.kaltmiete_eur == overrides[listing_id]["kaltmiete_eur"]
            assert x.deposit_eur == 3 * x.kaltmiete_eur
        else:
            assert x.kaltmiete_eur == raw[listing_id].kaltmiete_eur
        # Only rent fields change; ids, photos and labels never do.
        assert (x.photo_set_id, x.is_scam, x.scam_type) == (
            raw[listing_id].photo_set_id, raw[listing_id].is_scam, raw[listing_id].scam_type
        )


def test_catalogue_keeps_the_original_hundred_and_adds_forty():
    from collections import Counter

    from data.synthetic import generate_catalogue

    cat = generate_catalogue(reference_date=REF)
    base = generate_listings(100, seed=42, reference_date=REF)
    assert len(cat) == 164 and len({x.id for x in cat}) == 164
    assert cat[:100] == base
    kinds = Counter(
        x.scam_type or ("tricky" if x.is_hard_negative else "honest") for x in cat[100:140]
    )
    assert kinds == {"honest": 14, "tricky": 10, "advance_fee": 5, "overseas_landlord": 4,
                     "photo_reuse": 3, "subtle": 2, "fake_platform": 2}
    genuine_sets = {x.photo_set_id for x in base if not x.is_scam}
    assert all(x.photo_set_id in genuine_sets for x in cat[100:] if x.scam_type == "photo_reuse")


def test_every_berlin_district_has_listings():
    """The district batch adds Marzahn-Hellersdorf and Reinickendorf (12 each), so all 12
    Bezirke have listings; the first 140 stay as they were."""
    from collections import Counter

    from data.kieze import BERLIN_BBOX as BOX
    from data.synthetic import generate_catalogue, generate_district_listings

    cat = generate_catalogue(reference_date=REF)
    districts = Counter(x.district for x in cat)
    assert len(districts) == 12
    assert districts["Marzahn-Hellersdorf"] == 12 and districts["Reinickendorf"] == 12
    batch = generate_district_listings(reference_date=REF)
    assert [x.id for x in cat[140:]] == [x.id for x in batch]
    kinds = Counter(x.scam_type or ("tricky" if x.is_hard_negative else "honest") for x in batch)
    assert kinds == {"honest": 20, "price_bait": 2, "tricky": 2}
    for x in batch:
        assert BOX["lat_min"] <= x.lat <= BOX["lat_max"] and BOX["lng_min"] <= x.lng <= BOX["lng_max"]
        assert x.kiez in {"Marzahn", "Hellersdorf", "Reinickendorf", "Tegel"}
