# Private GitHub Release Checklist

Run this checklist immediately before the first push and before every later public-sharing decision.

## Required for the private repository

- [ ] Confirm `.gitignore` excludes `data/dashboard-export-*.csv`, `data/processed/`, `models/`, `.venv/`, and temporary files.
- [ ] Run `git status --short` and verify no raw CSV, ZIP, Parquet, Pickle, trained model, guest text, API key, or `.env` file appears.
- [ ] Confirm the data-rights statement names Hilton and the 2026 Hospitality Hackathon.
- [ ] Verify generated `results/` files contain only approved aggregate/model outputs; remove property-level records if they are not authorized for the private team repository.
- [ ] Re-run the documented scripts on the authorized local data source and retain the resulting JSON/CSV metadata with the commit hash.
- [ ] Review README claims: use “historical association,” “candidate coverage,” and “editable assumption”; do not claim causal solution effects or ordinary accuracy where Recall@3 is reported.

## Suggested Git commands

```bash
git status --short
git add README.md .gitignore docs/ data/issue_taxonomy.csv src/ results/department_solution_catalog.csv results/department_solution_catalog.json
git diff --cached --check
git commit -m "Add reproducible methodology and manager solution catalog"
git push origin main
```

Do **not** use `git add .` until the status review is complete.

## Before making anything public

Stop and obtain explicit written approval from the data owner/hackathon organizer. A private-team repository is not the same as a public data release.
