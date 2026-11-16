# Version 2 — Executed scenario results and interpretation

**These are modeled outcomes from synthetic inputs, not Philadelphia healthcare statistics.** Run command: `python build_v2.py --trials 80` (no fictional travel).

## Core result

- Annual modeled new-patient demand: **92,371.7** people.
- Synthetic annual new-patient capacity: **32,078** slots across 77 directory-derived records.
- Optimally assigned: **32,078** people (**34.7%** of modeled demand).
- Expected completed initial intakes under the **Wang weekly-odds / Zhang reference-intercept scenario**: **28,364** (**88.4%** of modeled assignments).
- Alternative **Zhang piecewise waiting-time** scenario: **23,097** modeled completed intakes. This substantial difference shows **sensitivity to the selected wait-time model**, not uncertainty measured in Philadelphia.

## Intervention comparison

| Scenario | Assigned | Expected completed | Coverage |
|---|---:|---:|---:|
| `insurance_capacity_wait_odds` | 32,078 | 28,364 | 34.7% |
| `max_min_insurance_transport_equity` | 32,078 | 28,364 | 34.7% |
| `capacity_plus_20pct` | 38,494 | 34,037 | 41.7% |
| `uninsured_accepted_all` | 32,078 | 28,364 | 34.7% |
| `capacity_and_uninsured` | 38,494 | 34,037 | 41.7% |
| `wait_piecewise_sensitivity` | 32,078 | 23,097 | 34.7% |


Capacity is the binding total-system constraint under these assumed inputs. Expanding uninsured eligibility alone changes feasible edges but not total assignments. This **does not** imply that insurance expansions are ineffective in real healthcare systems, nor that group assignments are unchanged.

## Equity illustration

- Baseline minimum group coverage across 8 insurance × vehicle-proxy groups: **12.8%**.
- True max-min coverage LP minimum: **34.7%**.
- Total assigned and modeled completed intakes are effectively unchanged because all provider capacity can be used and wait probabilities are provider-only; the model redistributes *who* receives appointments.
- **Warning:** baseline group differences largely reflect LP tie-breaking, since geographic barriers are excluded from this run and age/insurance groups are not assigned different attendance penalties. Do not describe these differences as measured disparities.

## Provider availability sensitivity

Provider records are independently activated with hypothetical probabilities (not empirical Philadelphia availability rates). 80 draws per probability, seed 20261111.

| Assumed availability | Mean assigned | 5th percentile | 95th percentile |
|---|---:|---:|---:|
| 50% | 16,042 | 12,538 | 19,746 |
| 75% | 23,699 | 19,750 | 27,109 |
| 90% | 28,832 | 26,315 | 30,714 |

These percentile intervals describe **Monte Carlo scenario variation**, not statistical confidence intervals for actual Philadelphia providers.

## What research determined and what it did not

- Wang et al. (2023): the **0.95 weekly attendance odds ratio**.
- Zhang et al. (2020): **0.91 attendance at 7 days** for the hybrid intercept and **three observed wait/no-show anchor points** for the alternative model.
- Brahmbhatt & Schpero (2024): motivates checking directory/appointment availability uncertainty. The model **does not** apply their 17.8% or 27.2% clinician findings to our mixed-service sites.
- The provider availability probabilities, synthetic insurance flags, capacity, wait days, 30% care-seeking assumption, and any travel decay remain **explicit scenarios**.

Read `docs/RESEARCH_METHODS.md` for the study-by-study source ledger, equations, validation and limitations.
