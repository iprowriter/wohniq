# ADR-0009: Route-based commute estimate over the VBB weekday-peak network

**Status:** Accepted · **Date:** 2026-11-06 · **Amends:** [ADR-0008](0008-offline-commute-estimate.md)

## Context

ADR-0008 estimates commutes from straight-line distance alone. In practice, listings at similar
distances from a destination got the same time even when their real commutes differ. Example:
a Lichtenberg flat next to the U5 and a Treptow flat a 12-minute walk from the S-Bahn are 5.3 and
5.6 km from Alexanderplatz, and both showed "≈30 min". Distance can't know where lines and
stations are.

## Decision

1. **Route over the real network.** `make demo-stops` (same VBB GTFS download as before) now also
   builds a compact network (`data/vbb_network.py` → `data/vbb/network_*.csv`, not committed).
   `enrich/transit_network.py` finds the fastest door-to-door trip: walk to a station, wait, ride
   line by line, change, walk to the destination. The straight-line estimate remains the fallback
   when the network isn't downloaded, or when no station is within walking distance.
2. **Weekday morning peak.** The network represents departures 07:00–09:00 on a Tue/Wed/Thu, the
   commute people care about. Waiting time is half the actual peak gap between departures of that
   line at that station.
3. **Weight 1.5 for route-based estimates** (`RankingWeights.commute_network`), between live
   journeys (2.0) and straight-line estimates (1.0, ADR-0008). This is conditional on the accuracy
   check below; it has not been run against live data yet (see Validation).
4. **Show real changes.** Route-based estimates know the number of changes, so the UI shows them:
   "≈25 min · direct · estimated", "≈41 min · 1 change · estimated". Straight-line estimates still
   show minutes only (ADR-0008 decision 4 stands for them).
5. **Round to the minute** (not to 5 as in ADR-0008). Rounding to 5 minutes hid exactly the
   differences this change is meant to show. The "≈" and "estimated" labels carry the uncertainty.

## Method

**Building the network** (`data/vbb_network.py`, GTFS in, four CSV/JSON files out):

- **Reference day:** the Tue/Wed/Thu with the most active services in the first six weeks of the
  feed (calendar.txt plus calendar_dates.txt exceptions). This avoids public holidays; `--date` overrides.
- **Line:** a GTFS route in one direction (`direction_id`, or the headsign if missing).
- **Stations:** platforms fold into their parent station. VBB uses several stop-ID formats
  (`…::4` and `…:4:56`); mapping through `parent_station` handles both.
- **Ride time** between consecutive stations: the median scheduled time of the trips departing in
  the window.
- **Wait** when boarding a line at a station: `window / departures / 2`.
- **Rare connections are dropped:** fewer than 2 trips in the window (less than hourly). One-off
  diversions would otherwise create shortcuts that don't exist in normal service.
- **Memory:** `stop_times.txt` is streamed; only active trips' rows between 07:00 and 10:00 are kept.

**Routing** (`enrich/transit_network.py`, Dijkstra on time):

| Step | Cost |
|---|---|
| Walk to/from stations within 1.2 km | 4.8 km/h × 1.3 detour (as ADR-0008) |
| Board a line | its peak wait at that station |
| Ride | scheduled median time per hop |
| Alight | 2 min (platform change or exit) |
| Walk between stations ≤ 300 m apart | walking time (e.g. S-Bahn platform to bus stop) |

Walking all the way is always a candidate. Changes = boardings − 1.

## What prototyping taught us (encoded as tests)

A prototype on public VBB line data first produced confident, wrong routes:

- **A night bus used for a morning commute.** Fixed by the peak window; night lines don't run then.
- **Every S-Bahn line silently missing**, because of the second stop-ID format. Fixed by folding
  platforms through `parent_station`. A mutation test confirms 11 tests fail without it.
- **A one-trip diversion (S45 via Alexanderplatz) used as a regular line.** Fixed by the
  2-trips-per-window rule. A mutation test confirms the diversion trap catches it.

`tests/gtfs_fixture.py` rebuilds each trap (diversion on the same line and direction, night
line, weekend-only line, calendar exception, platform IDs) so they stay fixed.

## Validation

`make eval-commute` (`evals/commute_eval.py`) compares both offline estimates with live BVG/VBB
journeys departing at 08:00 next Tue–Thu. It uses a deterministic sample of listings and eight
common destinations. It reports MAE, bias, the share within 5/10 minutes, order agreement (does
the faster listing also look faster, which is what ranking needs) and changes accuracy. Live
answers are cached, so `--offline` re-scores after tuning without new requests.

**Not yet run:** the live API is unreachable from the environment this was built in. In a
sandbox run on a synthetic timetable with real VBB topology, the routes matched known Berlin
trips (U5 from Magdalenenstraße, S7 from Bellevue, RE2 from Spandau). Extraction of 1.1M
timetable rows took about 8 s at about 250 MB; loading takes about 1 s and a route 5–25 ms. The
weight in decision 3 should be revisited once `make eval-commute` has been run. If the
route-based model turns out worse, deleting `data/vbb/network_*` reverts to straight-line
estimates without a code change.

## Limitations

- **Frequency-based, not timetable-exact.** Waits are averages, so timed connections
  (e.g. a guaranteed bus-to-train transfer) aren't modelled.
- **Branches of one line share a frequency** at common stations, which slightly understates
  waits on branches.
- **Peak only.** Off-peak and weekend commutes are longer than shown.
- **The real feed hasn't been processed here.** Its size (tens of millions of rows) means
  `make demo-stops` takes minutes, not seconds.

## Alternatives considered

- **Full timetable routing (RAPTOR, OpenTripPlanner, r5py):** exact departures and connections,
  but much heavier (Java, or the full feed in memory) for a gain that only matters at
  minute-level precision. Possible later.
- **Nearest station plus straight line:** tried in the prototype. It was worse than both
  alternatives: it ignores buses and picks stations with no useful line.
- **Calibrating ADR-0008's constants:** better averages, but it can't separate two listings at
  the same distance, which was the actual problem.

## Consequences

- **+** Listings at the same distance now get different times when their connections differ,
  and the UI shows real changes.
- **+** Same offline guarantees as ADR-0008: no network at request time, estimates never cached,
  clearly labelled.
- **−** `make demo-stops` takes longer and produces more data; the network must be rebuilt when
  the timetable changes (VBB publishes updates regularly).
- **−** Accuracy is unproven until `make eval-commute` has been run.
