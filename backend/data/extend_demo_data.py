"""Add catalogue listings that the offline demo files don't have yet, without a database.

    uv run python -m data.extend_demo_data        # or: make demo-extend

For every listing in `generate_catalogue()` missing from `data/demo/risk.json`:

  * photos: its photo set gets one photo per room type drawn from images already in
    `photos.json` (so the local copies under data/demo/photos/ already exist), sharing at
    most 2 with any other set (the photo-reuse signal needs 4, ADR-0017);
  * risk: the same detector as `make score --no-llm` (rules against the rent index, photo
    duplicates, the offline wording check), with Kiez price statistics over the whole
    catalogue.

Existing rows are never changed: new listings live in new Kieze and new photo sets, so the
statistics and photo matches of the others stay the same (checked below). Run
`python -m data.berlin.fair_rents` first so new listings get their rent overrides. The live
database gets the same listings with `make seed-extra`, then `make score`.
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import asdict

from berlin.listings import index_bounds
from data.demo_repository import DEMO_DIR, _to_listing
from data.photo_assign import assign_from_existing
from data.synthetic import generate_catalogue
from scam.detector import assess_listing
from scam.signals import kiez_price_stats

ENGINE_VERSION = "v2"
PHOTO_SEED = 4343


def _photo_id(set_id: object, position: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"wohniq-demo-photo:{set_id}:{position}"))


def main() -> int:
    photos_path, risk_path = DEMO_DIR / "photos.json", DEMO_DIR / "risk.json"
    photos: list[dict] = json.loads(photos_path.read_text(encoding="utf-8"))
    risks: list[dict] = json.loads(risk_path.read_text(encoding="utf-8"))
    catalogue = generate_catalogue()
    scored = {r["listing_id"] for r in risks}
    new = [x for x in catalogue if str(x.id) not in scored]
    if not new:
        print("Demo data already covers every catalogue listing.")
        return 0

    # Photos for sets nobody has yet.
    known_sets = {r["photo_set_id"] for r in photos}
    need = sorted({str(x.photo_set_id) for x in new} - known_sets)
    added_photos = assign_from_existing(need, photos, seed=PHOTO_SEED)
    for row in added_photos:
        row["photo_set_id"] = str(row["photo_set_id"])
        row["id"] = _photo_id(row["photo_set_id"], row["position"])
    all_photos = photos + added_photos

    phashes: dict[str, list[str]] = {}
    for r in all_photos:
        phashes.setdefault(r["photo_set_id"], []).append(r["phash"])
    corpus = [(str(x.id), h) for x in catalogue for h in phashes.get(str(x.photo_set_id), [])]
    ppm2: dict[str, list[float]] = {}
    for x in catalogue:
        ppm2.setdefault(x.kiez, []).append(x.kaltmiete_eur / x.size_m2)
    stats = {k: kiez_price_stats(v) for k, v in ppm2.items()}

    def assess(x) -> dict:
        median, mad = stats[x.kiez]
        low, row = index_bounds(_to_listing(x))
        result = assess_listing(
            listing_id=str(x.id),
            kiez=x.kiez,
            eur_per_m2=x.kaltmiete_eur / x.size_m2,
            anmeldung_possible=x.anmeldung_possible,
            median_eur_per_m2=median,
            mad_eur_per_m2=mad,
            phashes=phashes.get(str(x.photo_set_id), []),
            photo_corpus=corpus,
            contact_text=x.contact_text,
            skip_text=True,
            index_low=low,
            index_row=row,
            description=x.description,
        )
        return {
            "listing_id": str(x.id),
            "score": result.score,
            "band": result.band,
            "signals": [asdict(s) for s in result.signals],
            "engine_version": ENGINE_VERSION,
        }

    # Guard: the listings already scored must come out the same with the new ones present.
    by_id = {str(x.id): x for x in catalogue}
    for r in risks:
        again = assess(by_id[r["listing_id"]])
        if (again["score"], again["band"]) != (r["score"], r["band"]):
            print(f"error: listing {r['listing_id']} would change ({r['band']} → {again['band']}).")
            return 1

    added_risk = [assess(x) for x in new]
    photos_path.write_text(
        json.dumps(all_photos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    risk_path.write_text(
        json.dumps(risks + added_risk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    bands: dict[str, int] = {}
    for r in added_risk:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
    print(
        f"Added {len(new)} listings: {len(added_photos)} photos ({len(need)} sets), risk {bands}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
