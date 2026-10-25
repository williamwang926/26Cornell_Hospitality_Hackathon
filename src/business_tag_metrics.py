"""Business-facing evaluation for the existing TF-IDF tag classifier.

This file does not alter the raw data, train/test split, original labels, or the
strict F1 report.  It adds a transparent dashboard metric:

  Top-3 supported macro-category coverage =
  (# true supported categories appearing in the 3 suggestions) /
  (# true supported categories)

Extra suggestions are deliberately not penalized in this *coverage* metric, but
the list is capped at three categories so a model cannot score well by returning
every tag.  It is therefore not ordinary accuracy or F1.

Run from the HiltonHackathon repository root after replacing this file in src/:
    python -m src.business_tag_metrics
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
import pandas as pd

from . import config as C
from .temporal_validation import (
    VALIDATION_SHARE_OF_TRAIN,
    chronological_split,
    load_text_training_pool,
    load_us,
    train_text_model,
)

TOP_K = 3
MIN_TRAIN_POSITIVES = 300

# Fixed operational taxonomy, set before looking at the final-holdout results.
# Every original tag maps by its leading family; the four no-hyphen families are
# explicitly assigned here. This is a derived reporting taxonomy only.
FAMILY_TO_MACRO = {
    "Room": "Room condition & comfort",
    "Bathroom": "Bathroom",
    "Staff": "Staff service",
    "Staff Position ": "Staff service",
    "CustomerService": "Customer service & recovery",
    "PublicAreas": "Public areas",
    "Food/Beverage": "Food & beverage",
    "Arrival": "Arrival & departure",
    "Departure": "Arrival & departure",
    "Billing": "Billing & payments",
    "Amenities": "Amenities",
    "Reservations": "Reservations",
    "Security/Legal": "Safety & security",
    "DigitalExperience": "Digital & loyalty",
    "HiltonHonors": "Digital & loyalty",
}


def macro(topic: str) -> str | None:
    """Map a raw negative topic to one pre-specified operational macro category."""
    for prefix, result in FAMILY_TO_MACRO.items():
        if topic.startswith(prefix):
            return result
    return None


def topic_categories(topics, supported_topics: set[str]) -> set[str]:
    return {m for t in topics if t in supported_topics if (m := macro(t)) is not None}


def run():
    # Same leakage-safe temporal protocol as temporal_validation.py.
    us = load_us().sort_values(C.C_DATE).reset_index(drop=True)
    _, final_test, test_cutoff = chronological_split(us)
    pool = load_text_training_pool()
    historical = pool[pool[C.C_DATE] < test_cutoff].copy()
    threshold_date = historical[C.C_DATE].quantile(1 - VALIDATION_SHARE_OF_TRAIN)
    text_fit = historical[historical[C.C_DATE] < threshold_date].copy()
    text_val = historical[historical[C.C_DATE] >= threshold_date].copy()

    # The classifier is the unchanged, selected TF-IDF + OVR linear baseline.
    model, _, _, _ = train_text_model(text_fit, text_val)

    # Long-tail eligibility is decided only from the pre-holdout training period.
    train_counts = text_fit["platform_topics"].explode().value_counts()
    supported_topics = {
        topic for topic, count in train_counts.items()
        if count >= MIN_TRAIN_POSITIVES and macro(topic) is not None and topic in set(model.labels)
    }

    test = final_test[final_test[C.C_FEEDBACK].notna() & final_test[C.C_L2].notna()].copy()
    probabilities = model.model.predict_proba(model.vectorizer.transform(test[C.C_FEEDBACK].fillna("")))
    label_index = {topic: i for i, topic in enumerate(model.labels)}
    by_macro = defaultdict(list)
    for topic in supported_topics:
        by_macro[macro(topic)].append(label_index[topic])

    # A macro category receives the strongest probability of one of its supported
    # child tags. The UI shows no more than TOP_K category suggestions.
    macro_names = sorted(by_macro)
    macro_probability = np.column_stack([
        probabilities[:, by_macro[name]].max(axis=1) for name in macro_names
    ])
    top_indices = np.argsort(-macro_probability, axis=1)[:, :TOP_K]
    suggested = [{macro_names[j] for j in row} for row in top_indices]
    truth = [topic_categories(xs, supported_topics) for xs in test["platform_topics"]]

    eligible = [(actual, guessed) for actual, guessed in zip(truth, suggested) if actual]
    true_total = sum(len(actual) for actual, _ in eligible)
    covered_total = sum(len(actual & guessed) for actual, guessed in eligible)
    category_recalls = {
        name: (sum(name in actual and name in guessed for actual, guessed in eligible) /
               sum(name in actual for actual, _ in eligible))
        for name in macro_names
        if sum(name in actual for actual, _ in eligible) > 0
    }

    report = {
        "metric_name": f"Top-{TOP_K} supported macro-category coverage (Recall@{TOP_K})",
        "definition": (
            "Of all true, supported operational macro-categories, the share included in the "
            f"model's top {TOP_K} suggestions. Extra suggestions are not counted as errors; "
            "this is a candidate-coverage metric, not accuracy or F1."
        ),
        "scope": "United States; final chronological holdout; Open Feedback (English) only",
        "model": "Existing TF-IDF word-bigram + one-vs-rest linear baseline; no Transformer",
        "anti_leakage": (
            "Test cutoff, threshold-validation period, supported-tag set, and macro taxonomy "
            "are determined without using final-holdout outcomes."
        ),
        "top_k": TOP_K,
        "min_train_positives_per_raw_tag": MIN_TRAIN_POSITIVES,
        "raw_tags_in_model": int(len(model.labels)),
        "supported_raw_tags": int(len(supported_topics)),
        "supported_macro_categories": macro_names,
        "final_holdout_rows_with_platform_tags": int(len(test)),
        "eligible_holdout_rows_with_supported_category": int(len(eligible)),
        "excluded_holdout_rows_rare_or_unmapped_only": int(len(test) - len(eligible)),
        "true_supported_category_instances": int(true_total),
        "covered_supported_category_instances": int(covered_total),
        "top_k_macro_coverage_recall": float(covered_total / true_total) if true_total else None,
        "adjusted_error_rate_for_dashboard": float(1 - covered_total / true_total) if true_total else None,
        "macro_average_category_coverage": float(np.mean(list(category_recalls.values()))) if category_recalls else None,
        "per_macro_category_recall": category_recalls,
        "disclosure": (
            "Rare raw tags are not silently treated as successes: they route to Other / GM Review. "
            "Keep the original strict raw-tag Micro-F1 alongside this business metric."
        ),
    }
    C.RESULTS.mkdir(exist_ok=True)
    out = C.RESULTS / "business_tag_metrics_us.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
