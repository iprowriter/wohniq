# Lifestyle Match — screenshots for verification

Captured from the running app: production frontend build + backend in offline demo mode
(`WOHNIQ_DEMO=1`, bundled data, no network), headless Chromium. Desktop 1366 px wide,
mobile 390 px. Full-page shots render the sticky header as static so it doesn't overlap
content. Listing photos and map tiles show placeholders/plain background because the
capture machine had no internet.

## Desktop

| # | File | What it verifies |
|---|---|---|
| 01 | `desktop/01-homepage-entry-bar-and-card.png` | Homepage: "Try Lifestyle Match" bar under the search box, header link with "new" dot, marketing card |
| 01b | `desktop/01b-homepage-full.png` | Full homepage: card above "AI-Powered Matching" / "Built-in Scam Protection", footer link |
| 02 | `desktop/02-welcome-presets.png` | Welcome: how it works, 5 presets + "Start from scratch", privacy note |
| 03 | `desktop/03-your-move-student-preset.png` | Page 1 pre-filled by the Student preset: €700 warm, 30 m², 1 room; cited budget references (BAföG €380, WG room €650, typical 30 m² €576) |
| 04 | `desktop/04-your-days.png` | Page 2: fixed destination list (TU Berlin chosen), frequency, max commute 30 min, work style, getting around |
| 05 | `desktop/05-evenings-weekends.png` | Page 3: evenings, weekends (max 2) |
| 06 | `desktop/06-your-neighbourhood.png` | Page 4: neighbours, safety (opt-in, with caveat), extras |
| 07 | `desktop/07-summary-persona-confirm.png` | Summary: persona "The Campus Explorer", weights with the answer behind each, "You told us" with Change links, "Yes, that's me" |
| 08 | `desktop/08-results-overview.png` | **Definition of Done**: top results near TU Berlin within the €700 budget, with reasons + source chips; shaded map with numbered matches; Tune panel |
| 08b | `desktop/08b-results-full-page.png` | All top-10 cards, "Show 10 more areas", privacy note |
| 09 | `desktop/09-why-this-score.png` | "Why this score": per-factor score bars and contribution (Otto-Suhr-Allee/Kantstraße, the TU Berlin area) |
| 10 | `desktop/10-data-behind-this.png` | "The data behind this": every figure, data notes (district rent range), full sources with caveats and links |
| 11 | `desktop/11-listings-panel.png` | "See flats here": listings located in the area, budget fit, risk badges |
| 12 | `desktop/12-listings-panel-empty-state.png` | Honest empty state when an area has no WohnIQ listings |
| 13 | `desktop/13-map-top-matches.png` | Map zoomed to the numbered top matches |
| 14 | `desktop/14-map-all-berlin.png` | Map: all 143 areas shaded by match score |
| 15 | `desktop/15-tune-your-match-pending-update.png` | User control: sliders changed ("Set by you"), explicit "Update results (2 changes)" |
| 16 | `desktop/16-results-after-update.png` | Results after Update: re-ranked, persona priorities reflect the new weights, new trade-off shown |
| 17 | `desktop/17-area-removed.png` | "Not for me": top area removed ("top 10 of 142"); remaining scores unchanged |
| 17b | `desktop/17b-removed-area-undo-chip.png` | Removed area listed with ↺ undo |
| 18 | `desktop/18-from-scratch-needs-a-preference.png` | Start from scratch with no preferences: guidance shown, matching disabled |

## Mobile

| File | What it verifies |
|---|---|
| `mobile/m01-homepage.png` | Homepage entry bar + marketing card on a phone |
| `mobile/m02-welcome-presets.png` | Presets stacked, no horizontal overflow |
| `mobile/m03-your-days.png` | Destination picker on a phone |
| `mobile/m04-summary-persona.png` | Summary + persona, single column |
| `mobile/m05-results-top.png` / `m05b-results-full-page.png` | Results: header, map, tune panel, cards |
| `mobile/m06-listings-panel.png` | Listings panel full-screen on a phone |
