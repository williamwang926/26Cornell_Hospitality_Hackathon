# Data Dictionary and Handling Rules

`dashboard-export-06-01-pm-2026-10-23.csv` is an authorized local input only and is ignored by Git. The repository never redistributes guest text or internal property identifiers.

| Raw field | Role | Handling |
|---|---|---|
| `Rating` | 1–5 outcome | Fitting/evaluation target only; never a live scoring input. |
| `Feedback Date (+00:00 GMT)` | Time index | Chronological split and rolling validation. |
| `Country` | Scope | U.S. filter for showcase results. |
| `Open Feedback (English)` | Text input | Automatic tagging input. |
| Level-2 topic + topic sentiment fields | Platform metadata | Negative / Very Negative entries define observed raw tags. |
| `Problem Incidence` | Incident status | Mapped to none / reported / unreported / unknown. |
| `Problem Resolution` | Resolution status | Defined for reported cases; blank reported values are excluded from rating estimation. |
| `Problem Comments (English)` | Survey problem text | Not inferred into the final macro satisfaction regression. |
| `Feedback Type` | Control | Online-review indicator in the rating model. |
| Brand, Region, Ownership, Honors Tier, Purpose | Controls | One-hot encoded from training data. |
| `Facility ID [Internal]` | Property key | Grouped analysis only; never publicly displayed. |

Derived fields: `platform_topics` = unique negative Level-2 topics; `macro_issues` = 12-category mapping; `resolved` = Yes/No indicator for valid reported cases; and `Other / GM Review` = rare, ambiguous, or low-confidence routing state.

Missing-data rules: non-reported blank resolution is structurally non-applicable; reported blank resolution is unknown, not unresolved; missing Open Feedback cannot be scored by the automatic classifier.
