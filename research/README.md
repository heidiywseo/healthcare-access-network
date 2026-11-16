# AccessLab — Research Network Version 2

**A reproducible, research-informed proof-of-concept** for adult outpatient mental healthcare accessibility in Philadelphia, using the user's synthetic population cohorts and directory-derived provider scenario.

## What changed since v1

1. Two-stage optimization: **maximize feasible new-patient assignments**, then maximize **modeled expected completed intakes** using research-informed waiting-time attendance functions.
2. Nonlinear wait model from Wang et al. (2023) with a separately justified scenario intercept from Zhang et al. (2020).
3. Piecewise alternative based on Zhang et al.'s observed wait/no-show categories.
4. **True max-min equity LP** over insurance × vehicle-proxy groups (not a post-hoc ranking heuristic).
5. Provider-availability **Monte Carlo** uncertainty scenarios, motivated by JAMA (2024), without transferring its 17.8% rate to Philadelphia providers.
6. Insurance and +20% capacity interventions; illustrative fictional-travel scoring sensitivity.
7. Thorough study-by-study provenance and caveats in **[docs/RESEARCH_METHODS.md](docs/RESEARCH_METHODS.md)**.

## Run

```bash
python -m pip install -r requirements.txt
python build_v2.py
python make_figures.py
python -m unittest discover -s tests -v
```

Quick run with fewer uncertainty simulations:

```bash
python build_v2.py --trials 10
```

The standard run excludes the computationally expensive fictional-travel LP; it can be requested with `python build_v2.py --include-fictional-travel --trials 10` (potentially slow). The standard run uses 80 simulations for each of three hypothetical provider-availability levels. Results are written to `outputs/` and `figures/`. **No API key is needed.**

## Interpretation

- Input annual demand: approximately **92,372** *modeled* care seekers.
- Provider supply: **77 selected source records** and **32,078** *synthetic* annual new-patient intake slots.
- Model output is **not** observed Philadelphia access or predicted clinical outcomes.
- The primary insurance/capacity/wait model does **not** use synthetic population coordinates.
- All fictional-travel results use **fake population coordinates** and must not be interpreted geographically.
- **Not updated for the live map's geography (15 November 2026).** The live v4 map now uses real Census tract points and a 249-tract study area (see `../docs/GEOGRAPHY.md`). This research pipeline still models all 391 tracts with its own copy of the inputs, so its demand (~92,372) and coverage figures are not comparable to the live map's (~55,034 demand, 58.3% baseline coverage).
- A literature-based attendance association is not a validated causal effect or a locally fitted predictive model.
- The model does not yet include a React frontend. This ZIP is a complete Python research/analysis package; the earlier React demonstration is separate.

See `docs/RESEARCH_METHODS.md` for equations, exact sources, modeling decisions, and limitations. See `outputs/summary_v2.json` for the reproducible numerical scenario results.
