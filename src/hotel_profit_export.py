"""Per-hotel guest-complaint ranking by Stay Score gained per dollar, for the static dashboard.

For a selected hotel the dashboard lists a fixed set of guest complaints (data/guest_complaints.csv;
each maps to one Model B topic = its case type, and several complaints may share a case type) ranked by the best solution's Stay Score gained per $1,000 of annual cost,
using that hotel's OWN Model B regression (source results/model_b_hotel_scores.csv).

Gain of a solution (source solutions.solution_costs, guide 7.4, per hotel x topic):
  Prevent:  gain = prevent_gain(hotel, topic) x effect x seg_complaints(audience)
  Resolve:  gain = resolve_gain(hotel, topic) x effect x seg_complaints(audience)
  stay_score_gain   = gain x stay_score_per_rating_point (30.2)
  stay_score_per_1k = stay_score_gain / annual_cost x 1000          (ranking metric)
Per hotel x complaint: complaints, reviews_in_window, incidence = complaints / reviews_in_window,
full_fix_stay_score = prevent_gain x 30.2, solutions sorted by stay_score_per_1k desc.
Per case (one complaint fixed): cases_per_year = source fixed_per_year; cost_per_case,
stay_score_per_case, profit_per_case = annual_cost, stay_score_gain, profit_gain / cases_per_year;
net_per_case = profit_per_case - cost_per_case; guest_rating_lift = max(0, resolve_weight (Resolve) or
prevent_weight (Prevent)) x effect. Each complaint entry also carries unresolved_reported and the
hotel's resolve_weight / prevent_weight for the case type.

Solutions, unit cost, uses, annual cost and segment shares come from the SOURCE repo
(src.solutions.solution_costs: catalog_for fallback topic -> Level 1 -> '*'), with one change:
labor is priced at the BLS 2025 accommodation-industry (NAICS 721) mean hourly WAGE per labor_dept
from data/labor_rates.csv (wages only, no benefits loading) instead of the source's loaded P&L
hourly rates (PRICING_MODEL; the country labor_index still scales the wage). The source catalog
(data/solutions.csv) is extended with this repo's data/solutions_extra.csv (same columns; appended
rows add options to their topic, since catalog_for returns every row of the topic). Every catalog
solution is written once per hotel x complaint with ONE audience: all-guest -> "All guests",
Business / Leisure purpose -> that purpose, Gold & Diamond tier -> "Elite status", and any solution
whose name/description mentions famil(y/ies) -> only "Families" (re-targeted to the Family segment).
Family shares (Purpose of Stay Details == Family) are built from the raw export with the
source's build_segment_shares logic and cached in data/family_shares.csv. The money side comes
from src.price_model.hotel_parameters / price_actions / value_of_gain. The source package is
loaded under the alias `hilton_src` so it does not clash with this repo's `src` package.

Output: dashboard/data/hotel_index.js (window.HOTEL_INDEX) and one
dashboard/data/hotels/<hotel>.js per hotel (window.HOTEL_PROFIT_LOAD(id, data)).

Run:
  python -m src.hotel_profit_export [--source /path/to/HiltonHackathon] [--raw export.csv]
                                    [--rebuild-family-shares]
  (default source: $HILTON_SOURCE_REPO, else ../../HiltonHackathon from this repo's root;
   default raw export: $HILTON_RAW_CSV, else /Users/justin/Hilton/Data/dashboard-export-...csv)
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = (ROOT / ".." / ".." / "HiltonHackathon").resolve()
DEFAULT_RAW = Path("/Users/justin/Hilton/Data/dashboard-export-06-01-pm-2026-10-23.csv")
COMPLAINTS = ROOT / "data" / "guest_complaints.csv"
FAMILY_SHARES = ROOT / "data" / "family_shares.csv"
LABOR_RATES = ROOT / "data" / "labor_rates.csv"
EXTRA_SOLUTIONS = ROOT / "data" / "solutions_extra.csv"
PRICING_MODEL = ("Unit cost = labor hours × BLS hourly wage (× country labor index) + item cost (× price index) "
                 "+ displaced room nights × ADR × 0.25; annual cost = unit cost × uses")
OUT_DIR = ROOT / "dashboard" / "data"
HOTELS_DIR = OUT_DIR / "hotels"
OLD_OUTPUTS = [OUT_DIR / "hotel_profit.js", OUT_DIR / "hotel_profit.json"]

# Audience -> (purpose, tier) in the source's segment vocabulary. "Family" is a purpose segment
# added from data/family_shares.csv (Purpose of Stay Details == Family).
AUDIENCES = ["Leisure", "Business", "Families", "Elite status", "All guests"]
FAMILY_SEG = "Family"
FAMILY_COL = "Purpose of Stay Details"
FAMILY_RE = re.compile(r"famil(y|ies)", re.I)

ROW_COLUMNS = ["type", "solution", "description", "for", "source", "basis", "unit_cost", "uses",
               "annual_cost", "gain", "stay_score_gain", "stay_score_per_1k", "predicted_stay_score",
               "revenue_gain", "profit_gain", "profit_low", "profit_high", "net_profit", "roi",
               "cases_per_year", "cost_per_case", "stay_score_per_case", "profit_per_case", "net_per_case",
               "guest_rating_lift"]
DOLLARS = {"unit_cost", "annual_cost", "revenue_gain", "profit_gain", "profit_low", "profit_high", "net_profit"}
CENTS = {"cost_per_case", "profit_per_case", "net_per_case"}
SIX = {"stay_score_per_case"}
THREE = {"guest_rating_lift"}
TWO = {"cases_per_year"}
FIVE = {"gain", "stay_score_gain", "stay_score_per_1k", "predicted_stay_score"}
FOUR = {"roi", "uses", "incidence"}
DISCLOSURES = ["Historical rating association; not causal",
               "Default cost/effect values are editable assumptions",
               "Candidate coverage is not full classification accuracy",
               "Safety/legal items override cost ranking"]


# ---------------------------------------------------------------------------------------------
# Loading the source repo's package under an alias
# ---------------------------------------------------------------------------------------------
def load_source(source: Path):
    """Import SOURCE/src as package `hilton_src`; returns (price_model, solutions, config)."""
    pkg_dir = source / "src"
    if not (pkg_dir / "__init__.py").exists():
        raise SystemExit(f"Source repo not found or has no src/__init__.py: {source}")
    alias = "hilton_src"
    if alias not in sys.modules:
        spec = importlib.util.spec_from_file_location(alias, pkg_dir / "__init__.py",
                                                      submodule_search_locations=[str(pkg_dir)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = mod
        spec.loader.exec_module(mod)
    price_model = importlib.import_module(f"{alias}.price_model")
    solutions = importlib.import_module(f"{alias}.solutions")
    config = importlib.import_module(f"{alias}.config")
    return price_model, solutions, config


def git_short_hash(path: Path):
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip() or None
    except Exception:
        return None


def load_complaints(topics) -> pd.DataFrame:
    c = pd.read_csv(COMPLAINTS, keep_default_na=False)
    if c["complaint_id"].duplicated().any():
        raise SystemExit(f"{COMPLAINTS.name}: duplicate complaint_id")
    if not c["urgent"].isin(["yes", "no"]).all():
        raise SystemExit(f"{COMPLAINTS.name}: urgent must be yes/no")
    missing = sorted(set(c["topic"]) - set(topics))
    if missing:
        print(f"WARNING: complaint topics not in Model B scores (all hotels get zeros): {missing}")
    return c


# ---------------------------------------------------------------------------------------------
# Family shares (mirror of hilton_src.solutions.build_segment_shares for one segment)
# ---------------------------------------------------------------------------------------------
def build_family_shares(raw: Path, solutions, C) -> pd.DataFrame:
    """hotel x topic -> Family share of the topic's complaints among reviews with a known
    Purpose of Stay Details (topic "_stays": of all reviews), shrunk toward the network."""
    d = pd.read_csv(raw, usecols=[C.C_HOTEL, C.C_TOPIC_SENT, FAMILY_COL], low_memory=False)
    d = d.dropna(subset=[C.C_HOTEL])
    d["hotel"] = d[C.C_HOTEL].astype(int)
    d["topic"] = d[C.C_TOPIC_SENT].fillna("").map(lambda s: [t.strip() for t in solutions.NEG.findall(s)])
    long = d.explode("topic").dropna(subset=["topic"])
    stays = d.assign(topic="_stays")
    rows = []
    for frame in (long, stays):
        known = frame[frame[FAMILY_COL].notna()]
        n = known.groupby(["hotel", "topic"]).size()
        net_n = known.groupby("topic").size()
        hit = known[FAMILY_COL].isin([FAMILY_SEG])
        k = known[hit].groupby(["hotel", "topic"]).size().reindex(n.index, fill_value=0)
        net = (known[hit].groupby("topic").size() / net_n).fillna(0)
        prior = net.reindex(n.index.get_level_values("topic")).values
        share = (k + solutions.SHRINK * prior) / (n + solutions.SHRINK)
        rows.append(pd.DataFrame({"dim": "purpose", "segment": FAMILY_SEG, "share": share}).reset_index())
    out = pd.concat(rows).round({"share": 4})[["hotel", "topic", "dim", "segment", "share"]]
    FAMILY_SHARES.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(FAMILY_SHARES, index=False)
    return out


def load_family_shares(raw: Path, solutions, C, rebuild: bool) -> pd.DataFrame:
    if rebuild or not FAMILY_SHARES.exists():
        if not raw.exists():
            raise SystemExit(f"Raw export not found (needed to build {FAMILY_SHARES}): {raw}")
        print(f"Building {FAMILY_SHARES.name} from {raw.name} ...")
        return build_family_shares(raw, solutions, C)
    return pd.read_csv(FAMILY_SHARES)


# ---------------------------------------------------------------------------------------------
# Catalog with one audience per solution
# ---------------------------------------------------------------------------------------------
def combined_catalog(solutions) -> pd.DataFrame:
    """Source data/solutions.csv + this repo's data/solutions_extra.csv (same columns)."""
    base = solutions.load_catalog()
    if not EXTRA_SOLUTIONS.exists():
        return base
    extra = pd.read_csv(EXTRA_SOLUTIONS)
    if list(extra.columns) != list(base.columns):
        raise SystemExit(f"{EXTRA_SOLUTIONS.name}: columns must match the source solutions.csv {list(base.columns)}")
    dup = extra.merge(base, on=["topic", "solution", "purpose", "tier"])
    if len(dup):
        raise SystemExit(f"{EXTRA_SOLUTIONS.name}: rows already in the source catalog: {dup[['topic', 'solution']].values.tolist()}")
    return pd.concat([base, extra], ignore_index=True)


