# Geography: what the map can and cannot establish

**Current setup (15 November 2026): real Census tract locations and outlines, a study area around the provider sample, and network travel times from R5 (OpenStreetMap roads + SEPTA schedules).**

| Layer | Source | Status |
|---|---|---|
| Provider locations (77) | User-geocoded from source addresses | Real addresses; geocodes not independently checked against site entrances |
| Tract locations (391 populated tract IDs) | Census Bureau 2024 Gazetteer, tract internal points (2020 tract definitions) | Real. `data/tract_representative_points.csv` |
| Tract outlines | Census Bureau 2024 cartographic boundary file, 1:500k (`cb_2024_42_tract_500k`) | Real, lightly simplified (~5 m). `assets/tract_boundaries.js` |
| Study area | Smallest circle containing all 77 providers | Computed by `engine.py` at startup |
| Driving times (vehicle households) | R5 on OpenStreetMap roads (Geofabrik Pennsylvania extract, 15 Nov 2026) | Network-based, **free-flow** (no congestion). `data/travel_times.csv` |
| Transit times (no-vehicle households) | R5 on SEPTA GTFS (release v202611010: bus, trolley, subway, regional rail) + OSM walking | Network-based, schedule-based median, for three weekday departure windows (7–9 AM, 11 AM–1 PM, 5–7 PM). `data/travel_times.csv` |

The original cohort file (`data/synthetic_cohorts.csv`) still contains the old **synthetic** `origin_latitude`/`origin_longitude` values, which form an evenly spaced 17 × 24 grid. They are not used while `data/tract_representative_points.csv` is present: the engine replaces them with the real points when it loads. The data files themselves were not changed.

## Study area

Providers were collected from a ~5-mile map search around north-central Philadelphia. Tracts far outside that search have nearby providers that were never collected, so including them would make them look underserved because of how the data was gathered, not because of real access. The model therefore keeps only tracts whose internal point lies inside a circle.

By default (`STUDY_AREA_RADIUS_MILES = 'fit_providers'` in `engine.py`) the circle is the **smallest circle that contains every provider** in `data/providers.csv`:

- Center 39.9644, -75.1638 (Spring Garden area); radius **5.36 miles**.
- Two providers lie on the edge (Beanel Behavioral Health Services, GPHA); all 77 are inside.
- **249 of 391 tracts** are kept (1,992 of 3,128 optimization nodes).
- The circle is recomputed from `providers.csv` each time the server starts. A hypothetical clinic placed on the map does not move it.

The map draws the study area as a dashed circle.

### How the study area changes the results

Baseline scenario, straight-line travel proxy (the study-area comparison was run before network times were added; the pattern is the same with network times, since total assignments are capacity-bound):

| Study area | Tracts | Modeled demand | Assigned | Coverage | Lowest group coverage |
|---|---:|---:|---:|---:|---:|
| All tracts (no restriction) | 391 | 92,372 | 32,078 | 34.7% | 3.1% |
| 5-mile circle | 240 | 52,847 | 32,078 | 60.7% | 8.3% |
| **Smallest circle around providers (5.36 mi, default)** | **249** | **55,034** | **32,078** | **58.3%** | **5.5%** |
| 5.5-mile circle | 260 | 57,905 | 32,078 | 55.4% | 5.1% |

Assigned patients do not change because total provider capacity (32,078 annual intake slots) is the binding limit in every case. Coverage changes because the denominator (modeled demand) changes. **Always report the study area alongside any coverage figure.**

### Changing the study area

In `engine.py`, set `STUDY_AREA_RADIUS_MILES` to `'fit_providers'` (default), a number of miles around `STUDY_AREA_CENTER`, or `None` (all 391 tracts). Then restart `python server.py` and run `python export_snapshot.py`. The page first draws a baseline snapshot saved inside `index.html` and only asks the server for new results when you click **Recalculate network**, so a stale snapshot or an old server process will show the previous setup. The travel-time matrix covers all 391 tracts, so it does not need recomputing.

## Travel times

### How they were computed

