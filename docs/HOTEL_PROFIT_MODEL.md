# Hotel profit model (dashboard export)

`src/hotel_profit_export.py` precomputes, for every hotel, a fixed list of guest complaints
(`data/guest_complaints.csv`) ranked by **Stay Score gained per $1,000 of annual cost** of the best
solution, using that hotel's **own** Model B regression. For each complaint the dashboard shows the
candidate solutions, each once for the audience it targets, with their Stay Score gain, cost, expected owner profit and ROI.

## Rerun

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/python -m src.hotel_profit_export [--source /path/to/HiltonHackathon] \
    [--raw /path/to/dashboard-export.csv] [--rebuild-family-shares]
```

The source repo defaults to `$HILTON_SOURCE_REPO`, else `../../HiltonHackathon` from this repo's
root. Its `src` package is loaded under the alias `hilton_src` and reused unchanged
(`solutions.solution_costs`, `catalog_for`, `price_model.hotel_parameters`, `value_of_gain`,
`price_actions`), except that labor is priced at BLS wages (see Pricing). The raw export (`--raw`, default `$HILTON_RAW_CSV`, else
`/Users/justin/Hilton/Data/dashboard-export-06-01-pm-2026-10-23.csv`) is read only to build
`data/family_shares.csv`, which is cached and rebuilt only with `--rebuild-family-shares` or
when missing. The script prints a sanity check: hotel 17145 at +0.01 rating should give about
$38,888 profit and $54,006 total revenue.

## Inputs

| Input | From |
|---|---|
| Complaint list (guest wording, case type, owner, priority, urgent) | `data/guest_complaints.csv` |
| Hotel × topic Model B counts and gains (`prevent_gain`, `resolve_gain`) | source `results/model_b_hotel_scores.csv` |
| Solutions, costs, segment shares | source `data/solutions.csv`, `data/segment_shares.csv`, USALI P&Ls (occupancy, ADR), location indices |
| Extra solutions (appended to the source catalog) | `data/solutions_extra.csv` (same columns as the source `data/solutions.csv`) |
| Labor wage per `labor_dept` | `data/labor_rates.csv` (BLS 2025 accommodation-industry mean hourly wages) |
| Family shares | `data/family_shares.csv` (built from the raw export, git-ignored) |
| Hotel profile, price parameters | source `results/hotel_tiers.csv`, `data/hotel_stay_scores.csv`, price assumption files |

`data/macro_effects_us.csv` (US macro coefficients) and `data/issue_taxonomy.csv` are no longer
read: the earlier macro-coefficient × incidence gain was replaced by the per-hotel Model B gain.

## Complaint list

`data/guest_complaints.csv` has one row per complaint the dashboard offers, in guest language:
`complaint_id` (unique), `complaint`, `also_heard_as` (alternatives, `|`-separated), `topic`
(the Model B topic = **case type**), `macro_category`, `owner_department`, `priority_mode`
(`emergency_override` → `safety`), `urgent` (`yes`/`no`). Several complaints may share a case
type (e.g. "My bathroom is broken" and "The toilet won't flush" are both `BathroomCondition`);
they then carry identical numbers. Solutions are costed only for the case types in this file.
Editing the file and rerunning changes the list; the export warns when a topic has no Model B rows.

Per hotel × complaint (joined on hotel × topic; a hotel with no Model B row for the topic gets zeros):

```
complaints, reviews_in_window      from Model B
incidence           = complaints / reviews_in_window
full_fix_stay_score = prevent_gain(hotel, topic) × 30.2   (value of removing the problem entirely)
best_stay_score_per_1k = stay_score_per_1k of the first (best) solution, 0 if none
has_data            = complaints > 0 and at least one solution row
```

## Audiences

| Audience | Who | Share used |
|---|---|---|
| Leisure | Purpose of Stay = Leisure | source `segment_shares.csv`, dim `purpose`, segment `Leisure` |
| Business | Purpose of Stay = Business | source `segment_shares.csv`, dim `purpose`, segment `Business` |
| Families | Purpose of Stay Details = Family | `data/family_shares.csv` (dim `purpose`, segment `Family`) |
| Elite status | Honors Tier ∈ {Gold, Diamond, Diamond Reserve} | source `segment_shares.csv`, dim `tier`, segment `Gold & Diamond` |
| All guests | everyone | 1.0 |

As in the source, a topic missing from the share table uses the hotel's `_stays` share, and a
hotel with no share at all gets 0 (its rows then have zero gain and are dropped).

### Family-share build

Mirrors the source's `solutions.build_segment_shares` exactly, with Family vs. the other known
`Purpose of Stay Details` values (Individual, Couple, Group, Friends) as the segment:

- A review's negative topics are the labels matched by the source's `NEG` regex
  (`<topic>: Negative` / `Very Negative`) in the Topic Sentiment Label column; one row per
  review × negative topic. Like the source, no date window is applied (all reviews in the export).
- `_stays` is a pseudo-topic over all reviews (the segment's share of guests).
- Only reviews with a known `Purpose of Stay Details` count (blank ≈ 60%).
- `share = (complaints_from_family + 20 × network_share) ÷ (complaints_with_known_details + 20)`,
  where `network_share` is the topic's Family share across all hotels.

## Solutions per audience

For each hotel × topic the candidates are the source's `catalog_for(topic)` list (topic → Level 1
→ `*`). The source's `solution_costs` is run once on the catalog, with **one audience per catalog
solution**: each solution appears once per hotel × complaint, with a single `for`. Unit cost, uses,
segment shares and gain all come from the source's code (guide §7.2–7.4).

### Extra catalog rows (`data/solutions_extra.csv`)

The export appends `data/solutions_extra.csv` (same columns as the source `data/solutions.csv`;
the source repo is not modified) to the source catalog before anything else, and patches the
source's `load_catalog` so `solution_costs` and `catalog_for` both see the combined catalog. Because
`catalog_for` returns *every* row of a topic that has rows, an appended row simply adds one more
option to that topic. A row that repeats an existing (topic, solution, purpose, tier) stops the
export. Extra rows get audiences by the same rules as source rows (purpose All, tier All →
`All guests`). `results/department_solution_catalog.csv/.json` include them as well.

Current rows: **"Engineer repair within the hour"** for BathroomCondition ("My bathroom is broken",
"The toilet won't flush"), BathroomFeatures and Room-Condition — basis `complaint`, all guests,
Repairs & Maintenance 1.0 h, $15 parts, no room nights, effect 0.6. Why: the source catalog had no
on-complaint *repair* for bathroom condition or features; the only per-complaint option was "Room
move on complaint", about $85 a use at a US hotel, mostly displacement (1 room night × ADR × 0.25)
rather than labor. The repair costs 1.0 × $21.70 + $15 ≈ **$36.70** per complaint at US wages
(scaled by the country labor/price indices elsewhere). Effect 0.6 (share of the complaint's rating
loss recovered) is an editable assumption, not an estimate, set equal to Room-Condition's existing
"Fix or move on complaint". At hotel 17145 the repair becomes the best "My bathroom is broken"
solution (Stay Score per $1k 0.00188 → 0.00344); the complaint stays 9th of 10 there, just behind
"My room was too noisy to sleep" (0.00349), but rises in the ranking at 55 of 185 hotels.

| Catalog row | `for` | `source` |
|---|---|---|
| Name or description mentions famil(y/ies) (any purpose/tier) | Families only | `Targeted` |
| purpose Business | Business | `Targeted` |
| purpose Leisure (not family) | Leisure | `Targeted` |
| tier Gold & Diamond | Elite status | `Targeted` |
| All guests (purpose All, tier All) | All guests, priced as the source does | `All guests` |

All-guest solutions are no longer copied into per-audience versions. Family solutions (in the
source catalog they are purpose Leisure) are re-targeted to the Family purpose segment, so they
are priced with the Families shares from `data/family_shares.csv` instead of the Leisure shares:

| Basis | Uses (family rows) | Gain uses |
|---|---|---|
| `guest` | `annual_stays × seg_stays(Families) × uptake` | `seg_complaints(Families)` |
| `room_year` | `rooms × seg_stays(Families)` | `seg_complaints(Families)` |
| `complaint` | `unresolved_reported × per_review × seg_complaints(Families)` | `seg_complaints(Families)` |

The `room_year` rule is the only departure from the source formula (which uses all `rooms`): a
family program is sized to the Families share of stays. With the current catalog and complaint
list, the only family solution in scope is "Priority room-ready for families" (Arrival-CheckIn,
"Check-in took forever"), and no Leisure (non-family) solution falls in these case types, so the
Leisure audience has no rows (the page hides empty audiences).

### Pricing (unit cost and annual cost)

```
unit_cost   = labor_hours × w_dept × labor_index          (w_dept = BLS hourly wage, data/labor_rates.csv)
            + item_cost_usd × price_index
            + room_nights × ADR × price_index × 0.25       (displacement)
