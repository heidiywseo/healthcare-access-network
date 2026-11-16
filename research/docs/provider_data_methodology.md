# Philadelphia Adult Outpatient Mental Healthcare Provider Dataset

**Dataset documented:** `providers_geocoded_v2.csv`  
**Project use:** Baseline supply nodes for a Philadelphia census-tract-based mental healthcare accessibility and network intervention model  
**Documentation date:** November 11, 2026  
**Status:** Research-informed **synthetic scenario** built from real directory records; not a verified census of operating outpatient facilities.

## 1. Purpose and scope

This dataset was assembled to model access to routine **adult outpatient mental healthcare** in Philadelphia. For simplicity, therapy/counseling and outpatient psychiatry are treated as one service category. The intended exclusions are crisis-only services, substance-use-only services, inpatient-only care, residential programs, case management without clinical treatment, youth-only services, and unrelated medical specialties.

The modeling unit is intended to be a **provider service location**, rather than an individual clinician. However, the current 77 rows are *selected source records*: co-located or duplicate services have not all been independently resolved, and eligibility has not been confirmed by calling every site. The final dataset should therefore be described as a **77-record provider scenario**, not 77 independently verified unique clinics.

## 2. Original source files

Three separately sourced directories were collected:

| Input file | Original rows | Role in reconciliation | Important limitation |
|---|---:|---|---|
| `dbhids_city_funded_providers(1).csv` | 134 | Publicly funded behavioral health agency/program locations | Includes non-outpatient services and non-mental-health programs |
| `philadelphia_outpatient_mental_health_providers(1).csv` | 68 | Main source of adult outpatient provider candidates | Directory listing does not guarantee current service, intake, or payer status |
| `philly_medicare_eligible_behavioral_neuro_clinicians.csv` | 1,667 | Specialty and clinician/practice-site cross-check | Clinician records are not automatically distinct outpatient clinics; includes neurology |

These were **not concatenated into a single provider network**. They differ in unit of observation (program/site vs clinician), scope, and available evidence. Source information was preserved during screening and audit.

## 3. Initial eligibility screening

The first pass applied adult outpatient mental healthcare eligibility rules to all **1,869** original rows. Screening results were:

| Source | Initially retained | Requires review | Excluded |
|---|---:|---:|---:|
| Outpatient directory | 68 | 0 | 0 |
| DBHIDS | 10 | 50 | 74 |
| Medicare clinician directory | 0 | 972 | 695 |
| **Total** | **78** | **1,022** | **769** |

The Medicare file was not treated as a supply-site list because specialty and practice address alone do not prove an independently accessible adult outpatient clinic. Relevant clinician records were retained for possible future site-level checks rather than discarded as irrelevant.

**Audit artifacts:** `provider_reconciliation_all_source_rows.csv`, `provider_eligible_source_records.csv`, `provider_requires_verification.csv`, and `provider_audit_readme.md`.

## 4. Second-stage source-based screening and location reconciliation

A second pass reassessed outpatient eligibility and city scope, and normalized addresses **for potential match grouping**. It yielded:

| Disposition | Source rows |
|---|---:|
| Directory-supported eligible | **77** |
| Unresolved / require site-level verification | **1,088** |
| Excluded | **704** |
| **Total** | **1,869** |

The 77 retained rows consist of **68 outpatient directory** and **9 DBHIDS** records. The second pass identified **52 potential cross-source location groups** across the broader audit; these are *possible* shared addresses, not 52 proven duplicates. Within the retained set, the scenario audit counted **70 distinct location-group identifiers**, which likewise are not independently verified sites.

This was **directory-supported screening**, not an independent check of each site's current license, adult intake, or operating status. Public resources consulted for the approach included the Community Behavioral Health (CBH) provider directory and Pennsylvania's Human Services Provider Directory. Their existence should not be interpreted as site-by-site verification of all 77 records.

**Audit artifacts:** `provider_verification_stage2_all_records.csv`, `provider_verification_stage2_eligible.csv`, `provider_verification_stage2_unresolved.csv`, `provider_verification_stage2_location_groups.csv`, and `provider_verification_stage2_README.md`.

## 5. Building the 77-record synthetic baseline

The 77 retained source records were converted to the requested network schema. IDs `H001`–`H077` were assigned. Provider names and source attribution were carried forward. `service_type` was standardized to `Outpatient mental health`. Insurance flags, capacity, and waiting time were **generated**, not observed.

A reproducible random generator used **seed `20261110`**. An assumed provider category was assigned using simple rules based on organization names and source (e.g., hospital/university terms, LLC/private-practice terms, DBHIDS/community terms, or unknown). These classifications are **heuristic**, not confirmed ownership or staffing data.

### 5.1 Insurance flags

Each of the four binary flags was sampled independently using category-specific probabilities. `accepts_uninsured = 1` was intended to represent an affordable pathway for uninsured patients (e.g., sliding-scale/publicly supported care), **not** simply the ability to pay full cash price.

