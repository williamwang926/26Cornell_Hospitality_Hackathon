"""Export the editable department-manager solution catalog for the dashboard.

The issue layer contains twelve macro categories. A department manager selects a
fine issue before choosing a solution. Costs and effects in data/solutions.csv
are operating assumptions, not estimates from the review regression; owners may
override them in the dashboard.

Run: python -m src.macro_solution_catalog
"""
from __future__ import annotations

import json

import pandas as pd

from . import config as C

FAMILY_TO_MACRO = {
    "Room": "Room condition & comfort", "Bathroom": "Bathroom",
    "Staff": "Staff service", "CustomerService": "Customer service & recovery",
    "PublicAreas": "Public areas", "Food/Beverage": "Food & beverage",
    "Arrival": "Arrival & departure", "Departure": "Arrival & departure",
    "Billing": "Billing & payments", "Amenities": "Amenities",
    "Reservations": "Reservations", "Security/Legal": "Safety & security",
    "DigitalExperience": "Digital & loyalty", "HiltonHonors": "Digital & loyalty",
}


def macro_for(topic: str) -> str | None:
    for prefix, macro in FAMILY_TO_MACRO.items():
        if topic.startswith(prefix):
            return macro
    return None


def run():
    taxonomy = pd.read_csv(C.ROOT / "data" / "issue_taxonomy.csv")
    catalog = pd.read_csv(C.SOLUTIONS).copy()
    catalog = catalog[catalog["topic"] != "*"].copy()
    catalog["macro_category"] = catalog["topic"].map(macro_for)
    catalog = catalog.dropna(subset=["macro_category"])
    catalog["manager_confirmation_required"] = True
    catalog["effect_type"] = "Editable operating assumption (not data-estimated)"
    catalog["cost_formula"] = (
        "labor_hours × property loaded hourly rate + item_cost_usd + "
        "room_nights × local ADR × displacement factor"
    )
    catalog = catalog.merge(taxonomy[["macro_category", "owner_department", "priority_mode"]],
                            on="macro_category", how="left")
    columns = [
        "macro_category", "topic", "owner_department", "priority_mode", "solution",
        "description", "basis", "purpose", "tier", "labor_dept", "labor_hours",
        "item_cost_usd", "room_nights", "uptake", "effect", "effect_type",
        "cost_formula", "manager_confirmation_required",
    ]
    catalog = catalog[columns].sort_values(["macro_category", "topic", "basis", "solution"])
    C.RESULTS.mkdir(exist_ok=True)
    catalog.to_csv(C.RESULTS / "department_solution_catalog.csv", index=False)
    grouped = []
    for macro, group in catalog.groupby("macro_category", sort=True):
        meta = taxonomy.loc[taxonomy["macro_category"].eq(macro)].iloc[0].to_dict()
        grouped.append({**meta, "solutions": group.drop(columns=["macro_category", "owner_department", "priority_mode"])
                        .to_dict(orient="records")})
    (C.RESULTS / "department_solution_catalog.json").write_text(json.dumps(grouped, indent=2))
    print(f"Exported {len(catalog):,} editable solution rows across {len(grouped)} macro categories.")


if __name__ == "__main__":
    run()
