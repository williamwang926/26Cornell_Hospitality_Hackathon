# Guest Issue Triage & Recovery Decision Support

An academic, reproducible prototype for a Hilton hackathon. The project turns post-stay guest feedback into a **decision-support queue**: it identifies broad issue categories, estimates their historical association with guest ratings, and presents department managers with editable recovery options and costs.

> **Scope and status.** This is a research prototype, not a Hilton production system. It does not connect to Hilton systems, does not make autonomous guest-facing decisions, and should not be used to set compensation or evaluate employees without property review and governance approval.

## What the prototype does

1. **Text intake.** `Open Feedback (English)` is mapped to issue tags by a TF-IDF multi-label classifier.
2. **Issue layer.** Tags are rolled into 12 operational macro categories (for example, Room condition & comfort, Billing & payments, and Staff service).
3. **Satisfaction layer.** A leakage-safe temporal Ridge model estimates each macro category's historical association with the 1–5 guest rating and the association of reported resolution with that rating.
4. **Solution layer.** A department manager confirms a fine issue and selects an editable solution. Cash cost, incremental labor time, and expected effectiveness are transparent assumptions—not ML outputs.
5. **Governance layer.** Safety/security items bypass cost-only ranking; rare, low-confidence, and ambiguous issues route to `Other / GM Review`.

## Primary outputs

All primary measures use a chronological U.S. holdout: earlier feedback is used to train/tune; the newest 20% is never used for model selection.

| Question | Measure | Artifact |
|---|---|---|
| Can the system recover fine issue tags? | Strict raw-tag multi-label Micro-F1 | `results/temporal_validation_us.json` |
| Does the candidate UI surface the right operational area? | Top-3 supported macro-category coverage (Recall@3) | `results/business_tag_metrics_us.json` |
| Can macro issues predict later ratings? | Holdout RMSE, MAE, R², Spearman | `results/macro_satisfaction_regression_us.json` |
| What is associated with a rating loss/recovery? | 12 macro-category Ridge coefficients | `results/macro_satisfaction_effects_us.csv` |

The fine-tag F1 and Top-3 coverage are **different metrics**. Top-3 coverage does not penalize the second or third candidate, but is capped at three suggestions; it must never be described as ordinary accuracy or F1.

## Data availability and privacy

The raw review export is confidential and intentionally excluded from Git. It may contain free text and internal property identifiers. A user with authorized access must place it at:

```text
data/dashboard-export-06-01-pm-2026-10-23.csv
```

Do not commit the raw export, model caches, API credentials, screenshots containing guest text, or production data extracts. See [Data Dictionary](docs/DATA_DICTIONARY.md).

The underlying raw data are proprietary to Hilton and were provided solely for the **2026 Hospitality Hackathon**. They are not included in this repository, may not be redistributed, and are not licensed by this repository. See [Data rights and repository policy](docs/DATA_RIGHTS_AND_REPOSITORY_POLICY.md).

## Reproduce the updated U.S. pipeline

Python 3.10+ is recommended. The selected baseline is CPU-friendly; a GPU is not required.

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Leakage-safe fine-tag baseline and rating-model diagnostics
python -m src.temporal_validation

# Dashboard candidate-coverage metric (TF-IDF baseline only)
python -m src.business_tag_metrics

# 12-category satisfaction regression; observed platform tags only
python -m src.macro_satisfaction_regression

# Department-manager solution catalog for the dashboard
python -m src.macro_solution_catalog
```

The optional Transformer scripts are retained as benchmarks. The selected model for the prototype is the time-validated TF-IDF baseline unless a future, like-for-like comparison exceeds it on the untouched holdout.

## Documentation

- [Methodology](docs/METHODOLOGY.md): task definitions, temporal validation, equations, and limitations.
- [Current U.S. results](docs/RESULTS.md): headline holdout metrics and interpretation.
- [Data dictionary](docs/DATA_DICTIONARY.md): source columns, derived variables, and data-handling rules.
- [Cost and solution assumptions](docs/COST_AND_SOLUTION_ASSUMPTIONS.md): editable parameters, public benchmarks, and what is not identified from the data.
- [Dashboard contract](docs/DASHBOARD_CONTRACT.md): intended user flow, decision rights, and output fields.
- [Private-repository release checklist](docs/PRIVATE_REPO_RELEASE_CHECKLIST.md): what to verify before pushing.

## Dashboard

This repository includes a dashboard prototype for hotel guest-issue triage and recovery planning. It demonstrates how guest feedback can be categorized and prioritized by estimating the potential profit impact of resolving each issue, based on modeled rating improvements and editable property-level cost assumptions, and then routed to the appropriate department. The demo uses simulated data and is not connected to Hilton systems. See dashboard/README.md for setup and usage instructions.

## Repository structure

```text
src/       Reproducible modeling and catalog-export scripts
data/      Editable assumptions, taxonomy, and authorized local inputs
results/   Generated tables for the dashboard and reporting
docs/      Methodology, data dictionary, limitations, and governance notes
```

## Citation

If reusing this prototype, cite the repository commit hash, the retrieval date of any public benchmark, and the exact raw-export version supplied by the authorized data owner. Do not cite the results as causal estimates of solution effects.
