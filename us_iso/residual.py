"""Residual mix: an estimate of what California's "unspecified" (market) power is made of.

Method (annual, statewide approximation):
  1. California supply by fuel = generation of power plants in California's balancing
     authorities (EIA-923, plant level) + imports into California from outside, traced to
     their sources (EIA-930 flow tracing).
  2. Claimed specified power = sum over every retail supplier on the CEC Power Content Label
     table of retail MWh x its share of each specified source.
  3. Residual = supply - claimed, per fuel (negative results set to 0 and reported).
The residual's shares are then applied to each utility's "unspecified" percentage.

Hydro: EIA-930 and imports don't split small/large hydro, so the residual uses one "hydro".
"""

from __future__ import annotations

import io

import openpyxl

CA_BAS = {"CISO", "BANC", "LDWP", "TIDC", "IID"}

# CEC label columns (index in the 2024 sortable table) -> residual categories.
PCL_COLS = {
    5: "biomass", 6: "geothermal", 7: "hydro", 8: "solar", 9: "wind",
    10: "hydro", 11: "nuclear", 12: "other", 13: "other", 14: "gas", 15: "coal",
}
UNSPECIFIED_COL, SALES_COL = 16, 2
CATEGORIES = ["solar", "wind", "geothermal", "biomass", "hydro", "nuclear", "gas", "coal", "other"]


def claimed_specified(pcl_path) -> tuple[dict, float, float, list[str]]:
    """MWh claimed as specified power by fuel, total retail MWh, unspecified MWh, and notes."""
    wb = openpyxl.load_workbook(pcl_path, read_only=True, data_only=True)
    rows = list(wb[wb.sheetnames[0]].iter_rows(values_only=True))
    head = [str(c or "").replace("\n", " ") for c in rows[0]]
    assert "Unspecified" in head[UNSPECIFIED_COL] and "Retail Sales" in head[SALES_COL], "CEC table layout changed"
    claimed = {c: 0.0 for c in CATEGORIES}
    total = unspec = 0.0
    notes = []
    for r in rows[1:]:
        if not r or r[0] in (None, "N/A") or not isinstance(r[SALES_COL], (int, float)):
            continue  # skip the state average row, blank rows and the "current as of" footer
        mwh = r[SALES_COL]
        total += mwh
        for i, cat in PCL_COLS.items():
            v = r[i] if isinstance(r[i], (int, float)) else 0
            claimed[cat] += mwh * v
        u = r[UNSPECIFIED_COL] if isinstance(r[UNSPECIFIED_COL], (int, float)) else 0
        unspec += mwh * u
    notes.append(f"{len([1 for r in rows[1:] if r and isinstance(r[SALES_COL], (int, float)) and r[0] not in (None, 'N/A')])} retail products, {total/1e6:.1f} TWh retail sales")
    return claimed, total, unspec, notes


def supply_from_plants(eia923_by_ba: dict, imports: dict) -> dict:
    """California supply by category: EIA-923 generation of plants in California's balancing
    authorities + imports into California traced to their sources (EIA-930)."""
    s = {c: 0.0 for c in CATEGORIES}
    remap = {"oil": "other", "waste": "other", "unknown": "other"}
    for ba in CA_BAS:
        for f, v in eia923_by_ba.get(ba, {}).items():
            if f == "storage" or v <= 0:
                continue
            s[remap.get(f, f)] += v
    for f, v in imports.items():
        if v <= 0 or f in ("unattributed", "storage"):
            continue
        s[remap.get(f, f)] += v
    return s


def residual_mix(supply: dict, claimed: dict) -> tuple[dict, list[str]]:
    notes = []
    res = {}
    for c in CATEGORIES:
        r = supply.get(c, 0) - claimed.get(c, 0)
        if r < 0:
            notes.append(f"{c}: claims exceed supply by {-r/1e6:.2f} TWh (set to 0)")
            r = 0.0
        res[c] = r
    tot = sum(res.values())
    shares = {c: (v / tot if tot else 0) for c, v in res.items()}
    return shares, notes
