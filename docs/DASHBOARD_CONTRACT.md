# Dashboard Contract

## Decision rights

| Actor | System role | Human responsibility |
|---|---|---|
| AI intake | Suggest at most three supported macro categories from Open Feedback | Never closes a case or sets compensation. |
| GM | Confirm macro category, urgency, owner, and escalation | May override AI and cost ranking. |
| Department manager | Select fine issue and solution | Confirms feasibility, capacity, cost, and action. |
| Property owner | Edits labor/cash/effect defaults | Owns local assumptions. |

## Intended flow

1. Feedback enters the dashboard.
2. AI offers up to three macro-category candidates and a confidence signal.
3. GM confirms one or more categories; urgent items escalate.
4. Department manager selects a fine issue and sees corresponding preventive/recovery options.
5. The system displays historical rating association, incremental cost breakdown, and editable assumed effect.
6. The manager records the chosen action and outcome. That future log can support true action-level evaluation.

Required disclosures: “Historical rating association; not causal”; “Default cost/effect values are editable assumptions”; “Candidate coverage is not full classification accuracy”; and “Safety/legal items override cost ranking.”
