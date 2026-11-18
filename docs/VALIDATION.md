# Validation and executed example results

**Last run: 15 November 2026** (research-informed options added and checked 18 November 2026), with real Census tract points and outlines, the default study area (smallest circle containing all 77 providers: 5.36 miles, 249 of 391 tracts), and **network travel times** from R5 (OpenStreetMap driving; SEPTA transit, median over Tue 17 Nov 2026 7–9 AM departures unless noted). See `docs/GEOGRAPHY.md`. Earlier results (synthetic grid coordinates, then the straight-line travel proxy) are superseded.

## Checks

- **Unit tests** (`python -m unittest discover -s tests -v`): **5 of 7 pass.** The two failures are outdated test assumptions, not solver errors:
  - `test_inputs_and_baseline` expects 391 tracts and synthetic geography (`verified == False`); the model now has real tract points and 249 tracts in the study area.
  - `test_geography_gate` expects `travel_mode='verified'` to be refused because no real tract points exist; they now exist, so the request is accepted.
  - Flow conservation, wait-attendance monotonicity, capacity expansion, new-site addition and the equity objective pass.
- `node --check assets/app.js` passes.
- The local API (`/api/status`, `/api/run`) was checked over HTTP. `/api/status` reports `network_travel: true`; runs return `travel_mode: network` by default, and each returned exactly the study-area tracts.
- The live page and the offline preview were rendered in headless Chrome: tract outlines, study-area circle, network-travel note and relabeled travel controls display correctly.
- **Travel-time plausibility:** 182,988 R5 origin–destination times, none unreachable. Driving correlates 0.93 with straight-line distance, transit 0.82; door-to-door transit averages ~9 km/h of straight-line distance. See `docs/GEOGRAPHY.md`.

## Spot checks against trip planners (pending)

These R5 times have **not yet** been compared with Google Maps or SEPTA's trip planner. To check, enter the tract point (from) and provider address (to); for transit, set departure Tuesday ~8:00 AM. R5 driving is free-flow, so compare with Google's "typically" range rather than live traffic.

| Tract | From (lat, lon) | To (provider address) | Straight line | R5 drive | R5 transit |
|---|---|---|---:|---:|---:|
| 42101037200 | 39.91295, -75.15995 | One Reed St, 19147 | 2.2 km | 5 min | 26 min |
| 42101000403 | 39.95301, -75.16627 | One Reed St, 19147 | 2.2 km | 7 min | 25 min |
| 42101013500 | 39.96936, -75.17004 | 1235 Pine St, 19107 | 2.7 km | 7 min | 34 min |
| 42101016300 | 39.98851, -75.13392 | 520 N Christopher Columbus Blvd, 19123 | 3.3 km | 9 min | 27 min |
| 42101012201 | 40.00346, -75.21064 | 4900 Wyalusing Ave | 3.8 km | 9 min | 42 min |
| 42101017202 | 39.99867, -75.17421 | 4301 Rising Sun Ave | 4.3 km | 12 min | 46 min |
| 42101013702 | 39.97670, -75.18228 | 2424 E York St | 5.0 km | 12 min | 45 min |
| 42101010800 | 39.96602, -75.19899 | 3228 N 20th St, 19140 | 5.2 km | 15 min | 54 min |
| 42101028200 | 40.03487, -75.14033 | 2418 E York St, 19125 | 6.5 km | 15 min | 55 min |
| 42101020800 | 40.02140, -75.19354 | 2418 E York St, 19125 | 7.6 km | 15 min | 67 min |
| 42101020702 | 40.01352, -75.19693 | 2055 E Allegheny Ave | 7.7 km | 16 min | 50 min |
| 42101001101 | 39.94499, -75.16252 | 2600 Belmont Ave, 19131 | 7.8 km | 13 min | 54 min |

## Scenario results

Default study area; network travel times unless noted. Modeled demand is 55,034 in every scenario.

| Scenario | Assigned | Expected completed | Coverage | Lowest group coverage |
|---|---:|---:|---:|---:|
| Baseline | 32,078 | 27,047 | 58.3% | 5.1% |
| Max–min equity | 32,078 | 26,475 | 58.3% | 58.3% |
| +20% capacity | 38,494 | 32,219 | 69.9% | 12.0% |
| Uninsured acceptance everywhere | 32,078 | 27,060 | 58.3% | 8.4% |
| Piecewise wait model | 32,078 | 22,029 | 58.3% | 5.1% |
| New site, West Philadelphia (39.955, -75.235; 500 slots; Medicaid + uninsured; 14-day wait) | 32,578 | 27,488 | 59.2% | 6.6% |
| Stricter limits (30 min driving / 45 min transit) | 32,078 | 27,047 | 58.3% | 5.5% |
| Straight-line proxy instead of network (old method) | 32,078 | 25,185 | 58.3% | 5.5% |
| Travel constraints off | 32,078 | 28,364 | 58.3% | 32.0% |

