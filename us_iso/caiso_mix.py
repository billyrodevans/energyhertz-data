"""CAISO's own annual fuel mix from its Today's Outlook history (5-minute MW, one file per day).

Columns: Time, Solar, Wind, Geothermal, Biomass, Biogas, Small hydro, Coal, Nuclear, Natural Gas,
Large Hydro, Batteries, Imports, Other. Energy (MWh) = MW x 5/60 per interval.
Checks per day: all columns present, 288 intervals (276 / 300 on daylight-saving days), numbers only.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

COLUMNS = ["Solar", "Wind", "Geothermal", "Biomass", "Biogas", "Small hydro", "Coal", "Nuclear",
           "Natural Gas", "Large Hydro", "Batteries", "Imports", "Other"]
KEY = {
    "Solar": "solar", "Wind": "wind", "Geothermal": "geothermal", "Biomass": "biomass", "Biogas": "biogas",
    "Small hydro": "small_hydro", "Coal": "coal", "Nuclear": "nuclear", "Natural Gas": "gas",
    "Large Hydro": "large_hydro", "Batteries": "batteries", "Imports": "imports", "Other": "other",
}
VALID_ROWS = {276, 288, 300}


def annual(paths: list[Path]) -> tuple[dict, list[str]]:
    """Sum of MWh by source over all days, and problems found (each problem = an alert)."""
    total = defaultdict(float)
    problems = []
    for p in paths:
        with open(p, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        missing = [c for c in COLUMNS if not rows or c not in rows[0]]
        if missing:
            problems.append(f"{p.name}: missing columns {missing}")
            continue
        if len(rows) not in VALID_ROWS:
            problems.append(f"{p.name}: {len(rows)} five-minute rows (expected 288, or 276/300 on daylight-saving days)")
        for r in rows:
            for c in COLUMNS:
                v = (r[c] or "").strip()
                if v == "":
                    continue
                try:
                    total[KEY[c]] += float(v) * 5 / 60
                except ValueError:
                    problems.append(f"{p.name}: non-numeric {c} value {v!r}")
                    break
    return dict(total), problems
