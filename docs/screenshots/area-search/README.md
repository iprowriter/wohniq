# Area-aware search — screenshots

Production build + offline demo backend (keyword parser + template explanations, the same
code path as without Gemini). Photos show the offline placeholder (no internet on the build
machine). Each image is a viewport screenshot, exactly what the user sees after the results
auto-scroll; regenerate with `python docs/screenshots/area-search/scripts/capture.py`
(the script refuses to save a capture whose header isn't at the top or whose content isn't
on screen).

| File | Query | What it shows |
|---|---|---|
| `1_reported_query.png` | "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow" | Areas understood ("in Mitte / Spandau / Lichtenberg / Treptow"); every result badged "In …"; summaries say *why* it's a match |
| `2_budget_too_low.png` | "quiet flat in Mitte budget €300" | Budget-too-low notice: cheapest price, recommended minimum, one-click budgets |
| `3_budget_and_nearby.png` | "2-room in Mitte, budget 1000" | Budget notice for Mitte + closest matching flats nearby, each with its distance |
| `4_after_one_click_budget.png` | (after clicking "Search with €1.010") | The same search with the recommended budget: a flat in Mitte |

Before the fix, "a quiet flat in Mitte" returned Lichtenberg, Spandau, Treptow and
Schöneberg but no flat in Mitte. Decision record: [ADR-0014](../../adr/0014-area-aware-search.md).
