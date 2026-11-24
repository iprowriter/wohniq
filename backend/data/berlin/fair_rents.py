"""Rent overrides for the synthetic listings, set against the Mietspiegel (ADR-0017).

The generator prices listings from Kiez *asking* rents, so almost every honest listing came
out above the rent-brake limit (76 of 77 before this) and the "price-bait" scams weren't
below the index at all. This picks, by a hash of the id (stable, no rng):

  * ~45 % of honest listings built before 2014 → a fair cold rent inside their index range,
    at or below the rent-brake limit;
  * every price-bait scam → 35–55 % below the lowest index value for that flat.

It writes `data/demo/rent_overrides.json` (committed: it's synthetic listing data, like
risk.json), which `data.synthetic` applies (generate_listings, generate_catalogue), so
the demo and the database agree. `--apply-db` also updates the seeded rows; re-score afterwards (`make score`).

    uv run python -m data.berlin.fair_rents [--apply-db]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

from berlin import get_berlin_data
from berlin.listings import listing_location
from berlin.rent import NEW_BUILD_FROM_YEAR, find_row, period_for
from data.synthetic import OVERRIDES_PATH, generate_catalogue

FAIR_SHARE = 0.45


def _u(listing_id, salt: str) -> float:
    digest = hashlib.sha256(f"{salt}:{listing_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def compute_overrides(data, listings) -> dict[str, dict]:
    rows, periods = data.rent_rows(), data.rent_periods()
    out: dict[str, dict] = {}
    for x in listings:
        loc = listing_location(data, x)
        period = period_for(x.year_built, loc.east, periods)
        row = find_row(rows, loc.location_class, period, x.size_m2) if period else None
        if row is None:
            continue
        if x.scam_type == "price_bait":
            per_m2 = row["low"] * (0.45 + 0.20 * _u(x.id, "bait"))
            reason = f"price bait: below the index (row {row['row']})"
        elif (
            not x.is_scam
            and not x.is_hard_negative
            and x.year_built < NEW_BUILD_FROM_YEAR
            and _u(x.id, "fair") < FAIR_SHARE
        ):
            low = max(row["low"], 0.9 * row["mean"])
            high = 0.98 * row["mean"] * 1.10
            per_m2 = low + (high - low) * _u(x.id, "level")
            reason = f"fair rent within the index range (row {row['row']})"
        else:
            continue
        out[str(x.id)] = {"kaltmiete_eur": round(per_m2 * x.size_m2), "reason": reason}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--apply-db", action="store_true", help="also update the seeded listings")
    args = ap.parse_args(argv)
    data = get_berlin_data()
    # Compute from the generator's own prices, never from already-overridden ones.
    listings = generate_catalogue(apply_overrides=False)
    overrides = compute_overrides(data, listings)
    OVERRIDES_PATH.write_text(
        json.dumps(dict(sorted(overrides.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fair = sum(1 for v in overrides.values() if v["reason"].startswith("fair"))
    print(
        f"{len(overrides)} overrides ({fair} fair rents, {len(overrides) - fair} price bait) "
        f"→ {OVERRIDES_PATH}"
    )
    if args.apply_db:
        from sqlalchemy import text

        from core.db import get_engine

        with get_engine().begin() as conn:
            for listing_id, v in overrides.items():
                conn.execute(
                    text("UPDATE listing SET kaltmiete_eur = :k, deposit_eur = :d WHERE id = :i"),
                    {"k": v["kaltmiete_eur"], "d": 3 * v["kaltmiete_eur"], "i": listing_id},
                )
        print(f"Updated {len(overrides)} listings in the database. Now run `make score`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
