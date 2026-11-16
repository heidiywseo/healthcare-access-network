# AccessLab Research Network v2 — Research, equations, decisions, and audit trail

**Prepared 11 November 2026.** Project scope: synthetic, tract-cohort-based adult outpatient mental healthcare access in Philadelphia. **This is a research-method demonstration, not an empirical estimate of access, appointment attendance, or policy effects in Philadelphia.**

## 1. Source hierarchy and exactly what was used

The user supplied the eight-page `teammate_literature_review.pdf` (titled *Final Project Idea*), two modeled population/provider CSVs, and methodological documents. The PDF is a **secondary summary of studies**. We independently checked the original abstract/full text of the three primary studies below, and coded only those numerical findings as the main source-informed assumptions. Other references in the PDF are discussed as context, **not implemented as empirically fitted coefficients**.

| Evidence | Source and link | Verified finding | Actual use in v2 | Limits |
|---|---|---|---|---|
| Wang et al., *Psychological Services* (2023), PMID 37141046 | https://pubmed.ncbi.nlm.nih.gov/37141046/ | Logistic regression of **1,587 behavioral health referrals**: each additional week of waiting associated with **5% lower odds of attendance**. | Main nonlinear wait slope: odds ratio **0.95 per seven days**. | Observational association, not causal; different health system; intercept not supplied. |
| Zhang et al., *Journal of Psychiatric Practice* (2020), PMID 32692133 | https://pubmed.ncbi.nlm.nih.gov/32692133/ | One resident outpatient psychiatry clinic: **9.0% no-show at 1 week, 28.6% at 1 month, ~36% at 3 months**; overall 22.3%. | Assumed reference attendance **91% at seven days** for main odds model; separate piecewise log-odds interpolation sensitivity. | External single-clinic descriptive values, not calibrated Philadelphia rates; groups are not a universal curve. |
| Brahmbhatt & Schpero, *JAMA* (2024), PMID 39083249 | https://jamanetwork.com/journals/jama/fullarticle/2821639 | Secret-shopper audit of **320 Medicaid psychiatric prescribing clinicians** in NYC, LA, Chicago, Phoenix: **17.8%** sampled clinician available; **27.2%** appointment available including alternatives at same practice. | Justifies provider-availability uncertainty scenarios. **Neither 17.8% nor 27.2% is used as a Philadelphia site availability probability.** | Clinician-specific, Medicaid-specific, psychiatry-only, non-Philadelphia; cannot transfer directly to 77 mixed-service directory records. |

**Additional studies summarized by teammates, not fitted into v2:** Finnish travel-utilization study (PMID 36451184); Pace et al. 2018 on initial behavioral health attendance; Lesaca 2017 on open-access scheduling in child psychiatry; VA distance/gaps in care (PMC1955257); Bhatta et al. 2023 telehealth/no-shows (PMID 37466943); Pullyblank et al. 2024 rural telehealth (PMC10853349); Wolfe et al. 2020 transportation barriers (PMC7204444); Chaiyachati et al. 2018 Philadelphia rideshare trial (PMID 29404572); and others listed in the PDF. Their reported associations motivate sensitivity analyses, but there is no validated joint travel/wait/insurance attendance equation to transfer directly. No direct age, racial, Medicaid, or poverty penalty is applied to appointment attendance.

## 2. Input provenance and preprocessing

- **Demand:** `inputs/synthetic_cohorts.csv` is the user's 9,384-row synthetic cohort dataset. It represents approximately 1,243,059 modeled adults and **92,371.714 expected annual new-patient care seekers**, based on an explicitly assumed 30% annual care-seeking rate conditional on modeled mental illness. The population input's **origin coordinates are fictional grid points**; no Philadelphia routing claim can be made.
- **Supply:** `inputs/providers.csv` has **77 directory-derived source records**, not a verified census of unique sites. Synthetic payer flags, annual intake slots, and waits yield **32,078 annual new-patient slots**. Provider coordinates were geocoded by the user, but point accuracy and clinical eligibility were not independently confirmed.
- **Insurance:** Medicaid, Medicare, Private/other, Uninsured are mutually exclusive *synthetic* cohort categories, not plan-level network eligibility. `accepts_uninsured=1` means a hypothetical affordable intake pathway.
- **Service:** All modeled records treated as eligible for adult outpatient mental health, combining therapy and psychiatry. This simplifies away clinical suitability.
- **Time unit:** demand and capacity are both **annual new-patient intakes**. The six-annual-visits assumption in the input is intentionally **not** used to determine new-patient capacity.
- **Aggregation:** For insurance-only analyses, the 9,384 age cohorts are aggregated to **eight insurance × vehicle-proxy demand groups**. This is valid for this model because the objective, eligibility, and assumed attendance do not vary by age. For fictional-travel scenarios, group by tract, insurance, and vehicle proxy to **3,128 origins**. Fractional flows represent expected people, not individual appointments.

## 3. Network formulation

Let `i` index demand groups and `j` provider records. Let `D_i` be annual expected new-patient demand, `C_j` be annual intake capacity, and `e_ij` the synthetic insurance compatibility indicator. Assignment `x_ij` is a nonnegative real number of expected annual patients.

