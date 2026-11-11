"""Generation by fuel and power flows between balancing authorities, from EIA-930.

Files: EIA930_BALANCE_YYYY_{Jan_Jun,Jul_Dec}.csv (hourly generation by fuel per balancing
authority) and EIA930_INTERCHANGE_YYYY_*.csv (hourly flow with each neighbor; positive =
export from the reporting BA). Uses EIA's "(Adjusted)" generation columns.

Flow tracing (consumption-based mix): every hour, the power available in each balancing
authority is its own generation plus what flows in from neighbors. Assuming power mixes
proportionally, the fuel shares at every BA solve one linear system:
    P_i * c_i - sum_j F_ji * c_j = g_i        (P_i = generation + inflows into i)
so imports into CAISO are traced back through intermediate grids (e.g. LADWP, BANC) to the
plants that generated them. Flows from outside the traced area count as "unattributed".
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

# EIA-930 fuel columns -> our categories. Storage counts only when discharging (positive).
FUEL_COLS = {
    "Coal": "coal",
    "Natural Gas": "gas",
    "Nuclear": "nuclear",
    "All Petroleum Products": "oil",
    "Hydropower Excluding Pumped Storage": "hydro",
    "Solar without Integrated Battery Storage": "solar",
    "Solar with Integrated Battery Storage": "solar",
    "Wind without Integrated Battery Storage": "wind",
    "Wind with Integrated Battery Storage": "wind",
    "Geothermal": "geothermal",
    "Pumped Storage": "storage",
    "Battery Storage": "storage",
    "Other Energy Storage": "storage",
    "Unknown Energy Storage": "storage",
    "Other Fuel Sources": "other",
    "Unknown Fuel Sources": "unknown",
}
FUELS = ["solar", "wind", "hydro", "geothermal", "biomass", "waste", "nuclear", "gas", "coal", "oil", "storage", "other", "unknown"]
FI = {f: i for i, f in enumerate(FUELS)}
UNATTRIBUTED = len(FUELS)  # extra column for flows from outside the traced area
WEST_REGIONS = {"CAL", "NW", "SW"}  # EIA-930 regions of the Western Interconnection (US)


def _num(s: str):
    s = (s or "").replace(",", "").strip()
    return float(s) if s else None


def other_split(eia923_annual: dict, net930: dict) -> dict:
    """For each BA, how to split EIA-930's "other/unknown" MW into the sources EIA-930 leaves out.

    A source qualifies when EIA-923 (plant level) shows it in the BA but EIA-930 reports under 10%
    of that amount in its own column (e.g. geothermal, biomass, waste reported as "other").
    Returns {ba: shares over FUELS}; BAs with nothing to split are left out (stay "other").
    """
    out = {}
    for ba, a in eia923_annual.items():
        n = net930.get(ba)
        if n is None:
            continue
        w = np.zeros(len(FUELS))
        for f in ("geothermal", "biomass", "waste", "other"):
            v923 = a.get(f, 0)
            if v923 <= 0:
                continue
            if f == "other" or n[FI[f]] < 0.1 * v923:
                w[FI[f]] = v923
        if w[FI["other"]] < w.sum():  # something other than plain "other" to split into
            out[ba] = w / w.sum()
    return out


def read_generation(paths: list[Path], bas: set[str] | None = None, split: dict | None = None):
    """Hourly positive generation by fuel: {(ba, utc): np.array(len(FUELS))}, plus net totals per BA.

    `split` (from other_split) re-labels each hour's positive "other"/"unknown" MW into the
    sources EIA-923 shows for that BA. Gas, coal, solar, wind, hydro, nuclear stay as reported.
    """
    gen = {}
    net = defaultdict(lambda: np.zeros(len(FUELS)))
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rd = csv.DictReader(f)
            cols = [(c, FI[k]) for name, k in FUEL_COLS.items() if (c := f"Net Generation (MW) from {name} (Adjusted)") in rd.fieldnames]
            for r in rd:
                ba = r["Balancing Authority"]
                if bas is not None and ba not in bas:
                    continue
                v = np.zeros(len(FUELS))
                for c, i in cols:
                    x = _num(r[c])
                    if x is None:
                        continue
                    net[ba][i] += x
                    if x > 0:
                        v[i] += x
                if split and ba in split:
                    o = v[FI["other"]] + v[FI["unknown"]]
                    if o > 0:
                        v[FI["other"]] = v[FI["unknown"]] = 0
                        v += o * split[ba]
                gen[(ba, r["UTC Time at End of Hour"])] = v
    return gen, dict(net)


def read_interchange(paths: list[Path]):
    """Hourly flows {utc: {(from_ba, to_ba): MW}} for exports reported > 0, and each BA's region."""
    flows = defaultdict(dict)
    region = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                a, b = r["Balancing Authority"], r["Directly Interconnected Balancing Authority"]
                region[a] = r["Region"]
                region.setdefault(b, r["DIBA_Region"])
                v = _num(r["Interchange (MW)"])
                if v is None:
                    continue
                t = r["UTC Time at End of Hour"]
                if v > 0:
                    flows[t][(a, b)] = max(flows[t].get((a, b), 0.0), v)
                elif v < 0:
                    flows[t].setdefault((b, a), -v)  # use the other side's report only if the exporter didn't report
    return flows, region


