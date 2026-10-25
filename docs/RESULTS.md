# Current U.S. Showcase Results

These results are generated from the authorized U.S. export on the local project machine. Raw guest text is not included in this repository. Re-run the scripts in the README after receiving a new export; report the generated JSON/CSV alongside the repository commit hash.

## 1. Automatic issue identification

Final chronological holdout: 11,998 tagged `Open Feedback (English)` records; 77 raw Level-2 labels.

| Metric | Value |
|---|---:|
| Strict raw-tag Micro-F1 | 0.570 |
| Strict raw-tag Macro-F1 | 0.478 |

The selected system is the TF-IDF multi-label baseline. A plain `distilroberta-base` benchmark, constrained to 45,000 training rows and one epoch, achieved lower holdout Micro-F1 (0.363); it is retained as a benchmark, not the selected deployment model.

## 2. Candidate coverage for the issue-layer UI

The dashboard maps supported raw tags to 12 macro categories and shows at most three candidates. A raw tag requires at least 300 positive examples in the pre-holdout training period. This is evaluated only on holdout records containing at least one supported negative macro issue.

| Metric | Value |
|---|---:|
| Supported raw tags | 69 of 77 |
| Macro categories | 12 |
| Eligible holdout records | 5,601 |
| True supported category instances | 11,893 |
| Covered instances in top 3 | 9,177 |
| Top-3 macro-category coverage (Recall@3) | 0.772 |
| Macro-average category coverage | 0.693 |

Coverage@3 does not penalize an extra second or third suggestion. It is a triage/candidate-retrieval metric, **not** full classification accuracy or F1. Rare/unsupported cases route to GM review.

## 3. Macro-category rating associations

The updated Ridge model uses observed platform tags only and reports the following conditional associations in rating points. “Unresolved association” is the category coefficient; “recorded-resolution association” is the issue × resolved interaction. Neither column is a causal treatment effect.

| Macro category | Unresolved association | Recorded-resolution association |
|---|---:|---:|
| Staff service | -0.692 | +0.411 |
| Billing & payments | -0.661 | +0.351 |
| Room condition & comfort | -0.642 | +0.259 |
| Bathroom | -0.581 | +0.208 |
| Reservations | -0.518 | +0.061 |
| Public areas | -0.418 | +0.255 |
| Arrival & departure | -0.283 | +0.204 |
| Customer service & recovery | -0.270 | +0.306 |
| Amenities | -0.239 | +0.077 |
| Safety & security | -0.220 | +0.205 |
| Food & beverage | -0.220 | +0.224 |
| Digital & loyalty | -0.179 | +0.069 |

Use the generated `results/macro_satisfaction_regression_us.json` for the final holdout RMSE, MAE, R², Spearman correlation, CV-selected Ridge penalty, sample counts, and full run metadata. Do not claim conventional p-values: Ridge is selected for predictive stability under correlated features, not inferential hypothesis testing.