- `x_ij = 0` when `e_ij = 0` (and when the hypothetical travel cutoff is violated in the fictional-travel scenario).
- `sum_j x_ij <= D_i` for every demand group.
- `sum_i x_ij <= C_j` for every provider.
- **Stage 1:** maximize `sum_ij x_ij` (total feasible assigned people).
- **Stage 2:** among maximum-coverage allocations (numerical tolerance `1e-5` expected people), maximize `sum_ij x_ij p_ij` (modeled expected completed intakes).

Both stages use `scipy.optimize.linprog(method='highs')` with a sparse bipartite incidence matrix. This is a continuous transportation/flow LP, **not** an integer patient-level match and **not** an attendance-prediction model. Maximizing completions among maximum-coverage solutions does not automatically maximize equity.

## 4. Wait-time model — evidence and calibration

The primary modeled attendance probability for a booked initial appointment at provider `j` is:

`logit(p_wait,j) = logit(0.91) + ((wait_days_j - 7)/7) * ln(0.95)`.

- **0.95** is the *observed association* in Wang et al. for odds of attendance per additional week.
- **0.91** at seven days comes from the **9% no-show** in Zhang et al. and is an **external-reference scenario intercept**, not a locally fitted Philadelphia intercept.
- The two findings come from different samples. Combining them is a modeling choice. The resulting `p_wait` is **not validated as a probability for these 77 sites**.
- Waiting times in the provider CSV are themselves synthetic. No congestion feedback is modeled.

Alternative sensitivity: **piecewise interpolation in log-odds** of attendance through `(7 days, 0.91)`, `(30 days, 0.714)`, `(90 days, 0.64)`, clamped beyond the anchors. These descriptive data points are from Zhang et al. The alternative is **not** claimed as a validated continuous functional relationship.

## 5. Travel scenario — explicitly fictional

The input tract coordinates are artificial. To demonstrate the graph pipeline, we calculate great-circle distance `d_ij` from **fictional** origins to user-geocoded provider coordinates and assign *hypothetical* travel times:

- vehicle proxy: `t_ij = 8 + 2*d_ij` minutes; feasible when `t_ij <= 45`;
- no-household-vehicle proxy: `t_ij = 12 + 4*d_ij` minutes; feasible when `t_ij <= 60`.

Here `d_ij` is in km. These are **made-up speed/overhead formulas, not road or transit routing**. A no-vehicle household is not equivalent to transit use. In this demonstration only, we add an *assumed* travel-decay factor `f(t) = exp(-ln(2)*t/60)` and define `p_ij = p_wait,j * f(t_ij)`. The **60-minute half-life is an illustrative assumption**, not estimated from the Finnish study. We do **not** claim that this product is an empirically validated attendance probability. Outputs containing `fictional_travel` must never be mapped or interpreted as measured Philadelphia geography.

The main `insurance_capacity_wait_odds` analysis **does not use any population coordinates or travel penalty**. Its attendance proxy is `p_ij = p_wait,j`.

## 6. Expected completions, denominators, and interpretation

- `assigned = sum_ij x_ij` (expected booked new-patient intakes/year).
- `expected_completed = sum_ij x_ij p_ij` (modeled expected attended initial intakes/year).
- `coverage = assigned / total modeled care seekers`.
- `completed_per_demand = expected_completed / total modeled care seekers`.
- `expected_attendance_among_assigned = expected_completed / assigned`.

**Do not confuse attendance among assigned patients with access for the full population.** Do not interpret nonattendance as permanent loss of a capacity slot; cancellations, rescheduling, and refilling are not modeled. These are scenario expectations, not observed outcomes or causal intervention effects.

## 7. Equity objective

A separate model solves **max-min coverage** across the **eight synthetic insurance × vehicle-proxy groups**, while keeping total assignments at their maximum. Introduce `z` and constraints:

`sum_{i in group g, j} x_ij >= z * D_g` for each group `g`, where `D_g` is the group's total demand.

Maximize `z`, subject to the same flow constraints and maximum total assigned. Then, among solutions satisfying the optimal fairness threshold (numerical tolerance `1e-6`), maximize expected completed intakes. Outputs report each group's coverage for both allocations.

**Crucial:** the main baseline is free to distribute capacity arbitrarily among groups with similar wait-based costs. Thus extreme baseline group disparities may reflect LP tie-breaking rather than genuine access barriers. Equity comparison is a mathematical illustration, not an estimate of real group-level disparities. The fairness objective is based on synthetic groups and does not establish demographic fairness.

## 8. Intervention experiments

| Scenario | Exactly what changes | What does not change |
|---|---|---|
| Baseline | None | Synthetic demand, capacity, waits, eligibility |
| +20% capacity | Multiply every provider's annual intake capacity by 1.2 | Waits remain unchanged; no cost model |
| Uninsured accepted everywhere | Change all uninsured eligibility edges to feasible | Capacity and wait unchanged; no cost model |
| Both | Apply both changes | Demand and waits unchanged |
| Piecewise wait | Replace Wang+Zhang hybrid wait function with Zhang-anchored piecewise function | Eligibility and capacity unchanged |
| Fictional travel | Add hypothetical origin-provider travel constraints and travel decay | All geography remains fictional |