def trace(gen: dict, flows: dict, nodes: list[str]):
    """Solve the flow-tracing system each hour. Returns {utc: (shares[n, F+1], inflow[n, n])}."""
    idx = {b: i for i, b in enumerate(nodes)}
    n, k = len(nodes), len(FUELS) + 1
    for t, f in flows.items():
        G = np.zeros((n, k))
        for b, i in idx.items():
            g = gen.get((b, t))
            if g is not None:
                G[i, : len(FUELS)] = g
        F = np.zeros((n, n))  # F[j, i] = flow from j into i
        for (a, b), v in f.items():
            if b in idx and a in idx:
                F[idx[a], idx[b]] += v
            elif b in idx:  # from outside the traced area
                G[idx[b], UNATTRIBUTED] += v
        P = G.sum(axis=1) + F.sum(axis=0)
        A = np.diag(P) - F.T
        ok = P > 0
        A[~ok, :] = 0
        A[~ok, ~ok] = 1
        B = G.copy()
        try:
            X = np.linalg.solve(A, B)  # X[i] = MW-weighted composition of power at i, scaled by P_i
        except np.linalg.LinAlgError:
            X = np.linalg.lstsq(A, B, rcond=None)[0]
        shares = np.divide(X, X.sum(axis=1, keepdims=True), out=np.zeros_like(X), where=X.sum(axis=1, keepdims=True) > 0)
        yield t, shares, F


def traced_imports(gen: dict, flows: dict, region: dict, targets: set[str]):
    """Annual MWh imported into the `targets` group from outside it, by fuel (traced)."""
    nodes = sorted({b for b, r in region.items() if r in WEST_REGIONS} | targets)
    idx = {b: i for i, b in enumerate(nodes)}
    total = np.zeros(len(FUELS) + 1)
    gross_by_source = defaultdict(float)
    hours = 0
    for t, shares, F in trace(gen, flows, nodes):
        hours += 1
        for j, b in enumerate(nodes):
            if b in targets:
                continue
            into = sum(F[j, idx[x]] for x in targets if x in idx)
            if into > 0:
                total += into * shares[j]
                gross_by_source[b] += into
        # flows straight from outside the traced area into a target
        for (a, b), v in flows[t].items():
            if b in targets and a not in idx:
                total[UNATTRIBUTED] += v
                gross_by_source[a] += v
    mix = {f: float(total[i]) for i, f in enumerate(FUELS)}
    mix["unattributed"] = float(total[UNATTRIBUTED])
    return mix, dict(gross_by_source), hours


def annual_mix(net: dict, ba: str) -> dict:
    """Annual generation by fuel for one BA (MWh). Net storage kept separately (it can be negative)."""
    v = net.get(ba)
    return {f: float(v[i]) for i, f in enumerate(FUELS)} if v is not None else {}