annual_cost = unit_cost × uses
```

This is the cost doc's `C = h × w_dept + c_item + n_room × ADR × d` (METHODOLOGY.md, "Costs and
solution layer") with `w_dept` set to the **BLS 2025 accommodation-industry (NAICS 721) mean hourly
wage** of the occupation that does the work, wages only (no benefits or payroll-tax loading):

| `labor_dept` | Occupation (SOC) | Wage $/h | Source |
|---|---|---|---|
| Rooms | Maids and housekeeping cleaners (37-2012); desk clerks 43-4081 are close at $17.01 | 17.62 | <https://www.bls.gov/iag/tgs/iag721.htm> |
| Food & Beverage | Waiters and waitresses (35-3031), the largest F&B occupation in NAICS 721 (cooks, restaurant $21.51; F&B major group $21.36) | 21.49 | <https://www.bls.gov/iag/tgs/iag721.htm> |
| Repairs & Maintenance | Maintenance and repair workers, general (49-9071) | 21.70 | BLS OEWS May 2025 national industry-specific estimates, NAICS 721000 (<https://www.bls.gov/oes/2025/may/oessrci.htm>, `oesm25in4.zip` → `nat3d_M2025_dl.xlsx`) |
| Administrative & General | Lodging managers (11-9081) | 37.08 | <https://www.bls.gov/iag/tgs/iag721.htm> |

**What changed and why.** The source's `solution_costs` priced labor at *loaded* hourly rates
derived from the managed P&L (Rooms $31.00, F&B $39.38, R&M $44.12, A&G $60.01). The export now follows the cost doc, whose cited wage benchmark is BLS:
it replaces every benchmark's (Managed and Franchised) `hourly_rates` with the wages above, in
memory, before calling the source's `solution_costs`. Nothing else in the source logic changes:
program sizing (`uses`), item costs, displacement (0.25 × ADR), the country `labor_index` (still
scales the wage for non-US hotels) and `price_index`, Model B gains and the profit model are as
before. The labor part of unit cost falls 38–51% (A&G 38%, Rooms 43%, F&B 45%, R&M 51%; e.g.
hotel 17145 "Peak-hour staffing" $110,372 → $62,725 a year), so Stay Score per $1k and ROI rise
for labor-heavy solutions; item-cost solutions barely move. Every `labor_dept` in the catalog must have a row in `data/labor_rates.csv` or the export stops.

### Gain (hotel-specific Model B, guide §7.4)

The source's `solution_costs` is fed the hotel's own Model B `prevent_gain` / `resolve_gain`
(rating points from removing all of that hotel's complaints on the topic / resolving all its
unresolved reported ones):

```
Prevent (per guest, per room per year):  gain = prevent_gain(hotel, topic) × effect × seg_complaints(audience)
Resolve (per complaint):                  gain = resolve_gain(hotel, topic) × effect × seg_complaints(audience)
```

Rows with gain ≤ 0 or annual_cost ≤ 0 are dropped (a topic whose Model B weight is not negative
has a zero gain of that kind, so it may have only Prevent or only Resolve rows, or none).

### Ranking metric and money (guide §8–9, base / low / high elasticity)

```
stay_score_gain      = gain × stay_score_per_rating_point (30.2)
stay_score_per_1k    = stay_score_gain ÷ annual_cost × 1000          ← ranking metric
predicted_stay_score = hotel stay_score + stay_score_gain
revenue_gain         = value_of_gain(...).total_revenue_gain
profit_gain          = value_of_gain(...).profit_gain   (expected owner profit, before cost)
profit_low / high    = profit_gain at the low / high elasticity
net_profit           = profit_gain − annual_cost;  roi = net_profit ÷ annual_cost
```

Within a complaint, solutions (all audiences together) are sorted by `stay_score_per_1k`
descending (ties: `profit_gain`). Complaints are sorted by `best_stay_score_per_1k` descending;
the page itself pins urgent / safety complaints ahead of the cost ranking. Solutions for one
complaint overlap: their gains must not be added.

## Per-case metrics

What one fixed complaint costs and what it buys, per solution row (asked as "per resolution cost,
satisfaction score increase from that singular case"). `cases_per_year` is the source's
`fixed_per_year` from `solution_costs` (guide §7.4):

```
complaint basis (Resolve):          cases_per_year = uses × effect
                                                   = unresolved_reported × per_review × seg_complaints × effect
