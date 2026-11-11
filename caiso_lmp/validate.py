"""Checks that run on every refresh.

Severity:
  error   -> the interval (or the whole run) is NOT published. The site keeps the last good data.
  warning -> data is published, but Billy is alerted to review it.
  info    -> expected, self-resolving situations (logged only, no alert).
Nothing is ever corrected, filled in, or dropped silently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import config


@dataclass
class Issue:
    severity: str  # "error", "warning" or "info"
    check: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.check}: {self.message}"


def value_uncertainty(value: float) -> float:
    """How far a published CAISO price can be from its exact value, from rounding alone.

    Single-precision step size at this magnitude (2^(exponent - 23)) plus one step in the
    5th decimal. E.g. 52.6 -> 0.000014, 876.6 -> 0.000071, 2029 -> 0.000132, 2073 -> 0.000254.
    """
    v = abs(value)
    step = 2.0 ** (math.floor(math.log2(v)) - config.FLOAT32_MANTISSA_BITS) if v > 0 else 0.0
    return step + config.DECIMAL_STEP


def check_interval(start_iso: str, nodes: dict[str, dict[str, float]], end_iso: str) -> list[Issue]:
    """Checks for one 15-minute interval."""
    issues: list[Issue] = []
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)

    if end - start != timedelta(minutes=config.INTERVAL_MINUTES):
        issues.append(Issue("error", "interval", f"{start_iso}: interval is {end - start}, expected 15 minutes"))
    if start.minute % config.INTERVAL_MINUTES:
        issues.append(Issue("error", "interval", f"{start_iso}: does not start on a 15-minute boundary"))

    incomplete = [n for n, v in nodes.items() if set(v) != set(config.FIELD_ORDER)]
    if incomplete:
        issues.append(Issue(
            "error", "completeness",
            f"{start_iso}: {len(incomplete)} nodes missing a price component, e.g. {incomplete[:5]}",
        ))

    sum_bad = []
    out_of_range = []
    for node, v in nodes.items():
        if set(v) != set(config.FIELD_ORDER):
            continue
        parts = v["energy"] + v["congestion"] + v["loss"] + v["ghg"]
        allowed = sum(value_uncertainty(v[f]) for f in config.FIELD_ORDER)
        if abs(parts - v["lmp"]) > allowed:
            sum_bad.append(f"{node} (LMP {v['lmp']}, parts sum {parts:.5f}, allowed ±{allowed:.5f})")
        if not (config.PLAUSIBLE_MIN <= v["lmp"] <= config.PLAUSIBLE_MAX):
            out_of_range.append(f"{node} ({v['lmp']})")
    if sum_bad:
        issues.append(Issue(
            "error", "components",
            f"{start_iso}: LMP != energy + congestion + loss + GHG at {len(sum_bad)} nodes, e.g. {sum_bad[:5]}",
        ))
    if out_of_range:
        issues.append(Issue(
            "warning", "range",
            f"{start_iso}: {len(out_of_range)} LMPs outside ${config.PLAUSIBLE_MIN:.0f} to "
            f"${config.PLAUSIBLE_MAX:.0f}/MWh (published as-is; please review), e.g. {out_of_range[:5]}",
        ))
    return issues


def check_hour(hour_start: datetime, starts: list[str], is_retry: bool = False) -> list[Issue]:
    """Did we get the four intervals of the requested hour, and nothing else?

    A missing interval on the first try is "info" (CAISO may not have published it yet;
    the next run retries). Still missing on the retry -> "warning".
    """
    issues: list[Issue] = []
    expected = {(hour_start + timedelta(minutes=15 * i)).isoformat() for i in range(config.INTERVALS_PER_HOUR)}
    got = set(starts)
    extra = got - expected
    missing = expected - got
    if extra:
        issues.append(Issue("error", "interval", f"Intervals outside the requested hour: {sorted(extra)}"))
    if missing:
        if is_retry:
            issues.append(Issue("warning", "interval", f"Still not published on retry (shown as 'no data'): {sorted(missing)}"))
        else:
            issues.append(Issue("info", "interval", f"Not published yet, next run retries: {sorted(missing)}"))
    return issues


def check_locations(price_nodes: set[str], located: dict[str, dict], previous_unpriced: list[str] | None) -> tuple[list[Issue], list[str]]:
    """How well do price nodes and map coordinates line up?

    Returns (issues, unpriced) where unpriced = mapped nodes with no OASIS price.
    That list is expected to be small and stable, so it only raises a warning when it changes.
    """
    issues: list[Issue] = []
    unpriced = sorted(set(located) - price_nodes)
    if previous_unpriced is None or unpriced != previous_unpriced:
        if unpriced:
            issues.append(Issue(
                "warning", "location",
                f"{len(unpriced)} price-map nodes have no OASIS price (listed, not plotted); "
                f"this list changed since the last run. e.g. {unpriced[:5]}",
            ))
    matched = len(price_nodes & set(located))
    if located and matched / len(located) < 0.95:
        issues.append(Issue(
            "error", "location",
            f"Only {matched} of {len(located)} mapped nodes matched an OASIS price (expected over 95%)",
        ))
    return issues, unpriced
