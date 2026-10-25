# Cost and Solution Assumptions

The solution layer is a transparent planning aid. It separates accounting/wage benchmarks from property-editable operating assumptions.

## Benchmark basis

- The bundled managed and franchised P&L workbooks provide baseline department expense and occupied-room-night benchmarks.
- USALI is an industry lodging-accounting standard maintained through AHLA/HFTP governance; AHLA describes the 12th revised edition at <https://www.ahla.com/news/hftp-ahla-and-gfc-unveil-groundbreaking-12th-revised-edition-uniform-system-accounts-lodging>.
- BLS publishes 2025 accommodation-industry mean hourly wages, including housekeeping ($17.62), desk clerks ($17.01), and lodging managers ($37.08): <https://www.bls.gov/iag/tgs/iag721.htm>.

These sources support the cost structure and wage order of magnitude. They do not provide a property-specific price for a recovery action.

## Editable assumptions

| `solutions.csv` field | Meaning |
|---|---|
| `labor_hours` | Incremental time required for an action. |
| `item_cost_usd` | Goods, voucher, points, fee-waiver, contractor, or goodwill cash cost. |
| `room_nights` | Inventory tied up by a room move. |
| `uptake` | Share of eligible guests receiving a preventive action. |
| `effect` | Plausible share of macro recovery potential addressed by an action. |

No value above is a treatment effect identified from the review data. Owners/managers must be able to edit them. Baseline salaries, rent, and routine overhead are not charged again as recovery cost; only incremental cost belongs in the comparison.

Safety, legal, accessibility, discrimination, and serious hygiene items require escalation regardless of cost-to-rating ratio. Location and pricing complaints may require communication or revenue-management review rather than a claim that the property can physically eliminate the root cause.