The +20% capacity intervention is **not** an estimated effect of a real policy. When all slots fill, adding eligibility edges alone cannot increase total served; it may redistribute assignments.

## 9. Provider-availability uncertainty (Monte Carlo)

For each `q in {0.50, 0.75, 0.90}`, draw 80 independent provider-wide Bernoulli `active_j ~ Bernoulli(q)` with reproducible NumPy RNG seed `20261111`. An inactive site has `C_j=0`. Rebuild the insurance-only feasible network, solve the two-stage LP, and record total assigned, expected completed, and number of active provider records. Export all trials and 5th/95th empirical quantiles.

- **q values are hypothetical scenario assumptions**, not Philadelphia estimates or the JAMA 17.8%/27.2% clinician appointment findings.
- Site outages are independent in the simulation, which ignores correlated network failures and uncertainty in individual payer acceptance.
- A directory site being active is not equivalent to an individual Medicaid clinician offering a new-patient appointment.
- Monte Carlo percentiles describe variation **under these assumptions**, not confidence intervals for Philadelphia access.

## 10. Validation, numerical checks, and reproducibility

- Input cohort/provider IDs unique; annual demand nonnegative; provider capacity nonnegative; demand period annual.
- All assigned flows are nonnegative, do not exceed cohort demand or provider capacity, and are zero on infeasible insurance edges by construction.
- Two-stage optimization preserves maximum total served within numerical tolerance.
- The max-min equity run preserves maximum total assigned; each group's modeled coverage should meet the reported fairness threshold within tolerance.
- Attendance function returns probabilities in `[0,1]` and decreases as waiting time increases; synthetic travel factor decreases with time.
- Increasing capacity does not reduce maximum feasible served under identical eligibility assumptions.
- All Monte Carlo runs reproducible with fixed seed.

Run `python -m pip install -r requirements.txt`, `python build_v2.py`, and `python -m unittest discover -s tests -v`. The fictional-travel LP is optional via `--include-fictional-travel` because its large edge set makes it slow; the default research results do not use artificial geographic coordinates. The code and original input files are included. Output files are regenerated by the script.

## 11. Output map

- `outputs/scenario_comparison.csv`: total assignment, expected completion, coverage for interventions and scoring sensitivity.
- `outputs/baseline_coverage_by_group.csv`, `outputs/equity_coverage_by_group.csv`: synthetic insurance × vehicle-proxy distribution under two objectives.
- `outputs/*_coverage_by_group.csv`: corresponding intervention group outcomes.
- `outputs/provider_availability_trials.csv`, `outputs/provider_availability_summary.csv`: Monte Carlo uncertainty.
- `outputs/fictional_travel_positive_assignments.csv`: optional nonzero assignments using **fictional** travel, produced only with `--include-fictional-travel`; no geographic interpretation.
- `outputs/summary_v2.json`: assumptions, warnings, and numerical results.
- `figures/`: publication-ready illustrative plots, generated from the output tables.

## 12. Known gaps and priorities for v3

1. Replace synthetic tract coordinates with actual tract interior points before geographic inference; replace hypothetical travel times with road/transit routing.
2. Validate adult eligibility, deduplicate/co-located records, and improve insurance participation verification for all 77 directory-derived entries.
3. Split therapy from psychiatry and model age/service suitability explicitly.
4. Calibrate wait intercept and travel response with relevant patient appointment data if obtainable; distinguish booking probability from attendance probability.
5. Model provider congestion, rescheduling, and dynamic wait-time feedback if a queueing component is justified.
6. Include provider costs and site-location choices for genuine budget-constrained facility location optimization.
7. Repeat across plausible demand/capacity scenarios; avoid labeling output rates as measured Philadelphia unmet need.

## 13. Citation list

- Wang J, Knitter AC, Staab EM, et al. (2023). *Association between wait time and behavioral health appointment attendance across patient characteristics*. Psychological Services 20(4):983–987. DOI: 10.1037/ser0000768. https://pubmed.ncbi.nlm.nih.gov/37141046/
- Zhang X, Felici J, Gander H, et al. (2020). *Twelve-Month Analysis of Nonattendance for Initial Assessment in a Resident Outpatient Psychiatry Clinic*. Journal of Psychiatric Practice 26(4):337–343. DOI: 10.1097/PRA.0000000000000483. https://pubmed.ncbi.nlm.nih.gov/32692133/
- Brahmbhatt D, Schpero WL. (2024). *Access to Psychiatric Appointments for Medicaid Enrollees in 4 Large US Cities*. JAMA 332(8):668–669. DOI: 10.1001/jama.2024.13074. https://jamanetwork.com/journals/jama/fullarticle/2821639
- Additional bibliography and study summaries: user-provided `docs/teammate_literature_review.pdf`. These sources have not all been independently checked for this implementation.
- Provider and population input construction: `docs/provider_data_methodology.md` and `docs/population_data_methodology.md`.
