# Healthcare Access Simulator (v4, formerly AccessLab) — Model, sources, implementation, and audit trail

**Date:** 11 November 2026 (geography and travel sections updated 15 November 2026). **Purpose:** class proof-of-concept for outpatient adult mental healthcare network access in Philadelphia. **Not** an empirical estimate of unmet treatment needs, provider availability, travel time, or intervention impact.

## Source inputs

- `data/synthetic_cohorts.csv`: user-supplied 9,384 synthetic cohort records. Aggregated by tract × insurance × household vehicle access into 3,128 optimization nodes. These represent ~92,371.7 **assumed annual care-seeking episodes** across 391 populated tract IDs. Within the default study area (below) the model uses 249 tracts, 1,992 optimization nodes and ~55,034 episodes. The file's `origin_latitude`/`origin_longitude` values are synthetic grid points and are replaced at load time by real tract internal points. Mental health prevalence and care-seeking assumptions are modeled; the 30% care-seeking fraction is not observed new-patient referral incidence. Ages are aggregated for the optimization, so age-specific service restrictions are not modeled.
- `data/providers.csv`: user-supplied 77 directory-derived records. Provider names, source addresses, and user-generated geocodes originate in the source compilation; acceptance flags, waiting times, and annual intake capacities are **synthetic**. The 77 records are not a census of unique, verified outpatient clinics. At least one site has an out-of-city source address, one appears potentially youth-specific, and several records are co-located or potentially duplicates. See `research/docs/provider_data_methodology.md`.
- `data/tract_representative_points.csv`: Census Bureau 2024 Gazetteer tract internal points (2020 tract definitions) for all 391 tract IDs, built by `prepare_census_tract_points.py`.
- `assets/tract_boundaries.js`: Census Bureau 2024 cartographic boundary tract outlines (1:500k), lightly simplified, built by `prepare_tract_boundaries.py`. Used for drawing only; the model uses the internal points.
- **Study area:** only tracts whose internal point lies inside the smallest circle containing all providers are modeled (center 39.9644, -75.1638; radius 5.36 miles; computed in `engine.py` at startup; configurable via `STUDY_AREA_RADIUS_MILES`). Providers came from a ~5-mile search, so tracts outside it lack their nearby providers. See `docs/GEOGRAPHY.md` for sensitivity to this choice.
- `research/docs/teammate_literature_review.pdf`: teammate-provided literature synthesis. It motivates wait, travel, insurance, and provider directory availability considerations. Only specific wait findings are encoded numerically. The literature does not identify a validated joint accessibility score.
- `research/docs/RESEARCH_METHODS.md`: prior Version 2 detailed research evidence and equations; preserved unchanged in the bundle.

## Optimization graph

For cohort `i` with annual modeled demand `D_i` and provider `j` with modeled annual new-patient capacity `C_j`, `x_ij >= 0` is the modeled number of assigned new-patient intakes per year. Insurance compatibility is a **hard edge constraint**. A provider can only serve a cohort if its synthetic acceptance flag matches the cohort's insurance. Optional illustrative travel eligibility adds an additional edge restriction. Each cohort obeys `sum_j x_ij <= D_i`, and each provider obeys `sum_i x_ij <= C_j`.

**Stage 1** maximizes `sum_ij x_ij` (maximum assigned episodes). **Stage 2** fixes this maximum total assignment and maximizes `sum_ij x_ij p_ij`, expected attended initial appointments. SciPy HiGHS linear programming solves both stages. Values are fractional expected annual flows, not individual patient records. A map link represents assignment volume, not a route or patient movement.

### Attendance probability assumptions

