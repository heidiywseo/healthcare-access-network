# Healthcare Access Simulator (Philadelphia, v4)

This is the **map-first version** of the Healthcare Access Simulator (previously called AccessLab): the network map is the home page, and all provider, patient, and intervention decisions are visualized as **optimized assignment flows**. The Python solver recomputes after each change. This is a **synthetic class project**, not a live healthcare directory or real Philadelphia access estimate.

## Quick start

```bash
python -m pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:8765**. Allow a few seconds for each recalculation (the optimization is solved on demand). If port 8765 is busy, change it in `server.py`.

After changing `engine.py` or anything in `data/`, **restart the server and run `python export_snapshot.py`**. The page first draws a baseline snapshot saved inside `index.html` and only asks the server for new results when you click **Recalculate network**, so skipping either step shows stale results.

## Open without Python

Open `AccessLab_Map_Preview.html` in a browser. This is a **read-only interactive map preview**: you can inspect provider pins, cohort origins, and baseline assignment flows, but you cannot recompute interventions. To actually change the network and see the mathematically optimized result, start the local server.

## The interface

- **Map center:** 77 provider pins; 249 Census tracts drawn as their real outlines and shaded by modeled coverage; a dashed circle marking the study area; and the highest-volume patient assignment flows. Click a provider or tract for its details; zoom and pan to inspect. Connections are **assignments, not routes**.
- **Page layout:** a single footer line carries the project-wide caveats; panels no longer repeat them.
- **Left controls:** choose baseline/equity/capacity/uninsured/wait scenarios, adjust travel thresholds, add a clinic by clicking on the map, or select a provider to edit its capacity and insurance flags. Press **Recalculate network**.
- **Right insights:** provider/tract inspection, outcomes relative to baseline, eight insurance × vehicle-access coverage groups, and methodology links.
- **Patient view (demo tab, right panel):** set a patient's location on the map, their insurance, whether they have a car, the longest trip they'd accept and (for transit) when they'd travel. The panel lists the matching providers ranked by modeled likelihood of attending, shortest trip or shortest wait, and marks the top five on the map. It uses the same network travel times and the current scenario (added clinic, capacity, insurance changes), with no optimization. **Insurance acceptance, capacity and wait times are synthetic, so this is an illustration, not a directory or availability check.** It needs the server (`/api/patient`); the offline preview shows a notice instead. Nothing entered is stored.
- **Live backend:** `engine.py` constructs insurance/travel feasible edges and solves two-stage linear programs with SciPy HiGHS. Equity is a max–min coverage LP. The map draws **computed flow values**, not fabricated animation.

## Geography limitation — read this before presenting

Tract locations and outlines now come from Census Bureau files (2024 Gazetteer internal points and 2024 cartographic boundaries), replacing the synthetic grid coordinates in the cohort CSV. Provider coordinates were user-geocoded; site accuracy is not independently verified.

The model is limited to a **study area**: the smallest circle containing all 77 providers (5.36 miles, 249 of 391 tracts), because providers were collected from a ~5-mile search. Coverage depends heavily on this choice (34.7% with all tracts, 58.3% in the default study area), so always state the study area with any coverage figure. Change it with `STUDY_AREA_RADIUS_MILES` in `engine.py`.

**Travel times come from a transportation network.** Vehicle households use driving times on OpenStreetMap roads; no-vehicle households use SEPTA public-transit times including walking, waiting and transfers (median over Tuesday 17 Nov 2026 departures, 7–9 AM by default; 11 AM–1 PM and 5–7 PM are available from the *Transit departure time* dropdown), both computed with R5 by `prepare_travel_times.py`. Driving is free-flow (no congestion) and transit is schedule-based, so treat them as estimates. A clinic added on the map uses the times of the nearest tract. The low coverage of no-vehicle groups is **not** a reachability gap (every tract can reach 26+ Medicaid sites within 60 minutes by transit); it is driven by the assumed travel-attendance multiplier. See `docs/GEOGRAPHY.md` and `docs/VALIDATION.md`.

## What is in the ZIP

- `index.html`, `assets/app.js`, `server.py`, `engine.py`: live map-first simulator.
- `AccessLab_Map_Preview.html`: standalone baseline map preview.
- `data/`: original provider and cohort input CSVs (unchanged), plus `tract_representative_points.csv` (Census tract internal points) and `travel_times.csv` / `travel_times_meta.json` (R5 travel times and their settings).
- `assets/tract_boundaries.js`: Census tract outlines for the map.
- `prepare_census_tract_points.py`, `prepare_tract_boundaries.py`: rebuild the two Census files from Census downloads (see `docs/GEOGRAPHY.md`).
- `prepare_travel_times.py`: computes `data/travel_times.csv` (driving and transit minutes) with R5 from OpenStreetMap and SEPTA GTFS. Needs Java 21 and `pip install r5py`; only this script needs them, not the server.
- `export_snapshot.py`: regenerates the baseline embedded in `index.html` and the offline preview.
- `baseline_snapshot.json`: exported baseline results for the default study area.
- `research/`: Version 2 solver, outputs, original literature review, detailed research methods and tests.
- `legacy_sandbox/`: the original fictional React sandbox source, retained for comparison.
- `docs/MODEL_AND_PROVENANCE.md`: full mathematics, evidence, assumptions, implementation and limitations.
- `docs/GEOGRAPHY.md`: geographic sources, the study area, what the map can and cannot establish.
- `docs/VALIDATION.md`: test status and scenario results.
- `tests/`: basic reproducibility and solver invariant checks (2 of 7 currently fail on outdated geography assumptions; see `docs/VALIDATION.md`).

**No npm installation is required** to run the new interface. It uses a local Python API and a dependency-free SVG frontend.