`prepare_travel_times.py` runs [R5](https://github.com/conveyal/r5) through `r5py` on:

- **Roads and paths:** OpenStreetMap, Geofabrik `pennsylvania-latest.osm.pbf` (downloaded 15 Nov 2026), clipped to the Philadelphia area (bounding box -75.40, 39.80, -74.85, 40.20) with `osmium extract --strategy=complete_ways`.
- **Transit:** SEPTA GTFS release `v202611010` (`gtfs_public.zip`, which contains `google_bus.zip` and `google_rail.zip`; both inner feeds are used). PATCO and NJ Transit are not included.

For every tract internal point (all 391) to every provider (77) and every other tract:

| Mode | Used for | How |
|---|---|---|
| Driving | Vehicle-access cohorts | Car on the OSM road network at R5's free-flow speeds. No traffic congestion, parking search or walking from the car |
| Transit | No-household-vehicle cohorts | Walk to stop, wait, ride, transfer, walk to destination; walk-only if faster. **Median** over departures every minute in a 2-hour window on **Tuesday 17 November 2026**, computed separately for **7–9 AM** (default), **11 AM–1 PM** and **5–7 PM** |

The CSV has one `drive_min` column and one `transit_<window>_min` column per window (`transit_am_min`, `transit_midday_min`, `transit_evening_min`). Settings, including each window's label, are recorded in `data/travel_times_meta.json`. The run took about 20 minutes on a laptop and produced 182,988 origin–destination rows with no unreachable pairs (3-hour cap).

### What the times look like (study-area tracts to providers, 19,173 pairs; transit at 7–9 AM)

| | Network (R5) | Old straight-line proxy |
|---|---:|---:|
| Driving, median | 13 min | 20 min |
| Driving, range | 0–30 min | 8–42 min |
| Transit, median | 42 min | 35 min |
| Transit, range | 0–90 min | 12–80 min |
| Pairs within 45 min driving | 100% | 100% |
| Pairs within 60 min transit | 90.1% | 96.6% |

Driving times track straight-line distance closely (correlation 0.93). Transit is less regular (0.82) and averages about 9 km/h of straight-line distance door to door, which is typical for urban transit once walking and waiting are included. The nearest provider is a median 3 minutes' drive (max 14) or 13 minutes by transit (max 27) from a tract.

### How the engine uses them

`travel_mode='network'` (the default whenever `data/travel_times.csv` is present; the UI sends `auto`) looks up minutes instead of using a formula: driving for vehicle cohorts, transit for no-vehicle cohorts. Everything downstream is unchanged:

- Eligibility: a provider is a candidate only within the driving limit (default 45 min) or transit limit (default 60 min).
- The **assumed** attendance multiplier `exp(-ln(2) × minutes/60)` is applied on top of the wait-time attendance model.
- Up to **12 nearest plus 5 lowest-wait** eligible sites per cohort are retained for speed. The LP is exact over that candidate graph, not guaranteed globally optimal over every feasible edge.
- **A new clinic placed on the map** is not in the matrix. It is given the travel times of the **nearest tract internal point** (the result's `meta.new_site_travel` reports which tract and how far away it is). This is an approximation: within a few hundred meters it is usually close, but a site placed in a park or across a rail line can differ from its neighbor.
- The tract panel's "sites reachable" counts now come from the engine, using the same travel times.

The **transit departure time** dropdown in the app (API field `transit_window`: `am`, `midday` or `evening`; default `am`) picks which transit column no-vehicle cohorts use. Driving times are the same in every window because they are free-flow.

`travel_mode='illustrative'` still runs the old straight-line proxy for comparison, and travel constraints can be switched off entirely.

### Effect on the results

| Travel method | Expected completed intakes | Lowest group coverage |
|---|---:|---:|
| **Network (R5), default** | **27,047** | **5.1%** |
| Straight-line proxy (old) | 25,185 | 5.5% |
| Travel constraints off | 28,364 | 32.0% |

Network times raise expected completed intakes because most driving times are shorter than the old proxy assumed. The no-vehicle groups still receive only 5–9% coverage, against 76–85% for vehicle groups. **This gap is still not caused by reachability:** with network transit times, every study-area tract can reach at least 26 Medicaid-accepting providers within 60 minutes (median 58). It comes from the second optimization stage, which, after the maximum number of patients is assigned, chooses *which* patients to assign by maximizing expected attendance. Transit trips are longer, the assumed multiplier lowers their expected attendance, so no-vehicle patients are assigned last. With the equity objective every group reaches 58.3%. Treat the gap as a consequence of the attendance assumption applied to realistic travel times, not as a measured disparity.

### Time of day

| Transit window (Tue 17 Nov 2026) | Transit median | Pairs within 60 min | Nearest provider, median / max | Expected completed | Lowest group coverage | No-vehicle groups |
|---|---:|---:|---:|---:|---:|---:|
| **7–9 AM (default)** | 42 min | 90.1% | 13 / 27 min | 27,047 | 5.1% | 5.1–8.9% |
| 11 AM–1 PM | 43 min | 87.8% | 14 / 30 min | 27,047 | 5.5% | 5.5–8.6% |
| 5–7 PM | 42 min | 89.3% | 14 / 28 min | 27,047 | 5.0% | 5.0–8.6% |

SEPTA service in these three weekday windows is similar, so the times differ by only a minute or two at the median; midday is slightly slower (fewer peak-only trips). The model results barely move: expected completed intakes are the same to the nearest patient because the solver assigns vehicle households first (their driving times do not change), and every study-area tract still reaches at least 26 Medicaid sites within 60 minutes in every window. Weekend and late-evening service, which is much sparser, has not been computed.

## What the map shows

- Each tract in the study area is drawn as its Census outline, shaded by modeled coverage: under 20%, 20–35%, 35% or more. Click a tract to see its demand, assignments, and how many sites each group can reach.
- Flow lines run from each tract's internal point to the assigned provider. They are assignments, not routes.
- If the tract point file is missing, the map falls back to drawing the synthetic grid points as dots, without outlines, study area or network times, and shows the "illustrative only" warning.
- Philadelphia has 408 tracts (2020 definitions); the 17 not in the cohort file are all Census special land-use tracts (codes 9800–9899: parks, the airport and similar areas with few or no residents).

## How the input files were prepared

To reproduce or update them:

1. **Tract points.** Download `2024_gaz_tracts_42.txt` from https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/ (index: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html). Run `python prepare_census_tract_points.py /path/to/2024_gaz_tracts_42.txt` → `data/tract_representative_points.csv`.
2. **Tract outlines.** Download and unzip `cb_2024_42_tract_500k.zip` from https://www2.census.gov/geo/tiger/GENZ2024/shp/ (index: https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html). Run `python prepare_tract_boundaries.py /path/to/cb_2024_42_tract_500k.shp` → `assets/tract_boundaries.js`.
3. **Travel times.** Requires Java 21 and `pip install r5py` (only for this step; the server does not need them).
   - Download `pennsylvania-latest.osm.pbf` from https://download.geofabrik.de/north-america/us/pennsylvania.html and clip it: `osmium extract --bbox=-75.40,39.80,-74.85,40.20 --strategy=complete_ways -o philadelphia.osm.pbf pennsylvania-latest.osm.pbf` (`brew install osmium-tool`).
   - Download `gtfs_public.zip` from https://github.com/septadev/GTFS/releases and unzip it to get `google_bus.zip` and `google_rail.zip`.
   - Pick a **weekday inside the GTFS service calendar** (check `calendar.txt`; SEPTA releases are valid for a few weeks to months). Run:
     `python prepare_travel_times.py --osm philadelphia.osm.pbf --gtfs google_bus.zip google_rail.zip --date 2026-11-17 --window am=07:00 midday=11:00 evening=17:00 --window-hours 2`
     (each `key=HH:MM` adds a transit window; the first is the app's default)
     → `data/travel_times.csv`, `data/travel_times_meta.json`. The script selects Java 21 automatically on macOS.
4. Restart `python server.py` and run `python export_snapshot.py`.

Use Census file vintages whose tract definitions match the tract IDs in the cohort file (2020 definitions; any 2020–2029 file).

**Attribution:** map data © OpenStreetMap contributors (ODbL); transit schedules from SEPTA's public GTFS feed.

## What this still does not establish

- **Driving is free-flow.** R5 does not model traffic, so peak-hour driving will take longer than shown, and parking time is not included.
- **Transit is schedule-based.** It assumes buses and trains run on time, covers three weekday daytime windows only (no weekends or late evenings), and does not model fares, crowding, accessibility (stairs, elevators), or paratransit. Evening or weekend access can be much worse.
- **Tract internal points stand in for where residents live.** Large tracts can have residents well over a kilometer from that point; population-weighted tract centers (Census 2020 centers of population) would be a better origin.
- **Attendance and limits are assumptions.** The 45/60-minute limits and the travel-attendance multiplier are not estimated from data; they drive most of the vehicle/no-vehicle difference.
- **New map sites** use the nearest tract's times, not routed times.
- **Spot checks against Google Maps or SEPTA's trip planner are still pending**; see `docs/VALIDATION.md`.
