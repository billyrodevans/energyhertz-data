# energyhertz-data

Open-source data pipelines behind the dashboards on [energyhertz.com](https://energyhertz.com).
Each pipeline pulls public energy data, checks it, and publishes small JSON files that the site reads.

## CAISO nodal prices (`caiso_lmp/`)

Feeds the CAISO LMP map on the *Energy Pricing Fundamentals* project page.

| | |
|---|---|
| **Prices** | California ISO OASIS, Fifteen-Minute Market (FMM / RTPD) locational marginal prices, all nodes (`GroupZip`, group `RTPD_LMP_GRP`) |
| **Components** | LMP = energy (MCE) + congestion (MCC) + loss (MCL) + greenhouse gas (MGHG), in $/MWh |
| **Node locations** | California ISO price map ([caiso.com/todays-outlook/prices](https://www.caiso.com/todays-outlook/prices)). Approximate, substation-level positions |
| **Coverage** | CAISO balancing area plus Western Energy Imbalance Market (WEIM) areas |
| **Schedule** | Hourly at :28 UTC, plus a backup at :48 that only contacts CAISO if the :28 run was skipped or incomplete. One OASIS request per run, plus one retry of the previous hour only if intervals are missing. Node locations refreshed at most daily |
| **Window kept** | Latest 24 hours (96 fifteen-minute intervals) plus up to 4 intervals CAISO publishes ahead (100 files). Older files are deleted |

### Data integrity rules

Values are published exactly as CAISO publishes them: no rounding, filling or smoothing. Every run checks:

- All five price files are present, from the RTPD market, with no duplicate rows
- Every node has all five components, and LMP = energy + congestion + loss + GHG, allowing only for rounding in CAISO's published numbers (about 7 significant digits: ~$0.00001 at $50, ~$0.00013 at $2,000). Verified on 301,744 node-intervals
- Intervals are 15 minutes long and fall inside the requested hour
- LMPs outside −$5,000 to $5,000/MWh are flagged for review. These are sanity bounds for corrupted data, not market limits: real LMPs can pass CAISO's −$150 bid floor. Flagged values are still published as-is, listed in each interval file's `outliers` field, and marked on the map with a caution triangle
- Node coordinates are inside the Western US, and over 95% of mapped nodes match an OASIS price node by exact ID

**Errors** block publishing: the site keeps the last good data. **Warnings** publish but alert. Either one opens or updates a GitHub issue titled "Data alert: CAISO LMP". A missing interval is retried once; if it is still missing, it shows as "no data" and is never filled in.

### Output files (`caiso-lmp/` in the R2 bucket)

| File | Contents |
|---|---|
| `index.json` | Available intervals, last run status, source and attribution |
| `nodes.json` | `{node_id: {lat, lon, area, type}}` |
| `dlap-dam.json` | Day-ahead hourly prices (LMP + components) at the four Default Load Aggregation Points: PG&E, SCE, SDG&E, VEA, the price load in each utility area pays. Yesterday, today and tomorrow (Pacific operating days). One OASIS request when a day is missing, normally once a day after ~1:30 PM PT |
| `day.json` | Whole window in one file for the map slider: each mapped node's LMP rounded to the cent (colors only) plus one fixed color scale (2nd–98th percentile of the window), and each DLAP's exact 15-minute LMP. Exact values stay in `intervals/` |
| `intervals/YYYYMMDDTHHMMZ.json` | Interval start/end (UTC), CAISO file names, OASIS request URL, retrieval time, warnings, `outliers` (node IDs outside the sanity bounds), and `prices: {node_id: [lmp, energy, congestion, loss, ghg]}` |

## US ISO comparison (`us_iso/`)

Feeds the US map on the *Energy Pricing Fundamentals* project page: customers, average retail price and generation mix for the seven ISOs/RTOs, plus utility lists. Built once a year (`python -m us_iso.build --r2 --year 2025`); a monthly check (`python -m us_iso.validate --r2`, 12th of each month) tests the estimates against fresh data and reports to a GitHub issue.

| Output (`us-iso/`) | Contents | Source |
|---|---|---|
| `regions.json` | Per ISO: customer accounts, retail MWh, average retail price (all sectors), generation mix, renewable share; CAISO also with estimated imports | EIA Form 861; EIA Form 923; EIA-930 (flows) |
| `utilities.json` | Per ISO: every utility / retail provider: customers, bundled-service price, share of customers buying from another supplier | EIA Form 861 |
| `residual.json` | Estimated mix of California's "unspecified" market power | CEC Power Content Labels + EIA-923 + EIA-930 |
| `boundaries.geojson` | ISO boundaries, simplified | HIFLD (approximate, as of 2020) |

### Methods

- **Customers and prices (EIA-861 Schedule 4).** Part A = bundled, B = energy-only (e.g. CCAs), C = delivery-only, D = Texas retail providers. Each customer appears once in A, C or D (B duplicates C), so customers and MWh = A + C + D and revenue = A + B + C + D. Withheld cells (".") are missing, never zero. Utilities are assigned to ISOs by the balancing-authority code on each row.
- **Generation mix (EIA-923, plant level, final).** Annual net generation of every power plant located in each ISO's balancing authority, by fuel: the same definition for all seven regions. Utility-scale and industrial plants only (rooftop solar excluded). Storage is net and kept out of the pie. *Generation from plants within the ISO's territory: the power a utility or customer actually buys can differ because of purchase agreements and imports.*
- **Why not EIA-930 or CAISO's own data for the mix (checked 2026-11-12):** EIA-930's hourly fuel labels for CAISO overstate gas by ~20 TWh in 2025 versus EIA-923, and EIA-930 reports biomass/waste as "other" in NYISO and ISO-NE. CAISO's own fuel data agrees with EIA-923 within a few points (it counts some out-of-state plants it dispatches and excludes industrial on-site use) and is kept as a cross-check.
- **CAISO imports (estimated).** Flow tracing: every hour, power in each Western US balancing authority is its own generation plus inflows from neighbors, mixed proportionally, solved as one linear system (EIA-930 generation and interchange), so imports are traced back through intermediate grids to the generating source. Each grid's EIA-930 "other/unknown" generation is split into the sources EIA-923 shows it has but EIA-930 omits (e.g. NV Energy geothermal); all other EIA-930 fuels are used as reported. Flows from outside the traced area (e.g. Canada, Mexico) are "unattributed"; hours with no flow data are skipped.
- **Residual mix (estimated).** California supply by fuel (EIA-923 plants in CAISO, BANC, LADWP, TIDC, IID + traced imports into California) minus all specified power claimed on the CEC Power Content Labels; the remainder approximates what untraceable "unspecified" market power is made of. Annual, statewide approximation; small and large hydro combined; negative remainders set to zero and reported (wind: contracted out-of-state wind exceeds what is physically traced into California).
- **Checks.** Missing hours/days, layout changes, unattributed imports above 2%, "other/unknown" above 5% of a mix, CAISO vs EIA-930 import totals differing by more than 25%. Every warning is posted to the "US ISO estimates: checks" issue.

## Run it yourself

Requires Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m pytest -q             # tests
python -m caiso_lmp.run --out output   # one refresh, written to ./output
```

Uploading to R2 (`--r2`) needs these environment variables: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`. In GitHub Actions they are repository secrets.

## Data sources and terms

Data: **California ISO**; **U.S. Energy Information Administration** (EIA-861, EIA-930; public domain); **California Energy Commission** (Power Content Labels); ISO boundaries from **HIFLD** (public use). Used under the [CAISO Terms of Use](https://www.caiso.com/privacy-terms-of-use), which allow use of public materials with credit to the California ISO. CAISO provides the data "as is". For official values, see [OASIS](https://oasis.caiso.com/). This project is not affiliated with or endorsed by the California ISO.

The code in this repository is MIT licensed (see `LICENSE`). The data belongs to its sources and stays under their terms.

Content is educational and is not engineering, financial or trading advice.
