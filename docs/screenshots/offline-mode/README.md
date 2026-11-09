# WohnIQ offline mode: UI screenshots

Taken with headless Chromium (Playwright) against the real backend and frontend, running
in offline demo mode (no `.env`) in a sandbox without internet. Review material for the
offline-mode change; delete this folder before committing if you don't want it in the repo.

## 1_current_code_no_downloads/ (latest code)

Neither `make demo-photos` nor `make demo-stops` has been run, so this is the worst case.

| File | What to check |
|---|---|
| `1_home.png` | Six random listings load. Photos show as placeholders because Pexels is unreachable. |
| `2_listing_page.png` | Price breakdown, details, risk badge with its evidence, amenity counts, and amenity markers on the map. The map background is grey because tiles need internet. |
| `3_search_work_near_kreuzberg.png` | Every card shows "≈N min · estimated", with the estimate note under "Understood as". Kiez names work without the stops file. |
| `4_comparison.png` | Commute row shows "≈25 min / Estimated", with no change counts. Spandau's summary says "≈50 min to work (estimated)". |
| `5_example_search_without_stops_file.png` | Without the stops file "Alexanderplatz" can't be placed, and the note says so instead of leaving a silent gap. |

## 2_commute_with_stops_file/ (straight-line commute estimates, before ADR-0009)

Same code, with `data/vbb/stops.csv` present. The official VBB download is unreachable in
the sandbox, so that file was built from a public npm copy of VBB's stop data
(`vbb-stations`), then deleted afterwards. Photos are placeholders.

| File | What to check |
|---|---|
| `1_example_search_alexanderplatz.png` | The built-in example search: every card has an estimated commute to Alexanderplatz. |
| `2_comparison.png` | Comparison view for that search. |

## 3_earlier_standin_photos/ (before the commute feature)

Taken in the first round, before commute estimates existed, so result cards show no commute
here. To test the local-photo path, generated solid-colour JPEGs stood in for the Pexels photos under
their real file names (the files `make demo-photos` would save). They show that local photos are
served by the backend and displayed. They are not the real photos.

| File | What to check |
|---|---|
| `1_home.png` | Listing cards with locally served photos. |
| `2_listing_page.png` | Photo gallery (one colour per room type), risk, amenities, map markers. |
| `3_example_search.png` | Ranked results with risk flags. |

## 4_route_based_commute/ (route-based commute, ADR-0009)

Latest code with `data/vbb/` built by the real `make demo-stops` code path
(`--from-zip`). VBB's own download is unreachable in the sandbox, so the feed was
**synthetic**: real VBB lines and stations (public `vbb-lines`/`vbb-stations` npm data),
but ride times computed from mode speeds and frequencies estimated from trip counts.
The routes are real Berlin routes; the exact minutes are not the real timetable. The
generated files were deleted afterwards.

| File | What to check |
|---|---|
| `1_example_search_alexanderplatz.png` | Lichtenberg ≈25 vs Treptow ≈31 min (both showed 30 before), "direct"/"1 change" on each card, and the note naming the VBB weekday-peak timetable. |
| `2_comparison.png` | Commute row: ≈25 / ≈31 / ≈19 (fastest) / ≈41 min with "Direct · Estimated" or "1 Change · Estimated". Spandau's summary: "≈41 min to work, 1 change (estimated)". |

Routes behind these numbers (from the same run):

| Listing | Route | Estimate |
|---|---|---|
| Lichtenberg, 2.5-room | walk 7 → U5 Magdalenenstr. → Alexanderplatz | ≈25 min, direct |
| Treptow, 2-room | walk 12 → S9 Plänterwald → Alexanderplatz | ≈31 min, direct |
| Moabit, 1.5-room | walk 6 → S7 Bellevue → Alexanderplatz | ≈19 min, direct |
| Spandau, 3-room | walk 4 → bus M36 → walk 5 → RE2 Spandau → Alexanderplatz | ≈41 min, 1 change |

## 5_map_without_internet/ (map fallback, option A)

The listing-page map when its OpenStreetMap background can't load. Checked in four network
situations (`scripts/check_map_offline_fallback.py`): tiles failing, tiles loading, requests
hanging, and the connection coming back. "Online" tiles are a generated stand-in image served by
the test browser (labelled "stand-in tile (sandbox)"), because OSM is unreachable in the sandbox.

| File | What to check |
|---|---|
| `1_offline_map.png` | Clean background instead of grey, the whole 500 m amenity search area (dashed circle), a metric scale bar, and a caption below the map that hides no markers. A park centre can lie outside the circle, since its edge is within 500 m. |
| `2_offline_listing_page.png` | The same map in the context of the full listing page. (The header in the middle is a full-page capture artifact of the sticky header.) |
| `3_online_map_standin_tiles.png` | With tiles loading, the map looks exactly as before: no circle, scale bar or caption. |
| `4_connection_back_map.png` | After the connection returns and the map is panned, every tile is re-requested and loaded, with no grey gaps where tiles had failed. |

## Reproduce

```bash
# terminal 1: backend in offline mode (from the wohniq folder)
make demo

# terminal 2: frontend (from the wohniq folder)
cd frontend && npm ci && npm run build && npx next start -p 3000

# terminal 3: screenshots (from the wohniq folder)
pip install playwright && python -m playwright install chromium
cd docs/screenshots/offline-mode && mkdir -p screenshots
python scripts/capture_current.py         # set 1 -> screenshots/
python scripts/check_home_and_listings.py # home + every listing page; lists external hosts contacted
python scripts/check_commute_search.py    # example search + comparison (needs `make demo-stops`)
python scripts/check_route_based_commute.py  # set 4: route-based commute (needs `make demo-stops`)
python scripts/check_map_offline_fallback.py  # set 5: map fallback, 4 network scenarios
```

On a machine with internet, real photos and map tiles will appear, and after `make demo-photos`
and `make demo-stops` the example search shows commute estimates.
