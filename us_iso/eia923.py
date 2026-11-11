"""Annual generation by fuel for each balancing authority, from EIA Form 923 (plant level, final).

File: EIA923_Schedules_2_3_4_5_M_12_YYYY_Final.xlsx, sheet "Page 1 Generation and Fuel Data".
Each row is a plant x prime mover x fuel with its annual net generation (MWh) and the plant's
balancing authority. This is EIA's most complete plant-level record, so it's used for every
region's annual mix: "generation from power plants located in the region" (including industrial
plants that use some of their own output on site).
"""

from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from pathlib import Path

import openpyxl

# EIA fuel codes -> our categories (EIA-923 instructions, fuel type codes).
FUEL_CODES = {
    "NG": "gas", "OG": "gas", "BFG": "gas", "PG": "gas", "SGC": "gas",
    "BIT": "coal", "SUB": "coal", "LIG": "coal", "RC": "coal", "SC": "coal", "WC": "coal", "SGP": "coal",
    "DFO": "oil", "RFO": "oil", "JF": "oil", "KER": "oil", "PC": "oil", "WO": "oil",
    "NUC": "nuclear", "WAT": "hydro", "SUN": "solar", "WND": "wind", "GEO": "geothermal",
    "WDS": "biomass", "WDL": "biomass", "BLQ": "biomass", "LFG": "biomass", "OBG": "biomass",
    "AB": "biomass", "OBS": "biomass", "OBL": "biomass", "SLW": "biomass", "MSB": "biomass",
    "MSN": "waste", "MSW": "waste", "TDF": "waste",
    "MWH": "storage",  # net: charging is negative
    "WH": "other", "PUR": "other", "OTH": "other", "H2": "other",
}
CATEGORIES = ["solar", "wind", "hydro", "geothermal", "biomass", "nuclear", "gas", "coal", "oil", "waste", "other", "storage"]
RENEWABLE = {"solar", "wind", "hydro", "geothermal", "biomass"}


def load(zip_path: Path, year: int) -> tuple[dict, list[str]]:
    """Annual MWh by category for every balancing authority, plus notes (unknown fuel codes)."""
    name = f"EIA923_Schedules_2_3_4_5_M_12_{year}_Final.xlsx"
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(name)
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = wb["Page 1 Generation and Fuel Data"].iter_rows(values_only=True)
    header = None
    for i, r in enumerate(rows):
        if i == 5:
            header = [str(c).replace("\n", " ") if c else "" for c in r]
            break
    ba = header.index("Balancing Authority Code")
    fuel = header.index("Reported Fuel Type Code")
    ng = header.index("Net Generation (Megawatthours)")
    out = defaultdict(lambda: defaultdict(float))
    unknown = defaultdict(float)
    for r in rows:
        if not r or not r[ba]:
            continue
        v = r[ng] if isinstance(r[ng], (int, float)) else None
        if v is None:
            continue
        cat = FUEL_CODES.get(r[fuel])
        if cat is None:
            unknown[r[fuel]] += v
            cat = "other"
        out[r[ba]][cat] += v
    notes = [f"EIA-923 fuel code {k!r} not mapped ({v/1e3:.0f} GWh), counted as other" for k, v in unknown.items() if abs(v) > 1000]
    return {k: dict(v) for k, v in out.items()}, notes


def mix(annual: dict) -> tuple[dict, float, float]:
    """Shares of positive generation (storage excluded), renewable share, total MWh."""
    gen = {k: v for k, v in annual.items() if k != "storage" and v > 0}
    tot = sum(gen.values())
    shares = {k: round(v / tot, 5) for k, v in sorted(gen.items(), key=lambda x: -x[1])} if tot else {}
    ren = sum(v for k, v in gen.items() if k in RENEWABLE) / tot if tot else 0
    return shares, ren, tot