| Assumed provider category | Medicaid | Medicare | Private | Uninsured |
|---|---:|---:|---:|---:|
| Community/public | 0.94 | 0.65 | 0.77 | 0.70 |
| Hospital-affiliated | 0.85 | 0.83 | 0.92 | 0.40 |
| Private/small practice | 0.48 | 0.50 | 0.91 | 0.25 |
| Organization unknown | 0.76 | 0.64 | 0.83 | 0.48 |

**These are assumed scenario priors, not measured Philadelphia participation rates or validated provider-specific insurance contracts.** Statewide/national survey findings were considered as background motivation during project planning, but the actual numerical priors in this version were **not empirically fitted** to those studies.

### 5.2 Annual new-patient capacity

The baseline estimated the number of clinicians at a location and the number of new patients each clinician could accept per week, using these hypothetical ranges:

| Category | Assumed clinicians | New patients per clinician per week |
|---|---:|---:|
| Community/public | 4–14 | 0.8–2.0 |
| Hospital-affiliated | 6–20 | 0.7–1.7 |
| Private/small practice | 1–4 | 0.5–1.8 |
| Organization unknown | 2–9 | 0.6–1.9 |

For each row:

`annual_new_patient_capacity = round(assumed_clinicians × assumed_new_patients_per_clinician_per_week × 46)`

The **46 working weeks** and staffing/intake ranges are assumptions. Capacity is **new-patient intakes per year**, not therapy visit slots, clinician full-time equivalents, or observed appointment availability.

### 5.3 Waiting time

Waiting times were sampled from a right-skewed **lognormal distribution**, with log-scale standard deviation **0.46** and category-specific starting medians:

| Category | Assumed baseline median wait |
|---|---:|
| Community/public | 35 days |
| Hospital-affiliated | 49 days |
| Private/small practice | 48 days |
| Organization unknown | 42 days |

The median was multiplied by **1.12** when assumed new-patient intake per clinician was below 1/week, or by **0.94** when it exceeded 1.6/week; otherwise no adjustment was applied. Sampled waits were rounded to days and bounded to **3–180 days**.

This preserves heterogeneity and a long right tail, but **does not represent a fitted Philadelphia waiting-time distribution**. Waits are static baseline attributes: they **do not automatically respond to demand or congestion** when patients are reassigned in a network model.

### 5.4 Reproducibility and audit trail

The generating script was `build_provider_scenario.py`. Its companion `providers_scenario_assumptions_audit.csv` preserves source IDs, original address, original source-field JSON, assumed category, assumed clinician count, intake rate, and synthetic-field status. `providers_scenario_methodology.md` and `providers_scenario_validation.csv` document the initial generation. The initial scenario had 12 columns and blank coordinates.

## 6. Adding addresses and geocoding

Original source addresses were added as a 13th column in `providers_scenario_77_with_addresses.csv`, without changing the previously generated provider attributes. A first geocoded file, `providers_geocoded.csv`, had coordinates for **45 of 77** rows; **32** lacked coordinates.

To improve geocoding, secondary address components such as suites, floors, and building names were removed from the **geocoding address**; street-number spans were simplified where needed. Examples:

- `3535 Market Street, 2nd Floor, Philadelphia, PA 19104` → `3535 Market Street, Philadelphia, PA 19104`
- `New Market West, 3rd Floor, 5901 Market Street, Philadelphia, PA 19139` → `5901 Market Street, Philadelphia, PA 19139`
- `3221-25 Kensington Avenue, Philadelphia, PA 19134` → `3221 Kensington Avenue, Philadelphia, PA 19134`

The cleaning was intended to improve geocoder parsing, **not to assert that the shortened address is the precise clinic entrance**. Original-versus-cleaned values were recorded in `provider_address_normalization_audit.csv`; the re-geocoding input was `providers_77_geocoding_ready.csv`. The geocoding service and its exact algorithm/settings were user-operated and are not documented here; therefore the resulting coordinates should not be described as independently verified by this audit.

The supplied final file, **`providers_geocoded_v2.csv`**, contains **77 rows and 13 columns, with coordinates populated in all 77 rows**. Its observed coordinate ranges are latitude **39.908923–40.030775** and longitude **−75.257820 to −75.086308**. These bounds are a sanity check, **not proof** that each coordinate matches its source address or falls within Philadelphia's municipal boundary.

## 7. Final file schema

| Column | Meaning | Provenance |
|---|---|---|
| `provider_id` | Generated row identifier (`H001`–`H077`) | Generated |
| `provider_name` | Provider/program name | Original directory record |
| `address` | Address used in final geocoded dataset | Source-derived, possibly normalized for geocoding |
| `latitude`, `longitude` | Geocoder output coordinates | User's geocoding process; unverified point accuracy |
| `service_type` | Combined outpatient mental health category | Standardized modeling label |
| `accepts_medicaid` | Modeled Medicaid eligibility flag | Synthetic |
| `accepts_medicare` | Modeled Medicare eligibility flag | Synthetic |
| `accepts_private` | Modeled private insurance eligibility flag | Synthetic |
| `accepts_uninsured` | Modeled affordable uninsured access flag | Synthetic |
| `annual_new_patient_capacity` | Modeled annual new-patient intake slots | Synthetic |
| `wait_days` | Modeled baseline new-patient waiting days | Synthetic |
| `data_source` | Original source family plus synthetic scenario notice | Source-derived/generated annotation |

