# ADR-0008 — Offline commute estimate from straight-line distance and published speeds

**Status:** Accepted, amended by [ADR-0009](0009-route-based-commute-estimate.md) · **Date:** 2026-11-06

> ADR-0009 adds a route-based estimate over the VBB network, used whenever it has been downloaded. The straight-line estimate described here remains the fallback, and decisions 3–4 (weight 1.0, minutes only) still apply to it.

## Context

Commute time (SPEC F5) comes from the live BVG/VBB `transport.rest` API. Without it, in
offline demo mode or when the API is down, the commute factor disappeared and results showed
no travel time. Commute is the heaviest ranking factor and the first thing a flat-hunter asks
about, so the app was much less useful offline.

Two problems had to be solved without a network:

1. **Placing the work location.** It arrives as free text ("Alexanderplatz"), and live
   mode geocodes it through the API.
2. **Estimating door-to-door time** between the listing and that place.

## Decision

1. **Estimate from haversine distance and published average speeds** (`enrich/commute_estimate.py`,
   stdlib only). We chose published speeds over fitting constants to cached live journeys, to
   keep the model simple and explainable (the calibration option is noted below).
2. **Place the work location from a local index** (`enrich/places.py`): Berlin-area stops
   extracted once from VBB's open GTFS feed (`make demo-stops` → `data/vbb/stops.csv`), plus
   the Kiez centres in `data/kieze.py`. Like the demo photos, the stops file is downloaded per
   machine and **not committed**, which keeps the repo free of third-party data copies.
3. **Estimated commutes weigh 1.0 in ranking instead of 2.0** (`RankingWeights.commute_estimated`).
   An estimate is less certain than a live journey, so it still informs the order but no
   longer dominates it. It's labelled as an estimate everywhere.
4. **Show minutes only.** The number of changes is a guess, so estimates report `changes=None`
   and the UI shows "≈25 min · estimated" instead of "direct / 1 change".
5. **Fall back to the estimate when the live API fails**, in live mode too, not only in demo
   mode. If the API resolved the stop before failing, its coordinates are used; otherwise the
   local index. Estimates are **never written to `commute_cache`**, so an outage can't be
   cached as a real journey.
6. **Accept the keyword parser's reading of "near X" as a work location** ("quiet flat near
   Mitte" → commute to Mitte's centre), consistent with how the live version behaves.

## Model

With `d` = straight-line km from listing to destination:

```
walk    = d × 1.3 / 4.8 km/h
transit = 8 min (walk to/from stops) + 4 min (initial wait)
        + in-vehicle time for d × 1.2, split into brackets:
            first 2 km at bus/tram speed, next 4 km at U-Bahn speed, rest at S-Bahn speed
        + 4 min for one change if d ≥ 5 km
minutes = min(walk, transit), rounded to the nearest 5 (minimum 5)
```

The brackets reflect that longer trips use faster modes. Using marginal brackets keeps the
result continuous and never decreasing with distance, so a farther listing can't look closer.
A unit test checks this from 0 to 30 km.

### Published speeds

| Mode | Average speed incl. stops | Constant |
|---|---|---|
| Bus / tram (BVG) | ≈ 19 km/h | `BUS_TRAM_KMH` |
| U-Bahn (BVG) | ≈ 31 km/h | `UBAHN_KMH` |
| S-Bahn Berlin | ≈ 39 km/h | `SBAHN_KMH` |

These are rounded, commonly cited figures from BVG and S-Bahn Berlin publications. They
could not be re-checked against the primary sources when this was written (no internet in
the build environment). Verify them when convenient; each is a single constant.

### Assumptions (not published figures)

| Assumption | Value | Why |
|---|---|---|
| Walking speed | 4.8 km/h | Common planning value (~1.3 m/s) |
| Walking detour | × 1.3 | Street grid vs. straight line |
| Transit detour | × 1.2 | Rail/bus routes are fairly direct |
| Walk to + from stops | 8 min | ~300–400 m at each end |
| Initial wait | 4 min | About half of a 5–10 min headway |
| One change | from 5 km, 4 min | Short trips are usually direct |

### Example outputs

| Trip (stop to stop, via the local index) | Straight line | Estimate |
|---|---|---|
| Alexanderplatz → Friedrichstraße | 1.6 km | 20 min |
| Alexanderplatz → Warschauer Straße | 3.1 km | 20 min |
| Alexanderplatz → Hermannplatz | 3.9 km | 25 min |
| Alexanderplatz → Zoologischer Garten | 5.6 km | 30 min |
| Alexanderplatz → Rathaus Steglitz | 9.5 km | 40 min |
| Alexanderplatz → Rathaus Spandau | 14.4 km | 50 min |
| Hauptbahnhof → BER | 20.3 km | 60 min |

These are door-to-door times, including walking and waiting, so they're longer than the
in-vehicle time on a timetable.

## Known limitations

- **Ignores line structure.** Two places on the same U-Bahn line get the same estimate as
  two places that need an awkward change. Rounding to 5 minutes and the "≈ / estimated"
  labels signal the precision.
- **Overestimates express corridors.** Regional and airport express trains are faster than
  the S-Bahn speed used. Hauptbahnhof → BER shows 60 min; the airport express takes about
  30 min station to station.
- **No time of day**: off-peak headways are longer than the 4-minute wait assumes.
- **Places must be stations or Kiez names.** "TU Berlin" or a company name doesn't resolve.
  The search response then says so (`commute_note`) instead of silently showing nothing.
- **Without `make demo-stops`, only Kiez names resolve.** The demo backend prints a warning
  at startup. Production deploys don't run the download either, so there the fallback
  relies on the API's resolved stop, or Kiez names. Adding `make demo-stops` to the image
  build would extend coverage.

## Alternatives considered

- **Calibrate the constants against cached live journeys (`commute_cache`):** more accurate,
  but needs a DB export and a fitting step. Deferred in favour of published speeds (decision 1).
  It remains the natural next step if estimates need to be tighter.
- **Commit the stops file:** simpler setup, but adds a third-party data copy to the repo.
  Rejected for consistency with the demo photos (decision 2).
- **Timetable routing offline (OpenTripPlanner, r5py, RAPTOR on VBB GTFS):** real
  transfers and timetables, but needs Java and/or the full feed (tens of MB) plus a routing
  engine. Too heavy for a demo laptop; possible later.
- **Road routers (OSRM, Valhalla):** model cars, bikes and walking, not public transport.
- **`haversine` / `geopy` packages:** unnecessary. Haversine is a few lines of stdlib maths,
  accurate to well under 1% at city scale.

## Consequences

- **+** Offline mode shows a travel time for every listing whose work location can be placed,
  and live mode degrades to an estimate instead of a blank.
- **+** The estimate is honest: flagged in the API (`estimated`), labelled in the UI and the
  explanation ("≈25 min to work (estimated)"), weighted lower, and never cached.
- **+** Deterministic and pure, in line with ADR-0001: same inputs give the same minutes.
- **−** Accuracy hasn't been measured against live journeys (see the calibration alternative).
  Trips that don't fit the model can be well off, e.g. express corridors (BER) or awkward changes.
- **−** One more per-machine setup step (`make demo-stops`) for full place coverage.