- **Wang et al. (2023)**: behavioral health referral study, 1,587 referrals; 5% lower **odds** of attendance per additional week of waiting. Primary model uses `logit(p_wait,j) = logit(0.91) + ((wait_days_j - 7)/7) × ln(0.95)`. The 0.91 reference at seven days is an illustrative extrapolation from the no-show observation in **Zhang et al. (2020)**, not a jointly fitted model. DOI https://doi.org/10.1037/ser0000768 ; PMID https://pubmed.ncbi.nlm.nih.gov/37141046/ .
- **Zhang et al. (2020)**: outpatient resident psychiatry clinic with observed 9.0% no-show at one week, 28.6% at one month, 36% at three months. Alternative model interpolates **log-odds of attendance** between `(7 days, .91)`, `(30 days, .714)`, `(90 days, .64)`; outside those anchors it is constant. This is a sensitivity function, not a calibrated Philadelphia estimate. https://pubmed.ncbi.nlm.nih.gov/32692133/ .
- **Travel:** `p_ij = p_wait,j × exp(-ln(2) × minutes_ij / 60)`. By default `minutes_ij` is the R5 network travel time (driving for vehicle cohorts, SEPTA transit for no-vehicle cohorts; see `docs/GEOGRAPHY.md`); the old straight-line proxy remains available as `travel_mode='illustrative'`. The 60-minute travel half-life is **assumed**, not estimated from published travel findings.

### Equity

An alternative **max–min coverage** objective introduces `z` with constraints `sum_{i in group g,j} x_ij >= z × D_g` for each of the eight insurance × household-vehicle groups. It first maximizes `z` while preserving Stage 1 maximum total assignments, then maximizes expected attendance while holding the optimal `z` to a tolerance of 1e-6. Fairness across these synthetic groups is not a measurement of demographic inequity. Baseline differences may reflect LP tie-breaking.

### Scenario controls

- Global capacity adjustment scales all synthetic intake slots; no real intervention cost model.
- Uninsured access changes eligibility flags, not clinic cost, payment policy, or wait times.
- Clicking a provider allows an **additive** capacity change and replacement of its modeled payer acceptance flags.
- Clicking the map places one hypothetical new site with selected capacity, wait, and insurance. Location matters **only** when travel constraints are enabled; otherwise it changes network capacity and payer compatibility but not geographic reach. With network travel times the new site borrows the times of the nearest tract internal point.
- Travel threshold sliders (driving limit for vehicle cohorts, transit limit for no-vehicle cohorts) alter the feasibility graph and therefore patient assignments. The transit departure time dropdown switches no-vehicle cohorts between the 7–9 AM, 11 AM–1 PM and 5–7 PM weekday transit times.
- **Patient view (demo).** `Model.patient_options` / `POST /api/patient` ranks every provider for one hypothetical patient: origin = nearest Census tract internal point to the chosen map location; minutes = R5 driving (car) or transit (no car, chosen window) time to each site, with a new map site using its nearest tract's times; a site *matches* if it accepts the patient's insurance and is within the chosen trip limit; *likely to attend* = `p_wait,j × exp(-ln(2) × minutes/60)`, the same assumed factors the optimizer uses. *Booked* is the share of the site's capacity filled in the current scenario's optimized assignment. No optimization is run for the patient, and inputs are not stored. Insurance, capacity and waits are synthetic, so rankings are illustrative.
- Wait-model selector changes the expected-attendance objective, not static provider wait days or capacity.

## What the UI shows

The main page is the map. Blue pins represent geocoded provider records; Census tract outlines are shaded by modeled coverage (red under 20%, orange 20–35%, green 35% or more); a dashed circle marks the study area. If the tract point file is absent, the map instead shows the synthetic origins as colored dots. Mint lines run from each tract's internal point to its assigned provider and show **nonzero optimized patient assignments**, with thickness scaled by assigned episodes; the global map displays up to 210 largest flows for legibility, and clicking a node shows all flows involving it. Node selection displays capacity, assigned episodes, modeled wait, insurance flags, demand, and group-level outcomes. The right panel compares the current solution with the **default baseline (network travel times)** embedded in the project.

The `index.html` file embeds an offline baseline snapshot for immediate preview. The local FastAPI server runs **live SciPy optimization** for arbitrary changes; offline preview intentionally does not pretend to recompute assignments. The JS visualization and Python engine are separate. The original sandbox React project is included under `legacy_sandbox/` for reference.

