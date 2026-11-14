"""Export real /neighborhoods responses as frontend test fixtures (contract test).

    uv run python -m data.neighborhoods.export_fixture      # or: make neighborhoods-fixture

frontend/tests/neighborhoods.test.ts loads these files to check its logic against the
real API shape; tests/test_neighborhoods_api.py fails if they're stale, so backend and
frontend can't drift apart silently. (The outlines aren't exported: they're the same
file as Lifestyle Match's.)
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "frontend" / "tests" / "fixtures"
SAMPLE_AREA = "036013"  # Helmholtzplatz: strengths and watch-outs both present


def fixtures() -> dict[str, dict]:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    api = "/api/v1/neighborhoods"
    return {
        "neighborhoods-catalog.json": client.get(f"{api}/catalog").json(),
        "neighborhoods-ranking-overall.json": client.get(f"{api}/ranking").json(),
        "neighborhoods-ranking-safety.json": client.get(f"{api}/ranking?category=safety").json(),
        "neighborhoods-area.json": client.get(f"{api}/areas/{SAMPLE_AREA}").json(),
    }


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (FIXTURES / name).write_text(render(data), encoding="utf-8")
        print(f"Wrote {FIXTURES / name}")


if __name__ == "__main__":
    main()
