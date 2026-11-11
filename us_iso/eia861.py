"""Customers and retail prices by ISO, and per-utility figures, from EIA Form 861.

File: Sales_Ult_Cust_YYYY.xlsx, sheet "States" (one row per utility x state x balancing
authority x Schedule 4 part).

Schedule 4 parts (EIA-861 instructions):
  A = bundled (utility supplies energy and delivery)
  B = energy-only (supplier such as a CCA; another utility delivers)
  C = delivery-only (the wires utility for B's customers)
  D = bundled service by Texas retail electric providers
Each customer appears once in A, C or D; B duplicates C. So, for a region:
  customers = A + C + D,  MWh = A + C + D,  revenue = A + B + C + D (B = energy part of C's bills)
Cells shown as "." are withheld / not applicable: treated as missing, never zero.
"""

from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from pathlib import Path

import openpyxl

ISO_BY_BA = {"CISO": "CAISO", "ERCO": "ERCOT", "SWPP": "SPP", "MISO": "MISO", "PJM": "PJM", "NYIS": "NYISO", "ISNE": "ISO-NE"}

# Column positions in the "States" sheet (checked against the 2025 header rows).
C_YEAR, C_ID, C_NAME, C_PART, C_SERVICE, C_DTYPE, C_STATE, C_OWNER, C_BA = range(9)
C_REV, C_MWH, C_CUST = 21, 22, 23  # TOTAL revenue (thousand $), sales (MWh), customers


def _num(v):
    return v if isinstance(v, (int, float)) else None


def load_sales(zip_path: Path, year: int) -> list[tuple]:
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(f"Sales_Ult_Cust_{year}.xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = list(wb["States"].iter_rows(values_only=True))
    header = rows[2]
    assert header[C_ID] == "Utility Number" and header[C_PART] == "Part" and header[C_BA] == "BA Code", "EIA-861 layout changed"
    return [r for r in rows[3:] if r and r[C_ID] is not None]


def iso_totals(rows: list[tuple], region_of: dict | None = None) -> tuple[dict, list[str]]:
    """Customers, MWh, revenue and average price per region (default: ISO), plus check messages.

    region_of maps BA code -> region id; {ba: ba for ...} gives per-BA totals."""
    region_of = ISO_BY_BA if region_of is None else region_of
    t = defaultdict(lambda: defaultdict(float))
    missing = defaultdict(int)
    for r in rows:
        iso = region_of.get(r[C_BA])
        if not iso:
            continue
        p = r[C_PART]
        for col, key in ((C_CUST, "cust"), (C_MWH, "mwh"), (C_REV, "rev")):
            v = _num(r[col])
            if v is None:
                missing[iso] += 1
                continue
            t[iso][key + p] += v
    out, notes = {}, []
    for iso, x in t.items():
        mwh = x["mwhA"] + x["mwhC"] + x["mwhD"]
        rev_k = x["revA"] + x["revB"] + x["revC"] + x["revD"]
        out[iso] = {
            "customers": round(x["custA"] + x["custC"] + x["custD"]),
            "retail_mwh": round(mwh),
            "avg_price_cents_kwh": round(rev_k * 1000 / (mwh * 1000) * 100, 2) if mwh else None,
            "customers_other_supplier": round(x["custC"]),
        }
        if x["mwhB"] and (not x["mwhC"] or abs(x["mwhB"] - x["mwhC"]) / x["mwhC"] > 0.02):
            notes.append(f"{iso}: energy-only MWh ({x['mwhB']:.0f}) and delivery-only MWh ({x['mwhC']:.0f}) differ by more than 2%")
        if missing[iso]:
            notes.append(f"{iso}: {missing[iso]} withheld/blank cells treated as missing")
    return out, notes


def utilities(rows: list[tuple], region_of: dict | None = None) -> dict[str, list[dict]]:
    """Per region (default: ISO), every utility / retail provider with its customers and bundled price."""
    region_of = ISO_BY_BA if region_of is None else region_of
    u = defaultdict(lambda: defaultdict(float))
    meta = {}
    for r in rows:
        iso = region_of.get(r[C_BA])
        if not iso or r[C_PART] == "B":  # B (energy-only suppliers) shown via their delivery utility's split
            continue
        key = (iso, r[C_ID])
        if key not in meta:
            meta[key] = {"name": r[C_NAME], "ownership": r[C_OWNER], "states": set()}
        meta[key]["states"].add(r[C_STATE])
        p = r[C_PART]
        for col, k in ((C_CUST, "cust"), (C_MWH, "mwh"), (C_REV, "rev")):
            v = _num(r[col])
            if v is not None:
                u[key][k + p] += v
    out = defaultdict(list)
    for (iso, uid), x in u.items():
        cust = x["custA"] + x["custC"] + x["custD"]
        if cust <= 0:
            continue
        bundled_mwh = x["mwhA"] + x["mwhD"]
        bundled_rev = x["revA"] + x["revD"]
        m = meta[(iso, uid)]
        out[iso].append({
            "id": uid,
            "name": m["name"],
            "type": "Retail electric provider" if x["custD"] and not (x["custA"] or x["custC"]) else m["ownership"],
            "states": sorted(m["states"]),
            "customers": round(cust),
            # Average price paid by customers who buy both energy and delivery from this company.
            "bundled_price_cents_kwh": round(bundled_rev / bundled_mwh * 100, 2) if bundled_mwh > 0 else None,
            "share_other_supplier": round(x["custC"] / cust, 4) if cust else None,
        })
    for iso in out:
        out[iso].sort(key=lambda d: -d["customers"])
    return dict(out)