guest / room_year basis (Prevent):  cases_per_year = complaints × per_review × seg_complaints × effect
                                    (per_review = annual_stays ÷ reviews_in_window)
cost_per_case       = annual_cost ÷ cases_per_year     (complaint basis: ≈ unit_cost ÷ effect, the
                                                         cost per case actually fixed; unit_cost is kept as is)
stay_score_per_case = stay_score_gain ÷ cases_per_year (hotel Stay Score points one fixed case adds)
profit_per_case     = profit_gain ÷ cases_per_year
net_per_case        = profit_per_case − cost_per_case
guest_rating_lift   = max(0, weight(hotel, topic)) × effect     (1–5 rating points, the ONE guest)
                      weight = resolve_weight for Resolve rows, prevent_weight for Prevent rows
                      (source results/model_b_hotel_scores.csv: rating points per affected review)
```

Family `room_year` rows keep the source `fixed_per_year` (it depends on complaints, not on the
program size), so only their cost per case reflects the Families-sized program. Rows with
`cases_per_year ≤ 0` are **dropped** (none with the current data: gain > 0 already implies at
least one case a year), so the per-case fields never divide by zero. Rounding: per-case dollars
2 decimals, `stay_score_per_case` 6, `guest_rating_lift` 3, `cases_per_year` 2. Because
`annual_cost` is written in whole dollars, `cost_per_case × cases_per_year` reproduces it to within
rounding (exact before rounding; 21 of 5,781 rows are off by more than 1%, all with annual cost
of $45 or less).

Each complaint entry also carries `unresolved_reported` (reported, unresolved cases in the
hotel's last-365-day review window) and this hotel's `resolve_weight` / `prevent_weight` for the
case type (4 decimals). The page shows, for the best solution, "$X per case · +Y Stay Score · guest
+Z rating" in the complaint list; Cost / case (cases / yr beneath), Stay Score / case, Guest rating
lift and Net / case (green/red) in the solution table (Basis and Predicted Stay Score moved into
each row's detail expansion); and in the expanded panel "Resolving one reported case here lifts
that guest's rating by ~+R (this hotel's resolution weight W × the best Resolve solution's
effect) — N reported cases are still unresolved each year in reviews".

Hotel 17145 examples: "My bathroom is broken", Engineer repair within the hour: 122.39 cases/yr,
$61.17 per case (unit $36.70 ÷ 0.6), +0.00021 Stay Score per case, guest +0.227 rating,
profit $27.06 per case, net −$34.11. "I was overcharged on my bill", Correction and apology:
91.79 cases/yr, $17.48 per case, guest +0.428, net +$26.17.

## Output layout

`dashboard/data/hotel_index.js` sets `window.HOTEL_INDEX = {meta, hotels}`:

- `meta`: `generated`, `source_repo_commit`, `stay_score_per_rating_point` (30.2), `audiences`
  (`Leisure, Business, Families, Elite status, All guests`), `row_columns`, `complaints`
  (`[{complaint_id, complaint, also_heard_as, topic, macro_category, owner_department, safety,
  urgent, case_type}]`, CSV order; `case_type` = `topic`), `disclosures`, `pricing_model` (the
  unit/annual cost formula as text), `labor_rates` (`{labor_dept: wage}` from `data/labor_rates.csv`),
  `labor_rate_occupations` and `labor_rate_sources` (`{labor_dept: BLS occupation / source URL}`).
- `hotels`: `[{hotel, brand, hotel_class, region, country, ownership, rooms, avg_rating, stay_score}]`,
  sorted by hotel id.

`dashboard/data/hotels/<hotel>.js` (one per hotel) contains exactly one call
`window.HOTEL_PROFIT_LOAD("<hotel>", {hotel, complaints})`, with one entry per CSV complaint:

```
complaints: [{complaint_id, has_data, complaints, reviews_in_window, incidence,
              full_fix_stay_score, best_stay_score_per_1k, unresolved_reported,
              resolve_weight, prevent_weight, solutions: [row, ...]}]
row = [type, solution, description, for, source, basis, unit_cost, uses, annual_cost, gain,
       stay_score_gain, stay_score_per_1k, predicted_stay_score, revenue_gain, profit_gain,
       profit_low, profit_high, net_profit, roi, cases_per_year, cost_per_case,
       stay_score_per_case, profit_per_case, net_per_case, guest_rating_lift]
```

`for` is the single audience; `source` is `Targeted` (audience-specific) or `All guests`; `type`
is Prevent / Resolve; `basis` is per guest / per complaint / per room per year. Rounding: dollars
whole (per-case dollars 2 decimals, see Per-case metrics); gain, Stay Score values and `stay_score_per_1k` 5 decimals (so a few very small values
show as 0); incidence / uses / roi 4 decimals. Rows contain no null, NaN or Infinity. Stale hotel
files are removed on every run.

## Caveats

- Model B gains are per-hotel regressions; small hotels or rare topics give noisy or zero gains.
- Gains are historical associations between complaints and ratings, not causal effects.
- Solution costs and effects are editable operating assumptions, not estimates.
- Purpose, Purpose of Stay Details and tier are treated as independent, as in the source.
- The outputs and `data/family_shares.csv` contain internal hotel IDs from confidential data and
  are git-ignored.