def audience_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    """Source catalog with exactly one audience per row (no copies).
    Family-named solutions are re-targeted to the Family purpose segment (tier All), so the
    source prices them with the Families seg_stays / seg_complaints; `family` flags them."""
    out = []
    for r in catalog.to_dict("records"):
        if FAMILY_RE.search(f"{r['solution']} {r['description']}"):
            out.append({**r, "purpose": FAMILY_SEG, "tier": "All", "family": True, "audience": "Families"})
            continue
        if r["purpose"] == "All" and r["tier"] == "All":
            aud = "All guests"
        elif r["tier"] == "Gold & Diamond":
            aud = "Elite status"
        elif r["purpose"] in ("Business", "Leisure"):
            aud = r["purpose"]
        else:
            aud = ""
        out.append({**r, "family": False, "audience": aud})
    return pd.DataFrame(out)


def load_labor_rates(catalog: pd.DataFrame) -> pd.DataFrame:
    """data/labor_rates.csv indexed by labor_dept; every catalog labor_dept must have a wage."""
    r = pd.read_csv(LABOR_RATES, keep_default_na=False).set_index("labor_dept")
    if r.index.duplicated().any():
        raise SystemExit(f"{LABOR_RATES.name}: duplicate labor_dept")
    missing = sorted(set(catalog["labor_dept"]) - set(r.index))
    if missing:
        raise SystemExit(f"{LABOR_RATES.name}: no wage for labor_dept {missing}")
    r["hourly_wage_usd"] = r["hourly_wage_usd"].astype(float)
    return r


