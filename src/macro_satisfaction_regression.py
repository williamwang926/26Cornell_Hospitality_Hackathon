"""Leakage-safe satisfaction model aligned to the dashboard's 12 issue categories.

The model uses only observed platform negative tags. It deliberately does *not*
infer tags from Problem Comments. Those live complaints are GM-tagged in the
dashboard design. Output coefficients are associations with ratings, not causal
effects of a particular solution.

Run from the repository root:
    python -m src.macro_satisfaction_regression
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import OneHotEncoder

from . import config as C

COUNTRY = "United States"
TEST_SHARE = 0.20
RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0, 500.0]
INCIDENCE_MAP = {
    "No, I did not experience a problem": "none",
    "Yes, and I reported the problem": "reported",
    "Yes, but I did not report the problem": "unreported",
}
RAW_COLUMNS = [
    C.C_HOTEL, C.C_DATE, C.C_RATING, C.C_INCIDENCE, C.C_RESOLUTION,
    C.C_L2, C.C_TOPIC_SENT, C.C_FEEDBACK_TYPE, C.C_COUNTRY, *C.CONTROLS,
]

MACROS = [
    "Amenities", "Arrival & departure", "Bathroom", "Billing & payments",
    "Customer service & recovery", "Digital & loyalty", "Food & beverage",
    "Public areas", "Reservations", "Room condition & comfort",
    "Safety & security", "Staff service",
]
FAMILY_TO_MACRO = {
    "Room": "Room condition & comfort", "Bathroom": "Bathroom",
    "Staff": "Staff service", "CustomerService": "Customer service & recovery",
    "PublicAreas": "Public areas", "Food/Beverage": "Food & beverage",
    "Arrival": "Arrival & departure", "Departure": "Arrival & departure",
    "Billing": "Billing & payments", "Amenities": "Amenities",
    "Reservations": "Reservations", "Security/Legal": "Safety & security",
    "DigitalExperience": "Digital & loyalty", "HiltonHonors": "Digital & loyalty",
}


def parse_negative_topics(l2, sentiment):
    allowed = set(str(l2).split(",")) if pd.notna(l2) else set()
    if not isinstance(sentiment, str):
        return []
    answer = []
    for part in sentiment.split(","):
        topic, _, label = part.rpartition(":")
        topic = topic.strip()
        if topic in allowed and label.strip() in C.NEGATIVE_LABELS:
            answer.append(topic)
    return sorted(set(answer))


def macro(topic: str):
    for prefix, category in FAMILY_TO_MACRO.items():
        if topic.startswith(prefix):
            return category
    return None


def load_us():
    cache = C.PROCESSED / "us_macro_satisfaction_raw.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    df = pd.read_csv(C.RAW_CSV, usecols=RAW_COLUMNS, low_memory=False)
    df = df[df[C.C_COUNTRY].eq(COUNTRY)].copy()
    df[C.C_DATE] = pd.to_datetime(df[C.C_DATE], errors="coerce")
    df = df.dropna(subset=[C.C_HOTEL, C.C_RATING, C.C_DATE]).copy()
    df["incidence"] = df[C.C_INCIDENCE].map(INCIDENCE_MAP).fillna("unknown")
    df["resolved"] = df[C.C_RESOLUTION].map({"Yes": 1.0, "No": 0.0})
    df.loc[df["incidence"] != "reported", "resolved"] = np.nan
    topics = [parse_negative_topics(a, b) for a, b in zip(df[C.C_L2], df[C.C_TOPIC_SENT])]
    df["macro_issues"] = [sorted({m for t in xs if (m := macro(t)) is not None}) for xs in topics]
    for raw_name, feature_name in C.CONTROLS.items():
        df[feature_name] = df[raw_name].fillna("unknown").astype(str)
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache)
    return df


def chronological_split(df):
    cutoff = df[C.C_DATE].quantile(1 - TEST_SHARE)
    return df[df[C.C_DATE] < cutoff].copy(), df[df[C.C_DATE] >= cutoff].copy(), cutoff


def rolling_folds(df, n_folds=5):
    dates = df[C.C_DATE].sort_values().drop_duplicates().to_numpy()
    points = np.linspace(0, len(dates) - 1, n_folds + 2, dtype=int)
    folds = []
    for i in range(1, n_folds + 1):
        start, end = dates[points[i]], dates[points[i + 1]]
        fit = df[df[C.C_DATE] < start]
        val = df[(df[C.C_DATE] >= start) & (df[C.C_DATE] < end)]
        if len(fit) and len(val):
            folds.append((fit, val))
    return folds


class Design:
    def __init__(self, training):
        self.controls = list(C.CONTROLS.values())
        self.encoder = OneHotEncoder(handle_unknown="ignore", drop="first")
        self.encoder.fit(training[self.controls].fillna("unknown").astype(str))

    def matrix(self, df):
        issue = np.zeros((len(df), len(MACROS)), dtype=np.float32)
        index = {name: j for j, name in enumerate(MACROS)}
        for i, values in enumerate(df["macro_issues"]):
            for value in values:
                issue[i, index[value]] = 1
        resolved = df["resolved"].eq(1).to_numpy(dtype=np.float32)[:, None]
        interaction = issue * resolved
        incidence = np.column_stack([
            (df["incidence"] == label).to_numpy(dtype=np.float32)
            for label in ["reported", "unreported", "unknown"]
        ])
        online = (df[C.C_FEEDBACK_TYPE] == "Online Review").to_numpy(dtype=np.float32)[:, None]
        controls = self.encoder.transform(df[self.controls].fillna("unknown").astype(str))
        return sp.hstack([
            sp.csr_matrix(issue), sp.csr_matrix(interaction), sp.csr_matrix(incidence),
            sp.csr_matrix(online), controls,
        ], format="csr")


def usable(df):
    # A blank resolution is non-applicable outside reported cases, but unknown for a
    # reported issue. Do not silently code those reported cases as unresolved.
    return df.loc[~(df["incidence"].eq("reported") & df["resolved"].isna())].copy()


def metrics(y, prediction):
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, prediction))),
        "mae": float(mean_absolute_error(y, prediction)),
        "r2": float(r2_score(y, prediction)),
        "spearman": float(spearmanr(y, prediction).statistic) if np.std(prediction) > 1e-12 else None,
    }


def select_alpha(train):
    scores = {alpha: [] for alpha in RIDGE_ALPHAS}
    details = []
    for fold, (fit_raw, val_raw) in enumerate(rolling_folds(train), 1):
        fit, val = usable(fit_raw), usable(val_raw)
        design = Design(fit)
        x_fit, x_val = design.matrix(fit), design.matrix(val)
        y_fit, y_val = fit[C.C_RATING].to_numpy(float), val[C.C_RATING].to_numpy(float)
        for alpha in RIDGE_ALPHAS:
            scores[alpha].append(np.sqrt(mean_squared_error(y_val, Ridge(alpha=alpha).fit(x_fit, y_fit).predict(x_val))))
        details.append({"fold": fold, "train_rows": int(len(fit)), "validation_rows": int(len(val)),
                        "validation_start": str(val[C.C_DATE].min()), "validation_end": str(val[C.C_DATE].max())})
        print(f"Finished macro regression fold {fold}/5: {len(fit):,} train, {len(val):,} validation", flush=True)
    means = {str(alpha): float(np.mean(values)) for alpha, values in scores.items()}
    chosen = min(RIDGE_ALPHAS, key=lambda alpha: np.mean(scores[alpha]))
    return chosen, means, details


def run():
    raw = load_us().sort_values(C.C_DATE).reset_index(drop=True)
    train_raw, test_raw, cutoff = chronological_split(raw)
    alpha, cv_scores, cv_folds = select_alpha(train_raw)
    train, test = usable(train_raw), usable(test_raw)
    design = Design(train)
    x_train, x_test = design.matrix(train), design.matrix(test)
    y_train, y_test = train[C.C_RATING].to_numpy(float), test[C.C_RATING].to_numpy(float)
    model = Ridge(alpha=alpha).fit(x_train, y_train)
    prediction = model.predict(x_test)
    coefficient = model.coef_
    macro_rows = []
    for j, name in enumerate(MACROS):
        macro_rows.append({
            "macro_category": name,
            "train_rows_with_issue": int(train["macro_issues"].map(lambda xs: name in xs).sum()),
            "test_rows_with_issue": int(test["macro_issues"].map(lambda xs: name in xs).sum()),
            "rating_association_if_issue_unresolved": float(coefficient[j]),
            "rating_association_when_resolved": float(coefficient[len(MACROS) + j]),
            "interpretation": "Associational; not solution-specific causal effect.",
        })
    table = pd.DataFrame(macro_rows).sort_values("rating_association_if_issue_unresolved")
    C.RESULTS.mkdir(exist_ok=True)
    table.to_csv(C.RESULTS / "macro_satisfaction_effects_us.csv", index=False)
    report = {
        "scope": {"country": COUNTRY, "raw_rows": int(len(raw)), "hotels": int(raw[C.C_HOTEL].nunique())},
        "model": "Ridge satisfaction regression at 12 dashboard macro-category level",
        "tag_policy": "Observed platform negative tags only; no tags are inferred from Problem Comments.",
        "time_split": {"final_holdout_cutoff": str(cutoff), "train_rows": int(len(train)), "test_rows": int(len(test)),
                       "reported_resolution_missing_train_excluded": int(len(train_raw) - len(train)),
                       "reported_resolution_missing_test_excluded": int(len(test_raw) - len(test))},
        "controls": ["Brand", "Region", "Ownership Type", "Honors Tier", "Purpose of Stay", "Online Review", "Problem Incidence"],
        "macro_categories": MACROS,
        "ridge_alpha_selected_by_rolling_5_fold_cv": alpha,
        "rolling_cv_rmse_by_alpha": cv_scores,
        "rolling_cv_folds": cv_folds,
        "final_holdout": {"baseline_mean": metrics(y_test, np.repeat(y_train.mean(), len(y_test))),
                          "macro_ridge": metrics(y_test, prediction)},
        "limits": [
            "Resolution coefficients are associations with ratings, not causal effects of resolution or a particular solution.",
            "Solution-level effectiveness and costs remain editable operating assumptions.",
            "No hotel-specific Model B is used because its prior holdout gain was immaterial.",
        ],
    }
    (C.RESULTS / "macro_satisfaction_regression_us.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("\nMacro-category associations:")
    print(table.to_string(index=False))


if __name__ == "__main__":
    run()
