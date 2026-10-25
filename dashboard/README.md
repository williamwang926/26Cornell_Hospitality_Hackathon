# Dashboard Embed Placeholder

This directory deliberately contains no dashboard implementation in the current release.

When a front end is added, it should mount inside `embed.html` and read only approved, non-sensitive aggregate artifacts. The expected product flow is:

1. Receive feedback text from an authorized integration.
2. Show at most three AI-suggested **macro categories** with a confidence signal.
3. Require GM confirmation and department-manager selection of the fine issue.
4. Display the corresponding entries from `results/department_solution_catalog.json`.
5. Allow property owners to edit local cost/effect assumptions and retain an audit trail.

The front end must not expose raw guest text, property IDs, the raw CSV, or model training data in static assets. It must display the methodological disclosures in `docs/DASHBOARD_CONTRACT.md`.