## Important modeling limitations

1. **Estimated travel times and assumed travel effects.** Travel minutes are R5 network estimates: free-flow driving (no congestion or parking) and schedule-based SEPTA transit for three weekday daytime windows (no weekends or late evenings), from tract internal points. The travel-attendance multiplier and the 45/60-minute limits are assumptions. Under the default objective the multiplier drives most of the gap between vehicle and no-vehicle groups (lowest group coverage 5.1% with network travel vs 32.0% with travel off), even though every tract can reach 26+ Medicaid sites by transit within 60 minutes. See `docs/GEOGRAPHY.md`.
   - **Study-area dependence.** Coverage depends on which tracts are modeled: 34.7% with all 391 tracts, 58.3% in the default 249-tract study area. Total assignments (32,078) are capacity-bound and do not change.
2. **Candidate edge pruning when travel is on.** Up to 12 nearest plus 5 fastest-wait eligible sites per cohort are retained for interactive speed. The LP is exact on this reduced graph, not globally optimal on the full feasible graph.
3. **Synthetic provider attributes** are not factual assertions about named sites. Site names and locations do not prove intake availability.
4. **New-patient episode interpretation:** prevalence × seeking is a scenario proxy for new intake demand; it is not observed new referral volume. Annual slots are not therapy visit slots.
5. **Combined therapy and psychiatry:** provider service scope is collapsed into one category. Youth-only, specialty, and service-specific eligibility remain unverified.
6. **Waits do not respond to congestion.** No dynamic scheduling, cancellations, no-show refills, treatment continuity, or queues.
7. **Attendance is an observational association.** The research-informed attendance function is not a causal prediction of interventions.
8. **Selected provider sample:** comparing its synthetic capacity with all modeled Philadelphia care seekers does not measure citywide treatment coverage.
9. **Synthetic group proportions** and household vehicle proxy are not validated individual-level insurance/transport cross-tabs.
10. **Continuous fractional allocation:** this is an annual expected-flow LP, not discrete appointment booking.

## References

- Wang J et al. (2023), *Association between wait time and behavioral health appointment attendance across patient characteristics*. https://pubmed.ncbi.nlm.nih.gov/37141046/
- Zhang X et al. (2020), *Twelve-Month Analysis of Nonattendance for Initial Assessment in a Resident Outpatient Psychiatry Clinic*. https://pubmed.ncbi.nlm.nih.gov/32692133/
- Brahmbhatt D & Schpero WL (2024), *Access to Psychiatric Appointments for Medicaid Enrollees in 4 Large US Cities*. https://jamanetwork.com/journals/jama/fullarticle/2821639 . Motivates directory uncertainty, **not** a fitted provider availability probability in v4.
- User-supplied *Final Project Idea* PDF: travel, insurance, telehealth, and no-show studies. See full bibliography in `research/docs/RESEARCH_METHODS.md`.
- Census Bureau Gazetteer files (tract internal points, 2024): https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
- Census Bureau cartographic boundary files (tract outlines, 2024, 1:500k): https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
- OpenStreetMap, Geofabrik Pennsylvania extract (roads and paths; © OpenStreetMap contributors, ODbL): https://download.geofabrik.de/north-america/us/pennsylvania.html
- SEPTA GTFS, release v202611010: https://github.com/septadev/GTFS/releases
- R5 routing engine (Conveyal) via r5py: https://github.com/conveyal/r5 , https://r5py.readthedocs.io/

## Reproduction

Python 3.11+, `pip install -r requirements.txt`, `python server.py`, then visit http://127.0.0.1:8765 . To run the checks, `python -m unittest discover -s tests -v`. Baseline JSON is generated by `python export_snapshot.py`; the generated `index.html` embeds that baseline. Rerun it (and restart the server) after any change to `engine.py` or `data/`. Original inputs and research docs are retained; the cohort and provider CSVs are unchanged. Current test status and results: `docs/VALIDATION.md`.
