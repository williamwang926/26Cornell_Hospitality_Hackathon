# Methodology

## Study objective

The prototype asks three decision-support questions: can guest Open Feedback be mapped to known issue tags; how are twelve operational issue categories associated with later 1–5 guest ratings; and which recovery options are operationally plausible at editable incremental cost? It does **not** identify a causal effect of any specific recovery action.

## Unit, scope, and time split

The unit is one guest-feedback record. Reported showcase results use `Country == United States`. Records are ordered by `Feedback Date (+00:00 GMT)`; the newest 20% is held out once as final test data. Within the earlier 80%, expanding time folds select hyperparameters. No final-holdout text, labels, thresholds, or ratings enter fitting.

## Text tagging

Input \(X_i\) is `Open Feedback (English)`. The multi-label outcome \(Y_i\) is the set of Level-2 platform topics marked Negative or Very Negative. The selected baseline is word 1–2 gram TF-IDF plus one-vs-rest linear logistic classifiers. Per-label thresholds are selected using only an earlier validation period.

The strict tag metric is:

\[
F1_{micro}=\frac{2TP}{2TP+FP+FN}.
\]

It is not exact-set accuracy: a record can receive partial credit if one of several true issue tags is correctly recovered.

### Dashboard candidate coverage

For the dashboard, tags are mapped to a fixed twelve-category taxonomy. A raw tag is eligible for automatic routing only if it has at least 300 pre-holdout positive examples; other tags route to `Other / GM Review`. The interface presents at most \(K=3\) categories:

\[
\mathrm{Coverage@3}=\frac{\sum_i |T_i \cap \widehat{T}_{i,3}|}{\sum_i |T_i|}.
\]

Extra suggestions are not penalized, so Coverage@3 is a candidate-coverage measure—not F1, precision, or ordinary accuracy. The cap of three prevents the trivial policy of displaying every tag.

## Macro-category satisfaction model

The issue layer uses twelve categories: Amenities; Arrival & departure; Bathroom; Billing & payments; Customer service & recovery; Digital & loyalty; Food & beverage; Public areas; Reservations; Room condition & comfort; Safety & security; and Staff service.

Only observed platform tags enter this regression. `Problem Comments` are not converted into inferred regression covariates; in the intended workflow, a human confirms a fine issue for a live complaint.

\[
Rating_i = \alpha + \sum_{k=1}^{12}\beta_k Issue_{ik}
+ \sum_{k=1}^{12}\gamma_k(Issue_{ik}\times Resolved_i)
+ \delta'Incidence_i + \eta'Controls_i + \rho OnlineReview_i + \epsilon_i.
\]

Controls are Brand, Region, Ownership Type, Honors Tier, Purpose of Stay, feedback type, and problem-incidence indicators. Resolution is defined only for reported cases; a reported case with blank resolution is excluded from this outcome regression, not recoded as unresolved.

Ridge regression selects \(\lambda\) from a fixed grid by expanding five-fold time-series CV. Ridge is used for prediction stability under correlated issue and control variables; coefficients are not used for conventional p-value claims. \(\beta_k\) and \(\gamma_k\) are conditional historical associations, not causal treatment effects.

## Costs and solution layer

The review data do not identify solution-level costs or effects. The solution catalog therefore exposes editable operating assumptions with three bases: `complaint` (per reported case), `guest` (per eligible guest), and `room_year` (recurring program). Default incremental cost is:

\[
C=h\times w_{dept}+c_{item}+n_{room}\times ADR\times d,
\]

where \(h\) is incremental labor hours, \(w_{dept}\) the BLS accommodation-industry mean hourly wage for the department (`data/labor_rates.csv`, scaled by the country labor index), \(c_{item}\) cash/goodwill cost, \(n_{room}\) displaced room nights, and \(d\) the displacement factor. The `effect` field is an editable business assumption and does not sum to one across actions.

## Limitations and safety

- Platform tags are silver labels, not a purpose-built human gold standard.
- Observational resolution associations are not causal estimates.
- Costs/effects require property calibration and owner approval.
- Email/message integrations need separate human-labeled validation before automation.
- Safety, security, accessibility, discrimination, serious hygiene, and legal-risk items bypass cost-only ranking.
