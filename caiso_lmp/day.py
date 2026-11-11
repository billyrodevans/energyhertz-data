"""Build day.json: every mapped node's LMP for the whole 24-hour window in one small file.

Why: the map's slider redraws instantly from this one file instead of downloading a file per
15-minute step. Values are LMPs rounded to the nearest cent, used ONLY to color the map.
The exact published values (all decimals, plus the four components) stay in intervals/ and
are what the node panel shows.

It also fixes ONE color scale for the whole window (2nd-98th percentile of every LMP in it),
so a color means the same price at every step of the slider.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import config


def percentile(sorted_vals: list[float], p: float) -> float:
    i = round(p / 100 * (len(sorted_vals) - 1))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, i))]


def build_day(store, index: dict, located: dict[str, dict]) -> dict | None:
    """Return the day.json content, or None if there is nothing to build from."""
    entries = index.get("intervals", [])
    if not entries or not located:
        return None
    order = sorted(located)
    prefix = f"{config.R2_PREFIX}/intervals/"

    with ThreadPoolExecutor(max_workers=8) as pool:
        files = list(pool.map(lambda e: store.get_json(prefix + e["file"]), entries))

    rows, kept, all_lmps = [], [], []
    # 15-minute LMP at each utility area's DLAP, exact as published (for the utility price chart).
    dlap_fmm: dict[str, list[float | None]] = {code: [] for code in config.DLAPS}
    for e, iv in zip(entries, files):
        if iv is None:  # listed in the index but missing from storage: skip, never invent
            continue
        prices = iv["prices"]
        for code, (node, _) in config.DLAPS.items():
            p = prices.get(node)
            dlap_fmm[code].append(p[0] if p else None)
        row = []
        for n in order:
            p = prices.get(n)
            if p is None:
                row.append(None)
            else:
                row.append(round(p[0] * 100))
                all_lmps.append(p[0])
        rows.append(row)
        kept.append({"start": e["start"], "end": e["end"], "file": e["file"]})
    if not all_lmps:
        return None

    all_lmps.sort()
    return {
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "about": "LMP in cents/MWh, rounded to the nearest cent, for map colors only. "
                 "Exact published values are in intervals/.",
        "nodes": order,
        "intervals": kept,
        "scale": {
            "low": round(percentile(all_lmps, 2), 2),
            "high": round(percentile(all_lmps, 98), 2),
            "min": all_lmps[0],
            "max": all_lmps[-1],
            "basis": "2nd to 98th percentile of every mapped LMP in the window",
        },
        "outlier_bounds": [config.PLAUSIBLE_MIN, config.PLAUSIBLE_MAX],
        "dlap_fmm": dlap_fmm,
        "lmp_cents": rows,
    }
