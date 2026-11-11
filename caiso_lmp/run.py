"""Run one refresh.

    python -m caiso_lmp.run --out output            # test: write files to ./output
    python -m caiso_lmp.run --r2                    # production: upload to Cloudflare R2
    python -m caiso_lmp.run --out output --hour 2026-11-08T03:00Z   # a specific UTC hour

Each run downloads the current UTC hour (one OASIS request). If any interval of the
previous hour is missing from the site, that hour is re-downloaded too (one more request).

Exit codes: 0 = published with no errors (warnings possible), 1 = errors found.
Every issue is printed and written to alert.md for the GitHub workflow to report.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from . import config, day, dlap, fetch, publish, transform, validate
from .validate import Issue


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def refresh_nodes(store, issues: list[Issue]) -> dict[str, dict]:
    """Return node coordinates, re-downloading them if the stored copy is over a day old."""
    key = f"{config.R2_PREFIX}/nodes.json"
    stored = store.get_json(key)
    if stored:
        age = utc_now() - datetime.fromisoformat(stored["retrieved_utc"])
        if age < timedelta(hours=config.NODES_MAX_AGE_HOURS):
            return stored["nodes"]

    try:
        feed, retrieved = fetch.fetch_price_map()
        nodes, node_issues = transform.parse_price_map(feed)
        issues.extend(node_issues)
    except fetch.FetchError as exc:
        nodes, retrieved = {}, None
        issues.append(Issue("error", "nodes", f"Could not download node coordinates: {exc}"))

    if nodes and not any(i.severity == "error" for i in issues if i.check == "nodes"):
        store.put_json(key, {
            "retrieved_utc": retrieved.isoformat(),
            "source": config.SOURCE["locations"],
            "source_url": config.SOURCE["locations_url"],
            "count": len(nodes),
            "nodes": nodes,
        }, publish.CACHE_NODES)
        return nodes
    if stored:
        issues.append(Issue("warning", "nodes", "Using the previous node coordinates file (refresh failed)"))
        return stored["nodes"]
    return {}


def process_hour(store, hour_start: datetime, located: dict, issues: list[Issue],
                 is_retry: bool, previous_unpriced: list[str] | None) -> tuple[list[dict], list[str] | None]:
    """Download, check and publish one hour.

    Returns (index entries for published intervals, mapped nodes with no price).
    """
    label = hour_start.strftime("%Y-%m-%d %H:00 UTC")
    try:
        raw = fetch.fetch_hour(hour_start)
    except fetch.FetchError as exc:
        issues.append(Issue("error", "download", f"{label}: {exc}"))
        return [], None

    values, meta, parse_issues = transform.parse_hour(raw.files)
    issues.extend(parse_issues)
    if any(i.severity == "error" for i in parse_issues):
        issues.append(Issue("error", "publish", f"{label}: nothing published because the download failed checks"))
        return [], None

    issues.extend(validate.check_hour(hour_start, list(values), is_retry))

    # Location match, checked once per hour on all nodes priced this hour.
    priced = set().union(*(set(v) for v in values.values())) if values else set()
    loc_issues, unpriced = validate.check_locations(priced, located, previous_unpriced)
    issues.extend(loc_issues)
    if any(i.severity == "error" for i in loc_issues):
        issues.append(Issue("error", "publish", f"{label}: nothing published because node locations did not match"))
        return [], unpriced

    expected = {(hour_start + timedelta(minutes=15 * i)).isoformat() for i in range(config.INTERVALS_PER_HOUR)}
    entries = []
    for start in sorted(values):
        if start not in expected:
            continue  # outside the requested hour (already reported as an error)
        nodes = values[start]
        interval_issues = validate.check_interval(start, nodes, meta[start]["end"])
        issues.extend(interval_issues)
        if any(i.severity == "error" for i in interval_issues):
            issues.append(Issue("error", "publish", f"{start}: not published"))
            continue

        warnings = [str(i) for i in interval_issues if i.severity == "warning"]
        outliers = validate.find_outliers(nodes)
        key = publish.interval_key(start)
        store.put_json(key, {
            "interval_start_utc": start,
            "interval_end_utc": meta[start]["end"],
            "market": "CAISO Fifteen-Minute Market (FMM / RTPD)",
            "units": "$/MWh",
            "fields": config.FIELD_ORDER,
            "source": config.SOURCE,
            "caiso_files": meta[start]["caiso_files"],
            "oasis_request": raw.url,
            "retrieved_utc": raw.retrieved_utc.isoformat(),
            "node_count": len(nodes),
            "warnings": warnings,
            # Nodes with LMP outside the sanity bounds: published as-is, marked on the map.
            "outlier_bounds": [config.PLAUSIBLE_MIN, config.PLAUSIBLE_MAX],
            "outliers": outliers,
            # Values exactly as published by CAISO, in the order of "fields".
            "prices": {n: [v[f] for f in config.FIELD_ORDER] for n, v in sorted(nodes.items())},
        }, publish.CACHE_INTERVAL)
        entries.append({
            "start": start,
            "end": meta[start]["end"],
            "file": key.rsplit("/", 1)[-1],
            "nodes": len(nodes),
            "warnings": len(warnings),
            "outliers": len(outliers),
            "retrieved_utc": raw.retrieved_utc.isoformat(),
        })
    return entries, unpriced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--out", help="write files to this local folder (testing)")
    where.add_argument("--r2", action="store_true", help="upload to Cloudflare R2 (needs R2_* environment variables)")
    parser.add_argument("--hour", help="UTC hour to fetch, e.g. 2026-11-08T03:00Z (default: current hour)")
    parser.add_argument("--alert-file", default="alert.md", help="where to write the issue report")
    parser.add_argument("--skip-if-complete", action="store_true",
                        help="backup run: exit without contacting CAISO if the current hour is already published")
    args = parser.parse_args(argv)

    store = publish.R2Store() if args.r2 else publish.LocalStore(args.out)
    started = utc_now()
    hour = (datetime.fromisoformat(args.hour.replace("Z", "+00:00")) if args.hour else started)
    hour = hour.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)

    if args.skip_if_complete:
        # GitHub sometimes skips a scheduled run. The backup run only does work if the
        # main run's results are missing, so CAISO normally sees one request per hour.
        index = store.get_json(f"{config.R2_PREFIX}/index.json") or {}
        have = {e["start"] for e in index.get("intervals", [])}
        wanted = [(hour + timedelta(minutes=15 * i)).isoformat() for i in range(config.INTERVALS_PER_HOUR)]
        if all(w in have for w in wanted):
            print("Backup run: current hour already complete, nothing to do.")
            return 0

    issues: list[Issue] = []
    located = refresh_nodes(store, issues)

    hours = [hour]
    previous = hour - timedelta(hours=1)
    old_index = store.get_json(f"{config.R2_PREFIX}/index.json") or {}
    have = {e["start"] for e in old_index.get("intervals", [])}
    if old_index and any((previous + timedelta(minutes=15 * i)).isoformat() not in have for i in range(4)):
        hours.insert(0, previous)

    previous_unpriced = old_index.get("last_run", {}).get("unpriced_map_nodes")
    entries = []
    for h in hours:
        new, unpriced = process_hour(store, h, located, issues, is_retry=(h != hour), previous_unpriced=previous_unpriced)
        entries += new
        if unpriced is not None:
            previous_unpriced = unpriced

    # Day-ahead utility-area (DLAP) prices: downloads only when a day is missing (~once a day).
    try:
        dlap.refresh(store, utc_now(), issues)
    except Exception as exc:
        issues.append(Issue("error", "dlap", f"Day-ahead DLAP refresh failed: {exc}"))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    alerts = errors + warnings
    status = {
        "started_utc": started.isoformat(),
        "finished_utc": utc_now().isoformat(),
        "hours_requested": [h.isoformat() for h in hours],
        "intervals_published": [e["start"] for e in entries],
        "result": "errors" if errors else ("warnings" if warnings else "passed"),
        "errors": len(errors),
        "warnings": len(warnings),
        "mapped_nodes": len(located),
        "unpriced_map_nodes": previous_unpriced or [],
    }
    index = publish.prune_and_index(store, entries, status)

    # One-file summary of the whole window for the map's smooth slider (colors only).
    try:
        day_file = day.build_day(store, index, located)
        if day_file:
            store.put_json(f"{config.R2_PREFIX}/day.json", day_file, publish.CACHE_INDEX)
            print(f"day.json: {len(day_file['intervals'])} intervals x {len(day_file['nodes'])} nodes, "
                  f"scale ${day_file['scale']['low']} to ${day_file['scale']['high']}")
    except Exception as exc:  # the exact interval files are already published; flag and carry on
        issue = Issue("warning", "day-file", f"Could not build day.json (map falls back to per-interval files): {exc}")
        issues.append(issue)
        alerts.append(issue)

    print(f"Result: {status['result']}  published {len(entries)} intervals, "
          f"{len(index['intervals'])} kept, {len(errors)} errors, {len(warnings)} warnings")
    for i in issues:
        print(i)

    # Errors and warnings go to alert.md; the GitHub workflow turns that into a GitHub issue.
    if alerts:
        with open(args.alert_file, "w", encoding="utf-8") as f:
            f.write(f"## CAISO LMP refresh: {status['result']}\n\n")
            f.write(f"Run started {status['started_utc']}. Hours requested: {', '.join(status['hours_requested'])}.\n\n")
            for i in alerts:
                f.write(f"- {i}\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
