"""Day-ahead DLAP prices: the hourly price each utility area's load pays (PG&E, SCE, SDG&E, VEA).

Kept in dlap-dam.json for yesterday, today and tomorrow (Pacific operating days). Downloaded in a
single OASIS request only when something is missing, so normally once a day: when tomorrow's
prices appear (~1 PM PT). CAISO corrections are picked up whenever a day is downloaded again.

Same rules as the nodal data: every value is published exactly as CAISO reports it, a day that
fails any check is not published (the previous copy stays), and problems raise an alert.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import config, fetch, publish, validate
from .validate import Issue

PT = ZoneInfo(config.MARKET_TZ)
KEY = f"{config.R2_PREFIX}/dlap-dam.json"


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """Midnight-to-midnight Pacific time for an operating day, in UTC (23/24/25 hours with DST)."""
    start = datetime.combine(d, time(0), PT)
    end = datetime.combine(d + timedelta(days=1), time(0), PT)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def wanted_days(now: datetime) -> list[date]:
    today = now.astimezone(PT).date()
    days = [today - timedelta(days=1), today]
    local = now.astimezone(PT)
    if (local.hour, local.minute) >= config.DAM_PUBLISHED_AFTER_PT:
        days.append(today + timedelta(days=1))
    return days


def parse(files: dict[str, str]) -> tuple[dict, list[Issue]]:
    """Return {date_iso: {start_iso: {"end": iso, area: {field: value}}}} and issues."""
    by_node = {node: code for code, (node, _) in config.DLAPS.items()}
    out: dict[str, dict[str, dict]] = {}
    issues: list[Issue] = []
    for name, text in files.items():
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("MARKET_RUN_ID") != "DAM":
                issues.append(Issue("error", "dlap", f"{name}: market {row.get('MARKET_RUN_ID')!r}, expected DAM"))
                return {}, issues
            area = by_node.get(row["NODE"])
            field = config.COMPONENTS.get(row["LMP_TYPE"])
            if area is None or field is None:
                continue
            start = datetime.fromisoformat(row["INTERVALSTARTTIME_GMT"])
            d = start.astimezone(PT).date().isoformat()
            hour = out.setdefault(d, {}).setdefault(start.isoformat(), {
                "end": datetime.fromisoformat(row["INTERVALENDTIME_GMT"]).isoformat()})
            prices = hour.setdefault(area, {})
            if field in prices:
                issues.append(Issue("error", "dlap", f"{area} {start.isoformat()} {row['LMP_TYPE']}: duplicate row"))
                continue
            try:
                prices[field] = float(row["MW"])  # OASIS puts the price in the "MW" column for PRC_LMP
            except ValueError:
                issues.append(Issue("error", "dlap", f"{area} {start.isoformat()}: not a number: {row['MW']!r}"))
    return out, issues


def check_day(d: str, hours: dict) -> list[Issue]:
    """All hours present, all four areas, all five components, and LMP = sum of components."""
    issues: list[Issue] = []
    start, end = day_bounds(date.fromisoformat(d))
    expected = int((end - start).total_seconds() // 3600)
    if len(hours) != expected:
        issues.append(Issue("error", "dlap", f"{d}: {len(hours)} hours, expected {expected}"))
    for h, v in hours.items():
        for area in config.DLAPS:
            p = v.get(area)
            if not p or set(p) != set(config.FIELD_ORDER):
                issues.append(Issue("error", "dlap", f"{d} {h}: {area} missing a price component"))
                continue
            parts = p["energy"] + p["congestion"] + p["loss"] + p["ghg"]
            allowed = sum(validate.value_uncertainty(p[f]) for f in config.FIELD_ORDER)
            if abs(parts - p["lmp"]) > allowed:
                issues.append(Issue("error", "dlap", f"{d} {h} {area}: LMP {p['lmp']} != parts {parts:.5f}"))
    return issues


def refresh(store, now: datetime, issues: list[Issue]) -> None:
    """Download missing days (one request) and republish dlap-dam.json."""
    old = store.get_json(KEY) or {}
    have = set(old.get("days", {}))
    days = wanted_days(now)
    missing = [d for d in days if d.isoformat() not in have]
    if not missing:
        return

    start, _ = day_bounds(min(missing))
    _, end = day_bounds(max(missing))
    try:
        raw = fetch.fetch_dam_dlaps(start, end)
    except fetch.NotPublished:
        tomorrow = now.astimezone(PT).date() + timedelta(days=1)
        level = "info" if missing == [tomorrow] else "warning"
        issues.append(Issue(level, "dlap", f"Day-ahead prices not available yet for {[d.isoformat() for d in missing]}"))
        return
    except fetch.FetchError as exc:
        issues.append(Issue("error", "dlap", f"Day-ahead DLAP download failed: {exc}"))
        return

    parsed, parse_issues = parse(raw.files)
    issues.extend(parse_issues)
    if any(i.severity == "error" for i in parse_issues):
        return

    keep = {d.isoformat() for d in days}
    out_days = {d: v for d, v in old.get("days", {}).items() if d in keep}
    for d, hours in parsed.items():
        if d not in keep:
            continue
        day_issues = check_day(d, hours)
        issues.extend(day_issues)
        if any(i.severity == "error" for i in day_issues):
            issues.append(Issue("error", "dlap", f"{d}: day-ahead prices not published"))
            continue
        out_days[d] = {
            "retrieved_utc": raw.retrieved_utc.isoformat(),
            "oasis_request": raw.url,
            "hours": [
                {"start": h, "end": v["end"], "prices": {a: [v[a][f] for f in config.FIELD_ORDER] for a in config.DLAPS}}
                for h, v in sorted(hours.items())
            ],
        }
    for d in missing:
        if d.isoformat() not in parsed and d != now.astimezone(PT).date() + timedelta(days=1):
            issues.append(Issue("warning", "dlap", f"{d.isoformat()}: no day-ahead rows returned"))

    store.put_json(KEY, {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "market": "CAISO Day-Ahead Market (IFM), hourly",
        "units": "$/MWh",
        "fields": config.FIELD_ORDER,
        "areas": {code: label for code, (_, label) in config.DLAPS.items()},
        "about": "Default Load Aggregation Point (DLAP) prices: the load-weighted average LMP that load "
                 "in each utility area pays. Values exactly as published by CAISO.",
        "source": config.SOURCE,
        "days": dict(sorted(out_days.items())),
    }, publish.CACHE_INDEX)
    print(f"dlap-dam.json: days {sorted(out_days)}")
