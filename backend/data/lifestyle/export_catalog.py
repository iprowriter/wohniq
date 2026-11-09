"""Export the /lifestyle/catalog response as a frontend test fixture (contract test).

    uv run python -m data.lifestyle.export_catalog

The frontend's logic tests (frontend/tests/lifestyle-logic.test.ts) load this file to
check their assumptions against the real API shape; tests/test_lifestyle_api.py fails
if the fixture is stale, so backend and frontend can't drift apart silently.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "tests"
    / "fixtures"
    / "lifestyle-catalog.json"
)


def catalog_json() -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app).get("/api/v1/lifestyle/catalog").json()


def main() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(catalog_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"Wrote {FIXTURE}")


if __name__ == "__main__":
    main()
