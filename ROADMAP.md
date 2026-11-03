# WohnIQ Roadmap

WohnIQ is live at https://wohniq-plum.vercel.app (milestones M0–M5 in [`TASKS.md`](TASKS.md)). This is the next round of work, roughly **30+ hours**.

**Constraints that stay in place:** listings remain synthetic ([ADR-0003](docs/adr/0003-synthetic-data-and-images.md)), there are no user accounts, and no real personal data is stored. Ranking stays deterministic ([ADR-0001](docs/adr/0001-deterministic-ranking.md)).

| # | Item | Why | Est. |
|---|---|---|---|
| 1 | **CI + Supabase keep-alive** (T1.2) | Lint + tests on every push; cron ping so the free-tier DB doesn't pause and the demo stays up. | 3h |
| 2 | **Fix photo-reuse detection** (T6.1) | Photo-reuse recall is 0/3 because the eval can't fetch image bytes. Compute and store pHash at seed time so detection and eval use the same stored hashes. | 4h |
| 3 | **German-language queries** (T6.2) | Many Berlin searchers write in German ("2 Zimmer, Friedrichshain, max. 1.200 € warm"). Extend the parser and its keyword fallback, add German eval cases, add a DE/EN UI toggle. | 5h |
| 4 | **Shareable searches** (T6.3) | Encode query + filters in the URL so a search can be sent to a partner or flatmate; keep recent searches in localStorage only. | 3h |
| 5 | **Results map view** (T6.4) | Show all ranked results on one Leaflet map, with hover/selection synced to the result list. | 3h |
| 6 | **Multi-destination commute** (T6.5) | Couples and flatmates commute to different places. Support up to two destinations and a departure time, and score the combined commute. | 4h |
| 7 | **Cold-start & error UX** (T6.6) | Railway/Supabase can be slow on first request. Add skeleton loading, retry, and clear messages when commute or POI enrichment fails. | 2h |
| 8 | **Mobile & accessibility pass** (T6.7) | Responsive result cards and comparison view, keyboard navigation, contrast, screen-reader labels on risk badges. | 3h |
| 9 | **Frontend tests** (T6.8) | Playwright smoke test for search → results → detail → compare, running in CI. | 3h |
| 10 | **Model & prompt upkeep** (T6.9) | Move off `gemini-2.0-flash` to a current model, version the prompts, and re-run the parser and scam evals as a regression check. | 2h |

**Later / ideas:** price-trend chart per Kiez from the synthetic distributions; "why not this one?" explanations for listings filtered out; dark mode.