def wage_benchmarks(load_benchmarks, wages: dict):
    """Source load_benchmarks with every benchmark's hourly_rates replaced by `wages`
    (occupancy, ADR and the P&L are unchanged)."""
    def load():
        bms = load_benchmarks()
        for bm in bms.values():
            bm.hourly_rates = dict(wages)
        return bms
    return load


@contextlib.contextmanager
def patched(mod, **attrs):
    old = {k: getattr(mod, k) for k in attrs}
    for k, v in attrs.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


# ---------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------
def build(source: Path, raw: Path, rebuild_family: bool, topics):
    """topics: the complaint list's case types; solutions are costed only for these."""
    price_model, solutions, C = load_source(source)

    tiers = pd.read_csv(source / "results" / "hotel_tiers.csv", index_col="hotel")
    tiers.index = tiers.index.astype(int)
    locations = pd.read_csv(source / "data" / "hotel_locations.csv", index_col="hotel")
    scores = pd.read_csv(source / "results" / "model_b_hotel_scores.csv")
    scores["hotel"] = scores["hotel"].astype(int)
    scores = scores[scores["hotel"].isin(tiers.index)].reset_index(drop=True)
    scores["incidence"] = np.where(scores["reviews_in_window"] > 0,
                                   scores["complaints"] / scores["reviews_in_window"].where(
                                       scores["reviews_in_window"] > 0, 1), 0.0)

    params = price_model.hotel_parameters(tiers)
    a_ss = float(params["stay_score_per_rating_point"].iloc[0])
    scores["full_fix_stay_score"] = scores["prevent_gain"].fillna(0) * a_ss

    # Shares: source purpose/tier shares + our Family purpose segment
    family = load_family_shares(raw, solutions, C, rebuild_family)
    shares = pd.concat([solutions.load_segment_shares(), family], ignore_index=True)
    catalog = audience_catalog(combined_catalog(solutions))
    labor = load_labor_rates(catalog)
    wages = labor["hourly_wage_usd"].to_dict()

    # Source solution costing with the hotel's own Model B prevent_gain / resolve_gain (guide 7.4):
    # gain = prevent_gain x effect x seg_complaints (Prevent) or resolve_gain x ... (Resolve).
    active = scores[(scores["reviews_in_window"] > 0) & (scores["complaints"] > 0)
                    & scores["topic"].isin(topics)].reset_index(drop=True)
    active[["prevent_gain", "resolve_gain"]] = active[["prevent_gain", "resolve_gain"]].fillna(0.0)
    # Labor priced at BLS wages (data/labor_rates.csv) instead of the source's loaded P&L rates.
    with patched(solutions, load_catalog=lambda: catalog, load_segment_shares=lambda: shares,
                 load_benchmarks=wage_benchmarks(solutions.load_benchmarks, wages)):
        sol = solutions.solution_costs(active, tiers)

    # Map each row back to its audience-catalog row (sid = position within catalog_for(topic))
    lookup = {t: solutions.catalog_for(t, catalog)[["family", "audience", "effect"]].to_numpy() for t in sol["topic"].unique()}
    m = np.array([lookup[t][i] for t, i in zip(sol["topic"], sol["sid"])], dtype=object)
    sol["family"], sol["audience"], sol["effect"] = m[:, 0].astype(bool), m[:, 1], m[:, 2].astype(float)

    # Family room_year programs are sized to the Families share of stays (source: all rooms)
    sh = shares.set_index(["hotel", "topic", "dim", "segment"])["share"]

    def stay_share(hotel, dim, seg):
        return 1.0 if seg == "All" else float(sh.get((hotel, "_stays", dim, seg), 0.0))

    ry = sol["family"] & sol["basis"].eq("room_year")
    seg_stays = [stay_share(h, "purpose", p) * stay_share(h, "tier", t)
                 for h, p, t in zip(sol.loc[ry, "hotel"], sol.loc[ry, "purpose"], sol.loc[ry, "tier"])]
    sol.loc[ry, "uses"] = sol.loc[ry, "uses"] * np.array(seg_stays, dtype=float)
    sol["annual_cost"] = sol["unit_cost"] * sol["uses"]

    n_all = len(sol)
    sol = sol[(sol["gain"] > 0) & (sol["annual_cost"] > 0)].reset_index(drop=True)

    # One audience per row; rows with no audience (none expected) are dropped
    unplaced = int(sol["audience"].eq("").sum())
    sol = sol[sol["audience"].ne("")].reset_index(drop=True)
    sol["for"] = sol["audience"]
    sol["source"] = np.where(sol["audience"].eq("All guests"), "All guests", "Targeted")

    # base/low/high value_of_gain, stay_score_gain, stay_score_per_1k, net_profit, roi
    sol = price_model.price_actions(sol, params)
    P = params.reindex(sol["hotel"].values)
    sol["predicted_stay_score"] = P["stay_score"].to_numpy() + sol["stay_score_gain"]
    sol["revenue_gain"] = sol["total_revenue_gain"]

    # Per-case metrics. cases_per_year = the source's fixed_per_year (guide 7.4): complaint basis
    # uses x effect; guest / room_year basis complaints x per_review x seg_complaints x effect.
    # Rows with no case fixed a year (none expected once gain > 0) are dropped.
    sol["cases_per_year"] = sol["fixed_per_year"].fillna(0.0)
    no_cases = int((sol["cases_per_year"] <= 0).sum())
    sol = sol[sol["cases_per_year"] > 0].reset_index(drop=True)
    n = sol["cases_per_year"]
    sol["cost_per_case"] = sol["annual_cost"] / n
    sol["stay_score_per_case"] = sol["stay_score_gain"] / n
    sol["profit_per_case"] = sol["profit_gain"] / n
    sol["net_per_case"] = sol["profit_per_case"] - sol["cost_per_case"]
    # The one guest whose case is fixed: this hotel's Model B weight (rating points per affected
    # review) for the case type x effect; Resolve -> resolve_weight, Prevent -> prevent_weight; <= 0 -> 0.
    w = scores.set_index(["hotel", "topic"])[["prevent_weight", "resolve_weight"]].fillna(0.0)
    wi = pd.MultiIndex.from_arrays([sol["hotel"], sol["topic"]])
    weight = np.where(sol["type"].eq("Resolve"), w["resolve_weight"].reindex(wi).to_numpy(),
                      w["prevent_weight"].reindex(wi).to_numpy())
    sol["guest_rating_lift"] = np.clip(np.nan_to_num(weight.astype(float)), 0, None) * sol["effect"]
    sol["basis"] = sol["basis"].map(solutions.BASIS_LABEL)
    sol = sol.sort_values(["hotel", "topic", "stay_score_per_1k", "profit_gain"],
                          ascending=[True, True, False, False]).reset_index(drop=True)
    info = {"rows_before_filter": n_all, "targeted_unplaced": unplaced, "labor": labor, "no_cases": no_cases}
    return price_model, scores, sol, params, tiers, locations, info


