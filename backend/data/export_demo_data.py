"""Export demo fixtures for offline/demo mode.

Read-only: selects rows from Supabase and writes JSON files to `data/demo/`:

  photos.json         photo rows (hotlinked Pexels URLs + attribution + phash; no image bytes)
  risk.json           risk_assessment rows (score, band, signals with evidence)
  neighborhoods.json  neighborhood_cache rows (public OSM POI counts, POIs, summary)

Listings themselves aren't exported: `data.synthetic.generate_listings(seed=42)`
reproduces them exactly (same ids, prices, photo sets). No secrets are written.

    uv run python -m data.export_demo_data
"""

import json
from pathlib import Path

from sqlalchemy import text

from core.db import get_engine

DEMO_DIR = Path(__file__).parent / "demo"

EXPORTS = {
    "photos.json": """
        SELECT id, photo_set_id, source_url, room_type, position, phash, attribution
        FROM photo
        ORDER BY photo_set_id, position, id
    """,
    "risk.json": """
        SELECT listing_id, score, band, signals, engine_version
        FROM risk_assessment
        ORDER BY listing_id
    """,
    "neighborhoods.json": """
        SELECT location_key, poi_counts, pois, summary
        FROM neighborhood_cache
        ORDER BY location_key
    """,
}

UUID_FIELDS = {"id", "photo_set_id", "listing_id"}


def _clean(row: dict) -> dict:
    return {k: (str(v) if k in UUID_FIELDS and v is not None else v) for k, v in row.items()}


def main() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    with get_engine().connect() as conn:
        n_listings = conn.execute(text("SELECT count(*) FROM listing")).scalar_one()
        print(f"listings in db: {n_listings}")
        for filename, query in EXPORTS.items():
            rows = [_clean(dict(r)) for r in conn.execute(text(query)).mappings()]
            path = DEMO_DIR / filename
            path.write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"{filename}: {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