See `docs/SCENARIO_EXAMPLES.csv` for unrounded outputs. The new site used the travel times of tract 42101008102, whose internal point is 0.31 km away.

### Baseline coverage by group (network travel times)

| Group | Coverage |
|---|---:|
| Medicaid · vehicle access | 84.6% |
| Private/other · vehicle access | 79.8% |
| Medicare · vehicle access | 76.4% |
| Uninsured · vehicle access | 76.2% |
| Medicare · no household vehicle | 8.9% |
| Private/other · no household vehicle | 8.6% |
| Medicaid · no household vehicle | 8.3% |
| Uninsured · no household vehicle | 5.1% |

The gap between vehicle and no-vehicle groups is **not** a reachability gap: every study-area tract can reach at least 26 Medicaid-accepting providers within 60 minutes by transit. It comes from the assumed travel-attendance multiplier, which makes longer transit trips count for less when the solver decides who gets the limited slots. With travel constraints off the lowest group reaches 32.0%, and the equity objective brings every group to 58.3%. See "Effect on the results" in `docs/GEOGRAPHY.md`.

### Sensitivity to transit departure time (baseline)

| Transit window | Expected completed | Lowest group coverage | +20% capacity: lowest group | Equity: expected completed |
|---|---:|---:|---:|---:|
| **7–9 AM (default)** | 27,047 | 5.1% | 12.0% | 26,475 |
| 11 AM–1 PM | 27,047 | 5.5% | 13.0% | 26,460 |
| 5–7 PM | 27,047 | 5.0% | 13.0% | 26,469 |

Assigned patients (32,078) and coverage (58.3%) are the same in every window. The 7–9 AM transit times were recomputed alongside the new windows and matched the earlier run exactly. See "Time of day" in `docs/GEOGRAPHY.md`.

### Research-informed options (added 18 November 2026)

| Scenario | Expected completed | Lowest group coverage | Telehealth assignments |
|---|---:|---:|---:|
| Travel effect: 30-min half-life | 25,804 | 5.7% | 0 |
| Travel effect: group T(t) | 27,191 | 5.5% | 0 |
| Wait cap 30 days | 27,431 | 5.7% | 0 |
| Wait cap 14 days | 27,705 | 5.7% | 0 |
| Telehealth 20% (neutral / better / worse) | 27,439 / 27,685 / 27,206 | 19.1% / 18.6% / 19.2% | 6,416 |

Assigned stays 32,078 in all of these runs. The default baseline was re-run after the change and is identical (27,047 expected completed, 5.1% lowest group). The calibration checks against published no-show rates, Medicaid acceptance and wait times are in `docs/RESEARCH_INTEGRATION.md` §4. The checks summarized there: default attendance (84%) is optimistic compared with the published no-show rates; synthetic Medicaid acceptance (80.5%) far exceeds measured rates (35.4%, 17.8%). The new controls, presets and the Patient view score were exercised in headless Chrome with no page errors.

### Graph methods (added 18 November 2026)

- Shadow prices matched re-solving with +1 and +100 slots to within 0.01 for six providers across the value range (+0.69 to +0.88 per slot).
- The location screen correlated 0.984 with an exhaustive exact search over all 249 candidates and ranked the true best site first; the worst-off-group search found the exhaustive optimum (8.9% lowest-group coverage) with 28 exact solves.
- Max-flow check: every group is fully reachable at default limits; at 10/20-minute limits no-vehicle groups can reach only 64–83% of their demand.
- The search, map markers, shading and "add to scenario" were exercised in headless Chrome with no page errors.

Details: `docs/GRAPH_METHODS.md`.

### Sensitivity to the study area (baseline, straight-line proxy)

| Study area | Tracts | Modeled demand | Coverage | Lowest group coverage |
|---|---:|---:|---:|---:|
| All tracts | 391 | 92,372 | 34.7% | 3.1% |
| 5 miles | 240 | 52,847 | 60.7% | 8.3% |
| **Smallest circle around providers, 5.36 mi (default)** | **249** | **55,034** | **58.3%** | **5.5%** |
| 5.5 miles | 260 | 57,905 | 55.4% | 5.1% |

These are synthetic scenario results, not actual Philadelphia treatment coverage. Provider capacity, wait times and insurance acceptance are synthetic; travel times are network estimates under the stated assumptions. The v4 results **differ from the prior v2 insurance-only baseline** because v4 adds travel constraints, the travel attendance multiplier and the study area. Switching travel constraints off recovers the insurance-only optimization framework, within the study area.