## 8. Final descriptive checks (from `providers_geocoded_v2.csv`)

| Metric | Value |
|---|---:|
| Provider records | **77** |
| Records with both coordinates | **77** |
| Unique provider IDs | **77** |
| Exact duplicate address strings (additional rows beyond first occurrence) | **3** |
| Total synthetic annual new-patient capacity | **32,078** |
| Median synthetic wait | **43 days** |
| Medicaid flag = 1 | **62 / 77 (80.5%)** |
| Medicare flag = 1 | **52 / 77 (67.5%)** |
| Private flag = 1 | **69 / 77 (89.6%)** |
| Uninsured flag = 1 | **35 / 77 (45.5%)** |

Exact repeated final addresses include `H003`/`H072` (3221 Kensington Avenue), `H012`/`H055` (100 S Broad Street), and `H061`/`H066` (255 S 17th Street). Sharing an address does not necessarily mean the records represent the same clinical service. `H003` and `H072` also have closely related names and are particularly important to inspect for duplication.

**Additional eligibility/geography flags:** `H063` has a source address in **Bala Cynwyd**, outside the defined Philadelphia-only study scope; its geocoded coordinate being within the file's general numeric range does not resolve the mismatch. `H050` is a Children's Hospital eating-disorder program and should have **adult eligibility explicitly checked**. These records were **not silently removed or changed** in the delivered file.

## 9. How this fits the population and network model

The separate demand-side inputs are `philadelphia_tracts_DEMO_CALIBRATED(2).csv` (**408 tract rows**) and `synthetic_cohorts(2).csv` (**9,384 synthetic cohort rows**, covering 391 tracts). The cohorts represent modeled adult care-seeking demand segmented by age, insurance, and vehicle access. Earlier checks found approximately **1,243,059 modeled adults**, **92,372 modeled annual care-seeking patients**, and **554,230 modeled annual visits** (six visits per patient). These are **synthetic demand scenario figures**, not observed utilization.

For a bipartite access network, tract/cohort records act as **demand origins** and provider records as **supply destinations**. Potential edges can depend on distance/travel burden, insurance compatibility, and available new-patient intake capacity. In the current simplified model, therapy and psychiatry are combined into one service class.

**Do not interpret** 32,078 synthetic new-patient slots divided by 92,372 modeled care seekers as the city's measured treatment coverage: the 77 selected records are not the full Philadelphia supply network, and both numerator and denominator are modeled.

## 10. Intervention modeling and methodological safeguards

The project's aim is to compare access under interventions such as additional intake slots, new outpatient sites, improved Medicaid/uninsured participation, or changes to travel access. Use this file as a **fixed baseline scenario** and compare interventions against it with consistent population inputs, random seeds, and eligibility definitions.

For waiting-time interventions, a **demand-responsive congestion or queueing component** should be introduced in the network model. Otherwise, reassigning patients or adding provider capacity will not change the static `wait_days` field unless the simulation explicitly updates it. Run sensitivity analyses over insurance acceptance, capacity, and wait assumptions, because these synthetic quantities can materially affect results.

Before drawing strong geographic or provider-specific conclusions, review duplicate/co-located sites, out-of-city addresses, adult eligibility, geocoder point accuracy, and whether the selected sites are currently taking new patients. Do not present modeled payer acceptance, capacity, or wait times as factual statements about named providers.

## 11. File lineage

```text
Original provider directories (134 DBHIDS + 68 outpatient + 1,667 clinician rows)
  -> first eligibility audit (78 retained source records)
  -> second-stage directory-supported audit (77 retained source records)
  -> providers_scenario_77.csv (12 columns; synthetic insurance/capacity/waits)
  -> providers_scenario_77_with_addresses.csv (13 columns; original addresses added)
  -> providers_geocoded.csv (45 coordinate-complete rows)
  -> address normalization audit + providers_77_geocoding_ready.csv
  -> providers_geocoded_v2.csv (77 coordinate-complete rows; current baseline)
```

The audit and assumptions files should be retained alongside the final CSV to support reproducibility and transparent interpretation.

## 12. Reference directories (context, not record-by-record verification)

- Community Behavioral Health (Philadelphia): https://cbhphilly.org/members/provider-directory/
- Pennsylvania DHS Human Services Provider Directory: https://www.humanservices.dhs.pa.gov/human_service_provider_directory/
- Philadelphia DBHIDS: https://dbhids.org/

The numeric insurance, staffing, capacity, and waiting-time assumptions above are **scenario choices**. No external study was used to fit those specific values in the actual generating script.