# ---------------------------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------------------------
def _num(v, digits):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    if digits == 0:
        return int(round(v))
    return round(float(v), digits)


def fmt(col, v):
    if col in CENTS:
        return _num(v, 2)
    if col in SIX:
        return _num(v, 6)
    if col in THREE:
        return _num(v, 3)
    if col in TWO:
        return _num(v, 2)
    if col in DOLLARS:
        return _num(v, 0)
    if col in FIVE:
        return _num(v, 5)
    if col in FOUR:
        return _num(v, 4)
    if isinstance(v, (np.floating, float)):
        return _num(float(v), 5)
    if isinstance(v, np.integer):
        return int(v)
    return v


def _clean(v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return _clean(float(v))
    return v


def index_payload(params, tiers, locations, complaints, source, labor):
    hotels = []
    for h in sorted(params.index):
        p, t = params.loc[h], tiers.loc[h]
        hotels.append({
            "hotel": str(h), "brand": _clean(p["brand"]), "hotel_class": _clean(p["hotel_class"]),
            "region": _clean(t["region"]), "country": _clean(locations["country"].get(h)),
            "ownership": _clean(p["ownership"]), "rooms": _num(p["rooms"], 0),
            "avg_rating": _num(p["avg_rating"], 5), "stay_score": _num(p["stay_score"], 5),
        })
    meta = {
        "generated": dt.date.today().isoformat(),
        "source_repo_commit": git_short_hash(source),
        "stay_score_per_rating_point": float(params["stay_score_per_rating_point"].iloc[0]),
        "audiences": AUDIENCES,
        "row_columns": ROW_COLUMNS,
        "complaints": [{"complaint_id": r["complaint_id"], "complaint": r["complaint"],
                        "also_heard_as": r["also_heard_as"], "topic": r["topic"],
                        "macro_category": r["macro_category"], "owner_department": r["owner_department"],
                        "safety": r["priority_mode"] == "emergency_override",
                        "urgent": r["urgent"] == "yes", "case_type": r["topic"]}
                       for r in complaints.to_dict("records")],
        "disclosures": DISCLOSURES,
        "pricing_model": PRICING_MODEL,
        "labor_rates": {d: round(float(w), 2) for d, w in labor["hourly_wage_usd"].items()},
        "labor_rate_occupations": labor["bls_occupation"].to_dict(),
        "labor_rate_sources": labor["source_url"].to_dict(),
    }
    return {"meta": meta, "hotels": hotels}


def _w(v):
    v = float(v)
    return v if math.isfinite(v) else 0.0


def hotel_payload(h, scores_h, sol_h, complaints):
    """scores_h: this hotel's Model B rows (indexed by topic); sol_h: this hotel's solution rows."""
    by_topic = {t: g for t, g in sol_h.groupby("topic", sort=False)} if len(sol_h) else {}
    out = []
    for c in complaints.itertuples(index=False):
        s = scores_h.loc[c.topic] if c.topic in scores_h.index else None
        g = by_topic.get(c.topic)
        rows = [] if g is None else [
            [fmt(col, v) for col, v in zip(ROW_COLUMNS, row)]
            for row in g.sort_values(["stay_score_per_1k", "profit_gain"], ascending=False)[ROW_COLUMNS]
            .itertuples(index=False, name=None)]
        n = 0 if s is None else int(s["complaints"])
        ix_k = ROW_COLUMNS.index("stay_score_per_1k")
        out.append({
            "complaint_id": c.complaint_id,
            "has_data": bool(n > 0 and rows),
            "complaints": n,
            "reviews_in_window": 0 if s is None else int(s["reviews_in_window"]),
            "incidence": 0.0 if s is None else _num(s["incidence"], 4),
            "full_fix_stay_score": 0.0 if s is None else _num(s["full_fix_stay_score"], 5),
            "unresolved_reported": 0 if s is None else int(s["unresolved_reported"]),
            "resolve_weight": 0.0 if s is None else _num(_w(s["resolve_weight"]), 4),
            "prevent_weight": 0.0 if s is None else _num(_w(s["prevent_weight"]), 4),
            "best_stay_score_per_1k": rows[0][ix_k] if rows else 0.0,
            "solutions": rows,
        })
    out.sort(key=lambda c: c["best_stay_score_per_1k"], reverse=True)  # stable: file order on ties
    return {"hotel": str(h), "complaints": out}


def _dump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _assert_clean(payload):
    for c in payload["complaints"]:
        for k in ("complaints", "reviews_in_window", "incidence", "full_fix_stay_score", "best_stay_score_per_1k",
                  "unresolved_reported", "resolve_weight", "prevent_weight"):
            if c[k] is None:
                raise ValueError(f"null {k} for hotel {payload['hotel']} {c['complaint_id']}")
        for r in c["solutions"]:
            if len(r) != len(ROW_COLUMNS) or any(v is None for v in r):
                raise ValueError(f"bad row for hotel {payload['hotel']} {c['complaint_id']}: {r}")


def write_all(index, hotel_payloads):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HOTELS_DIR.mkdir(parents=True, exist_ok=True)
    for old in OLD_OUTPUTS:
        old.unlink(missing_ok=True)
    for f in HOTELS_DIR.glob("*.js"):
        f.unlink()
    (OUT_DIR / "hotel_index.js").write_text(f"window.HOTEL_INDEX = {_dump(index)};\n", encoding="utf-8")
    sizes = {}
    for hp in hotel_payloads:
        _assert_clean(hp)
        text = f"window.HOTEL_PROFIT_LOAD({json.dumps(hp['hotel'])}, {_dump(hp)});\n"
        path = HOTELS_DIR / f"{hp['hotel']}.js"
        path.write_text(text, encoding="utf-8")
        sizes[hp["hotel"]] = len(text.encode("utf-8"))
    return sizes


def sanity_17145(price_model, params):
    if 17145 not in params.index:
        return None
    v = price_model.value_of_gain(np.array([0.01]), params.loc[[17145]], "base")
    return float(v["profit_gain"].iloc[0]), float(v["total_revenue_gain"].iloc[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=Path(os.environ.get("HILTON_SOURCE_REPO", DEFAULT_SOURCE)))
    ap.add_argument("--raw", type=Path, default=Path(os.environ.get("HILTON_RAW_CSV", DEFAULT_RAW)),
                    help="raw dashboard export (only read to build data/family_shares.csv)")
    ap.add_argument("--rebuild-family-shares", action="store_true")
    args = ap.parse_args()
    source = args.source.resolve()

    complaints = pd.read_csv(COMPLAINTS, keep_default_na=False)
    price_model, scores, sol, params, tiers, locations, info = build(
        source, args.raw, args.rebuild_family_shares, set(complaints["topic"]))
    complaints = load_complaints(scores["topic"].unique())
    index = index_payload(params, tiers, locations, complaints, source, info["labor"])
    scores_by_h = {h: g.set_index("topic") for h, g in scores.groupby("hotel")}
    sol_by_h = dict(tuple(sol.groupby("hotel")))
    empty_scores = scores.iloc[0:0].set_index("topic")
    payloads = [hotel_payload(h, scores_by_h.get(h, empty_scores), sol_by_h.get(h, sol.iloc[0:0]), complaints)
                for h in sorted(params.index)]
    sizes = write_all(index, payloads)

    # ---- report ----
    check = sanity_17145(price_model, params)
    print(f"Source: {source} @ {index['meta']['source_repo_commit']}")
    print("Labor wages (data/labor_rates.csv): "
          + ", ".join(f"{d} ${w:.2f}" for d, w in index["meta"]["labor_rates"].items()))
    if check:
        print(f"Sanity 17145, +0.01 rating: profit ${check[0]:,.0f}, total revenue ${check[1]:,.0f} "
              f"(guide: $38,888 / $54,006)")
    text = complaints.set_index("complaint_id")["complaint"]
    ix = {c: i for i, c in enumerate(ROW_COLUMNS)}
    hp = next((p for p in payloads if p["hotel"] == "17145"), None)
    if hp:
        print(f"\nHotel 17145, all {len(hp['complaints'])} complaints by best Stay Score per $1k:")
        for c in hp["complaints"]:
            r = c["solutions"][0] if c["solutions"] else None
            if r is None:
                print(f"  {text[c['complaint_id']][:45]:<45} (no data)")
                continue
            print(f"  {text[c['complaint_id']][:45]:<45} | {r[ix['solution']][:38]:<38} | {r[ix['for']]:<12} "
                  f"cost ${r[ix['annual_cost']]:>9,} ss_gain {r[ix['stay_score_gain']]:.5f} "
                  f"per1k {r[ix['stay_score_per_1k']]:.5f} profit ${r[ix['profit_gain']]:>9,} "
                  f"net ${r[ix['net_profit']]:>10,} roi {r[ix['roi']]:.4f}")
        print(f"  has_data false: {sum(not c['has_data'] for c in hp['complaints'])} of {len(hp['complaints'])}")

    n_data = [sum(c["has_data"] for c in p["complaints"]) for p in payloads]
    written = sum(len(c["solutions"]) for p in payloads for c in p["complaints"])
    print(f"\nNetwork: {len(payloads)} hotel files, {written:,} rows written ({len(sol):,} unique per case type) "
          f"(of {info['rows_before_filter']:,} costed before gain>0 & cost>0; "
          f"{info['targeted_unplaced']} targeted rows had no audience; "
          f"{info['no_cases']} rows dropped for 0 cases fixed a year)")
    fi = ROW_COLUMNS.index("for")
    per = {a: sum(r[fi] == a for p in payloads for c in p["complaints"] for r in c["solutions"]) for a in AUDIENCES}
    print("Rows written per audience: " + ", ".join(f"{a} {n:,}" for a, n in per.items()))
    print(f"has_data complaints per hotel: median {float(np.median(n_data)):.1f}, "
          f"min {min(n_data)}, max {max(n_data)}")
    print(f"net_profit > 0: {(sol['net_profit'] > 0).mean():.1%} of rows")
    mx = max(sizes, key=sizes.get)
    print(f"Hotel files: max {sizes[mx] / 1e6:.2f} MB ({mx}), total {sum(sizes.values()) / 1e6:.1f} MB | "
          f"index {(OUT_DIR / 'hotel_index.js').stat().st_size / 1e3:.1f} kB")
    print(f"Wrote {OUT_DIR / 'hotel_index.js'} and {HOTELS_DIR}/<hotel>.js")


if __name__ == "__main__":
    main()
