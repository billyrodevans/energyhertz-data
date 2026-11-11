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
| `day.json` | Whole window in one file for the map slider: each mapped node's LMP rounded to the cent (colors only) plus one fixed color scale (2nd–98th percentile of the window). Exact values stay in `intervals/` |
| `intervals/YYYYMMDDTHHMMZ.json` | Interval start/end (UTC), CAISO file names, OASIS request URL, retrieval time, warnings, `outliers` (node IDs outside the sanity bounds), and `prices: {node_id: [lmp, energy, congestion, loss, ghg]}` |

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

Data: **California ISO**. Used under the [CAISO Terms of Use](https://www.caiso.com/privacy-terms-of-use), which allow use of public materials with credit to the California ISO. CAISO provides the data "as is". For official values, see [OASIS](https://oasis.caiso.com/). This project is not affiliated with or endorsed by the California ISO.

The code in this repository is MIT licensed (see `LICENSE`). The data belongs to its sources and stays under their terms.

Content is educational and is not engineering, financial or trading advice.
