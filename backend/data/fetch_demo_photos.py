"""Download local copies of the demo listing photos (run once, while online).

The demo fixtures reference hotlinked Pexels CDN URLs (ADR-0003). For a demo with no
internet, run this beforehand: it saves each distinct photo to `data/demo/photos/`,
and in demo mode the backend then serves those files instead of the CDN URLs. No API
key is needed (plain CDN downloads). Idempotent: existing files are skipped.

    uv run python -m data.fetch_demo_photos      # or: make demo-photos
"""

from __future__ import annotations

import json
import sys

import httpx

from data.demo_repository import DEMO_DIR, PHOTOS_DIR, local_photo_name
from data.pexels import fetch_image_bytes


def main() -> None:
    rows = json.loads((DEMO_DIR / "photos.json").read_text(encoding="utf-8"))
    urls = sorted({r["source_url"] for r in rows})
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    fetched = skipped = 0
    failed: list[str] = []
    for i, url in enumerate(urls, 1):
        target = PHOTOS_DIR / local_photo_name(url)
        if target.is_file() and target.stat().st_size > 0:
            skipped += 1
            continue
        try:
            data = fetch_image_bytes(url)
        except httpx.HTTPError as exc:
            failed.append(f"{url}: {exc}")
            continue
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)  # never leave a half-written file the server could serve
        fetched += 1
        print(f"[{i}/{len(urls)}] {target.name}")

    print(f"photos: {fetched} fetched, {skipped} already present, {len(failed)} failed")
    print(f"-> {PHOTOS_DIR}")
    if failed:
        print("\n".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
