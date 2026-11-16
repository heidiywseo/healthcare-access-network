# Dataset B — Synthetic Philadelphia mental-healthcare cohorts

## Purpose and scope
This is a **class-project proof of concept**, not a validated tract-level patient census or a forecast of actual clinical utilization. Each row represents an expected adult population subgroup in a Philadelphia census tract. It is designed to feed an illustrative network assignment/optimization model.

**Files:** `synthetic_cohorts.csv` (main output), `build_dataset_b.py` (reproducible code), `dataset_b_validation.json` (quality checks), and the input `philadelphia_tracts_DEMO_CALIBRATED.csv` (Dataset A). The code uses only local uploaded data; no Census API key is required.

## Source evidence versus synthetic assumptions

| Input | Value / definition | Provenance | Status |
|---|---|---|---|
| Tract IDs, total population | 408 tracts; 1,579,706 people | User-supplied `2024_census_tract(1).json`, `tract_demographics(1).json`, carried through Dataset A | Supplied published estimates |
| Adult and age populations | 1,243,059 adults; 18–34, 35–64, 65+ | Dataset A's age synthesis, anchored to `Vital_Population_Cty(1).csv` county age counts | Modeled tract-level estimates |
| Insurance shares | Medicaid, Medicare, uninsured, residual private/other | Dataset A's modeled tract values, anchored to Philadelphia 2024 Data USA coverage benchmarks | Modeled tract-level rates |
| No-vehicle households | Dataset A `households_no_vehicle_rate` | Dataset A, calibrated to a published Philadelphia household benchmark | **Household** measure used as a **person-level proxy** |
| Frequent mental distress | Dataset A `frequent_mental_distress_pct` | Dataset A's synthetic 19% adult scenario proxy | Not CDC PLACES observations |
| Any mental illness (AMI), past year | **24.77%** of adults 18+ in Philadelphia Region 36, 2021–2023 annual average | User-supplied `NSDUHsubstateExcelTab32-2023(1).csv`; SAMHSA official NSDUH substate tables | Published modeled regional estimate |
| Serious mental illness (SMI), past year | **6.80%** of adults 18+ | User-supplied `NSDUHsubstateExcelTab33-2023(1).csv` | Context only; **not** added to AMI |
| Care-seeking conditional on AMI | **30% annually** | Explicit class-project scenario | Assumption, not observed treatment utilization |
| Visits per care-seeking patient | **6 annually** | Explicit class-project scenario | Assumption, not a clinical estimate |
| Coordinates | Latitude and longitude from Dataset A | Dataset A's fictional grid | **Not real tract coordinates or valid real-world travel origins** |

Sources: https://www.samhsa.gov/data/data-we-collect/nsduh-national-survey-drug-use-and-health/substate-releases/2021-2023 ; https://datausa.io/profile/geo/philadelphia-pa . For Dataset A's detailed benchmark and age derivations, consult `philadelphia_tracts_DEMO_CALIBRATED_METHODS.md`.

## Cohort construction, step by step

1. Read all 408 Dataset A tracts. For each tract, take the integer adult age-group counts for 18–34, 35–64 and 65+. **Seventeen tracts have zero adult population and produce no rows.**
2. Within each age group, construct **four mutually exclusive insurance categories**: Medicaid, Medicare, Private/other, Uninsured. Start from the tract's Dataset A Medicaid, Medicare and uninsured rates; set Private/other to the residual `max(0, 1 - Medicaid - Medicare - uninsured)`. Apply the age-specific multipliers in the code, then renormalize probabilities to sum to one. The multipliers are scenario assumptions, not fitted regression coefficients:

   | Age | Medicaid | Medicare | Private/other | Uninsured |
   |---|---:|---:|---:|---:|
   | 18–34 | 1.35 | 0.18 | 1.05 | 1.45 |
   | 35–64 | 1.00 | 0.55 | 1.12 | 1.05 |
   | 65+ | 0.55 | 6.50 | 0.38 | 0.25 |

   **Caution:** Medicare/Medicaid dual eligibility exists in reality. The input rates are not a joint distribution and may overlap; this demonstration forces mutually exclusive categories, so the resulting adult insurance counts should **not** be presented as accurate adult coverage estimates. No PUMS microdata were used.
3. Split each insurance group into **Vehicle access** and **No household vehicle**. Use Dataset A's *household* no-vehicle rate as a starting proxy. Apply insurance-specific multipliers (1.22, 1.05, 0.80, 1.15 respectively), then approximately recenter to the tract household rate. These relationships are assumptions; no household-to-person conversion or observed joint insurance/vehicle data are available.
4. Set `population_weight = tract_age_count × P(insurance | tract, age) × P(transport | tract, insurance)`. Fractional values are **expected people**, not actual individuals. The 24 combinations per populated tract are retained, including very small expected counts.
5. Model each cohort's *relative* mental-health need as:

   `raw_need = age_multiplier × clip(tract_distress_pct / 19, 0.55, 1.60) × transport_multiplier`

   Age multipliers: 18–34 **1.12**, 35–64 **1.00**, 65+ **0.72**. Transport multipliers: vehicle access **1.00**, no household vehicle **1.06**. These are **illustrative modeling choices**, not measured effects of age or transport on illness. The tract distress indicator itself is a synthetic proxy from Dataset A, not an observed PLACES measure. It is used only to generate scenario variation; it is not equivalent to NSDUH AMI.
