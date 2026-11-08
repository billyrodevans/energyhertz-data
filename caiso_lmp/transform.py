"""Reshape CAISO's files into the site's format. Values are copied, never altered.

CAISO's group download has one CSV per price component (LMP, MCE, MCC, MCL, MGHG),
with one row per node per 15-minute interval. We regroup that into one record per
interval: {node_id: [lmp, energy, congestion, loss, ghg]}.

Every problem found while reshaping is recorded as an Issue (see validate.py),
never silently fixed.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime

from . import config
from .validate import Issue


def parse_time(text: str) -> datetime:
    """OASIS times look like 2026-11-08T03:00:00-00:00."""
    return datetime.fromisoformat(text)


def parse_hour(files: dict[str, str]) -> tuple[dict, dict, list[Issue]]:
    """Return (values, meta, issues).

    values: {interval_start_iso: {node_id: {field: float}}}
    meta:   {interval_start_iso: {"end": iso, "caiso_files": [...]}}
    """
    values: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    meta: dict[str, dict] = {}
    issues: list[Issue] = []
    seen_components: set[str] = set()

    for name, text in sorted(files.items()):
        reader = csv.DictReader(io.StringIO(text))
        required = {"INTERVALSTARTTIME_GMT", "INTERVALENDTIME_GMT", "NODE", "LMP_TYPE", "MARKET_RUN_ID", "PRC"}
        missing_cols = required - set(reader.fieldnames or [])
        if missing_cols:
            issues.append(Issue("error", "columns", f"{name}: missing columns {sorted(missing_cols)}"))
            continue

        for row in reader:
            component = row["LMP_TYPE"]
            field = config.COMPONENTS.get(component)
            if field is None:
                issues.append(Issue("error", "component", f"{name}: unknown LMP_TYPE {component!r}"))
                break
            seen_components.add(component)
            if row["MARKET_RUN_ID"] != "RTPD":
                issues.append(Issue("error", "market", f"{name}: market {row['MARKET_RUN_ID']!r}, expected RTPD"))
                break

            start = parse_time(row["INTERVALSTARTTIME_GMT"]).isoformat()
            node = row["NODE"]
            try:
                price = float(row["PRC"])
            except ValueError:
                issues.append(Issue("error", "number", f"{node} {start} {component}: not a number: {row['PRC']!r}"))
                continue

            if field in values[start][node]:
                issues.append(Issue("error", "duplicate", f"{node} {start} {component}: duplicate row"))
                continue
            values[start][node][field] = price
            m = meta.setdefault(start, {"end": parse_time(row["INTERVALENDTIME_GMT"]).isoformat(), "caiso_files": set()})
            m["caiso_files"].add(name)

    for component in config.COMPONENTS:
        if component not in seen_components:
            issues.append(Issue("error", "component", f"No {component} rows in the download"))

    for m in meta.values():
        m["caiso_files"] = sorted(m["caiso_files"])
    return {k: dict(v) for k, v in values.items()}, meta, issues


def parse_price_map(feed: dict) -> tuple[dict[str, dict], list[Issue]]:
    """Extract node coordinates from the price map feed.

    Returns {node_id: {"lat", "lon", "area", "type"}}. Prices in the feed are ignored:
    official prices come from OASIS.
    """
    issues: list[Issue] = []
    markers = []
    for layer in feed.get("l", []):
        for m in layer.get("m", []) or []:
            if isinstance(m, dict) and m.get("t") == "Node":
                markers.append(m)
    if not markers:
        issues.append(Issue("error", "nodes", "Price map feed had no node markers (format may have changed)"))
        return {}, issues

    nodes: dict[str, dict] = {}
    for m in markers:
        node_id = m.get("n")
        coords = m.get("c")
        if not node_id or not isinstance(coords, list) or len(coords) != 2:
            issues.append(Issue("warning", "nodes", f"Malformed price map marker: {str(m)[:120]}"))
            continue
        lat, lon = coords
        if not (config.WEST_LAT[0] <= lat <= config.WEST_LAT[1] and config.WEST_LON[0] <= lon <= config.WEST_LON[1]):
            issues.append(Issue("warning", "location", f"{node_id} at ({lat}, {lon}) is outside the Western US box; not plotted"))
            continue
        if node_id in nodes:
            issues.append(Issue("warning", "nodes", f"{node_id} appears twice in the price map; kept the first"))
            continue
        nodes[node_id] = {"lat": lat, "lon": lon, "area": m.get("a"), "type": m.get("p")}
    return nodes, issues
