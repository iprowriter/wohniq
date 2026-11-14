# Berlin Neighborhoods — screenshots

Captured in headless Chromium against the offline demo backend (`make demo`) and the production frontend build. The sandbox had no internet, so the OSM tiles show the offline fallback (outlines on a plain background). Online, the OpenStreetMap tiles appear under the outlines.

| File | Shows |
|---|---|
| `1_overall_list_and_map.png` | Overall ranking: list left, shaded map right, top-10 markers |
| `2_map_click_selects_in_sidebar.png` | Clicking Helmholtzplatz on the map selects, scrolls to and expands it in the sidebar |
| `3_safety_lowest_crime_first.png` | Safety category, lowest crime first |
| `4_safety_highest_crime_first.png` | Safety, highest crime first (markers on the bottom 10) |
| `5_education_detail_shared_link.png` | `/neighborhoods?category=education&area=036013`: metrics vs. Berlin with sources |
| `6_weights_panel.png` | "What matters to you?" weights for the overall score |
| `7_mobile_transit.png` | Mobile (Pixel 5 size): map above, list below |
| `8_affluence_land_values.png` | Affluence detail for Grunewald: land-value index, context land value, income shown Berlin-wide until district data exists |