6. Multiply all raw needs by a common calibration factor, clipping cohort need rates to [0.03, 0.65], and solve for the factor such that the **adult-population-weighted mean equals 0.2477**. This reproduces the Philadelphia NSDUH AMI regional benchmark *by construction*, not by tract-level validation.
7. Assign `care_seeking_rate = 0.30` for all cohorts, **conditional on modeled need**. Compute `estimated_demand = population_weight × mental_health_need_rate × 0.30`. This is the expected number of distinct adults seeking mental-healthcare **in one year** under the scenario; it is not the number of visits or an estimate of observed utilization.
8. Assign `expected_visits_per_patient = 6.0`, then `estimated_annual_visits = estimated_demand × 6`. This represents an illustrative annual appointment demand. It is suitable for comparing with equally defined hypothetical provider capacity (appointments/year).
9. Carry forward Dataset A's **fictional** latitude and longitude as cohort origin coordinates; these must not be used for claims about real Philadelphia distance, driving time, or transit accessibility. Attach scenario and provenance fields.

## Schema

| Column | Meaning |
|---|---|
| `cohort_id` | Unique synthetic group identifier, composed from GEOID and age/insurance/transport category codes |
| `tract_geoid` | 11-character Census tract GEOID; links to Dataset A |
| `age_group` | `18-34`, `35-64`, `65+` |
| `insurance_type` | `Medicaid`, `Medicare`, `Private/other`, `Uninsured`; mutually exclusive **scenario** categories |
| `transport_access` | `Vehicle access` or `No household vehicle`; household proxy |
| `population_weight` | Expected adult population represented by the cohort; fractional |
| `mental_health_need_rate` | Modeled probability of past-year AMI, calibrated to regional NSDUH prevalence |
| `care_seeking_rate` | Scenario probability of seeking care given modeled AMI: 0.30 |
| `estimated_demand` | Expected care-seeking adults/year |
| `origin_latitude`, `origin_longitude` | **Artificial** demo grid coordinates inherited from Dataset A |
| `scenario_id` | `baseline_30pct_6visits` |
| `expected_visits_per_patient` | Assumed 6 visits annually for each modeled care seeker |
| `estimated_annual_visits` | Expected visits/year |
| `need_definition` | `NSDUH_any_mental_illness_past_year` |
| `demand_period` | `annual` |
| `coordinates_are_synthetic` | `True` |
| `insurance_and_vehicle_are_modeled` | `True` |
| `source_version` | Dataset provenance string |

## Validation results

- **408** source tracts, of which **391** have positive adult population and **17** have zero adult population.
- **9,384** cohort rows = 391 × 3 × 4 × 2.
- Dataset A adult population = **1,243,059**; sum of all cohort population weights = **1,243,059** within rounding tolerance.
- Cohort weights reconcile to **each tract's total adult count and each tract's three age counts**.
- Adult-population-weighted mean of `mental_health_need_rate` = **24.77%** (within numerical tolerance).
- Expected adults with AMI ≈ **307,906**; expected care seekers/year ≈ **92,372**; expected visits/year ≈ **554,230**. These are **modeled scenario outputs**, not actual counts.
- All cohort IDs unique; no negative demand.

## Limitations and responsible interpretation

- The regional AMI rate does not identify individual tracts or age-specific rates. Synthetic within-city differences are **not epidemiological estimates**.
- The age and socioeconomic variables in Dataset A are themselves synthetic and calibrated to broader-area statistics; model outputs inherit those uncertainties.
- Insurance and transportation categories use marginals and ad hoc age/category multipliers; they are **not based on ACS PUMS joint distributions**.
- No explicit dual-eligible Medicare/Medicaid category; provider-insurance compatibility is simplified.
- Household vehicle ownership is not individual car access; no-vehicle status does not establish transit access.
- The 30% care-seeking probability is **not sourced from NSDUH or NHIS**; the 6-visits assumption is not an observed utilization rate.
- Model need is *any mental illness*, not necessarily need for a particular type of treatment. Demand is annual, not concurrent.
- Geographic coordinates are artificial. **Only use abstract/synthetic travel costs for the network demo**, never real-world travel claims.
- The demo's 2024 ACS benchmark year and 2021–2023 NSDUH estimation period differ.

## Report-ready methods paragraph

> We constructed a synthetic adult cohort dataset for Philadelphia census tracts to test a proof-of-concept mental-healthcare network optimization model. The tract population backbone and selected demographic inputs were drawn from user-supplied Census extracts, while age, insurance, and vehicle-access distributions were modeled using the calibrated synthetic tract dataset. Each nonempty tract was divided into groups defined by age (18–34, 35–64, 65+), mutually exclusive insurance category (Medicaid, Medicare, private/other, uninsured), and household vehicle access (yes/no). Cohort weights were constrained to reproduce each tract's modeled adult age totals. Cohort-level past-year mental-health need rates were assigned illustrative age and neighborhood adjustment factors and calibrated to the 24.77% adult prevalence of any mental illness reported for Philadelphia in SAMHSA's 2021–2023 NSDUH substate estimates. We assumed that 30% of adults with modeled mental-health need seek care annually and that each care-seeking adult generates six appointments per year. These assumptions yield illustrative demand for network optimization; they do not estimate observed patient utilization. Geographic coordinates are synthetic, and all tract-level cohort attributes and access comparisons should be interpreted as demonstrations rather than validated local estimates.
