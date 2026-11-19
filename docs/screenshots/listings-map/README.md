# Homepage "See on the map" — screenshots

Production build + offline demo backend (`WOHNIQ_DEMO=1`, 100 seeded listings).

**Note:** the build machine had no internet, so OpenStreetMap tiles and Pexels photos could
not load. Tiles were replaced by *stand-in* tiles rendered from the bundled LOR area outlines
(plus a few town labels) — the markers, card and layout are real; the map background is not
what users see. Photos show the app's offline placeholder.

| File | Zoom | What it shows |
|---|---|---|
| `1_listings_z13.png` | 13 | Opening view: price pills (warm rent), overlapping pills stacked as "N flats" |
| `2_card_selected_and_visited.png` | 13 | Card above the clicked pill (photo, rent, title, location, rooms, m²); selected pill white with purple ring; the previously opened pill lavender |
| `3_neighbourhood_medians_z12.png` | 12 | Median warm rent per neighbourhood (Kiez) |
| `4_district_medians_z11.png` | 11 | Median warm rent per district (Bezirk), at each Bezirk's centre |
| `5_berlin_median_z10.png` | 10 | One "Berlin median rent" bubble — other towns (Potsdam) on screen |
| `6_berlin_median_z8_other_cities.png` | 8 | Region view: Berlin median among other cities |

Tiers and thresholds: [ADR-0015](../../adr/0015-homepage-listings-map.md).
