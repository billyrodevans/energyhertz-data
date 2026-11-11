"""Monthly validity check for the US ISO estimates (runs on the 12th; first run 2026-12-12).

For the previous calendar month it compares:
  1. CAISO-reported imports (Today's Outlook) vs EIA-930 gross imports into CAISO
  2. The traced import mix for the month vs the published yearly estimate (regions.json)
  3. CAISO's own renewable share inside CAISO vs EIA-930's for the same month
and writes checks.md, which the workflow posts as a GitHub issue for Billy.

    python -m us_iso.validate --out output      (reads regions.json from ./output)
    python -m us_iso.validate --r2               (reads regions.json from R2)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from caiso_lmp.publish import LocalStore, R2Store

from . import caiso_mix, eia923, eia930, sources

IMPORT_GAP_LIMIT = 0.25  # flag if CAISO and EIA import totals differ by more than 25%
SHARE_GAP_LIMIT = 0.05   # flag if a fuel's share moves by more than 5 percentage points


def previous_month(today: date) -> tuple[date, date]:
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1), last_prev


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--out")
    where.add_argument("--r2", action="store_true")
    ap.add_argument("--month", help="YYYY-MM to check (default: previous month)")
    ap.add_argument("--checks-file", default="checks.md")
    a = ap.parse_args(argv)
    store = R2Store() if a.r2 else LocalStore(a.out)

    if a.month:
        y, m = map(int, a.month.split("-"))
        start = date(y, m, 1)
        end = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    else:
        start, end = previous_month(date.today())
    label = start.strftime("%Y-%m")
    lines, flags = [], []

    # The current year's EIA-930 files grow every day: always fetch fresh copies.
    for kind in ("BALANCE", "INTERCHANGE"):
        for half in ("Jan_Jun", "Jul_Dec"):
            p = sources.CACHE / f"eia930/EIA930_{kind}_{start.year}_{half}.csv"
            if start.year >= date.today().year and p.exists():
                p.unlink()
    flows_all, region = eia930.read_interchange(sources.eia_930("INTERCHANGE", start.year))
    _, net_raw = eia930.read_generation(sources.eia_930("BALANCE", start.year))
    # Same "other" split as the yearly build, using the latest final EIA-923 year available.
    plants = None
    for py in (start.year - 1, start.year - 2):
        try:
            plants, _ = eia923.load(sources.eia_923(py), py)
            break
        except Exception:
            continue
    split = eia930.other_split(plants, net_raw) if plants else None
    gen_all, _ = eia930.read_generation(sources.eia_930("BALANCE", start.year), split=split)
    def month_of(t: str) -> str:  # "MM/DD/YYYY hh:mm:ss AM" -> "YYYY-MM"
        return f"{t[6:10]}-{t[0:2]}"

    flows = {t: f for t, f in flows_all.items() if month_of(t) == label}
    gen = {k: v for k, v in gen_all.items() if month_of(k[1]) == label}
    if len(flows) < 24 * (end - start).days:
        flags.append(f"EIA-930 has only {len(flows)} hours of interchange for {label} so far")
    imp, src, hours = eia930.traced_imports(gen, flows, region, {"CISO"})
    eia_imports = sum(imp.values())

    caiso, problems = caiso_mix.annual(sources.caiso_fuel_days(start, end))
    flags += problems
    caiso_imports = caiso.get("imports", 0)
    lines.append(f"CAISO-reported imports: {caiso_imports/1e6:.2f} TWh; EIA-930 gross imports into CAISO: {eia_imports/1e6:.2f} TWh ({hours} hours)")
    if eia_imports and abs(caiso_imports - eia_imports) / eia_imports > IMPORT_GAP_LIMIT:
        flags.append(f"Import totals differ by {abs(caiso_imports - eia_imports) / eia_imports:.0%} (limit {IMPORT_GAP_LIMIT:.0%})")

    published = (store.get_json("us-iso/regions.json") or {}).get("regions", {}).get("CAISO", {})
    yearly = published.get("imports_mix_estimated", {})
    month_mix = {k: v / eia_imports for k, v in imp.items()} if eia_imports else {}
    for k in sorted((set(yearly) | set(month_mix)) - {"storage"}):  # storage is left out of the yearly pie
        d = month_mix.get(k, 0) - yearly.get(k, 0)
        lines.append(f"Import mix {k}: month {month_mix.get(k, 0):.1%} vs yearly {yearly.get(k, 0):.1%}")
        if abs(d) > SHARE_GAP_LIMIT:
            flags.append(f"Import share of {k} moved {d:+.1%} from the yearly estimate (seasonal changes are expected; please review)")

    ren_keys = ("solar", "wind", "geothermal", "biomass", "biogas", "small_hydro", "large_hydro")
    inside = {k: v for k, v in caiso.items() if k != "imports" and v > 0}
    ren_caiso = sum(inside.get(k, 0) for k in ren_keys) / sum(inside.values()) if inside else 0
    ciso_hours = [v for (ba, _), v in gen.items() if ba == "CISO"]
    ciso_total = sum(ciso_hours) if ciso_hours else None  # array of MWh by fuel for the month
    ren_eia = 0.0
    if ciso_total is not None and ciso_total.sum() > 0:
        ren_eia = sum(ciso_total[eia930.FI[k]] for k in ("solar", "wind", "hydro", "geothermal")) / ciso_total.sum()
    lines.append(f"Renewable share inside CAISO: CAISO data {ren_caiso:.1%}; EIA-930 {ren_eia:.1%} (the published mix uses EIA-923; EIA-930's CAISO fuel labels are known to overstate gas)")

    with open(a.checks_file, "w", encoding="utf-8") as fh:
        fh.write(f"## Monthly check of US ISO estimates: {label} ({'please review' if flags else 'no flags'})\n\n")
        for f in flags:
            fh.write(f"- [FLAG] {f}\n")
        for l in lines:
            fh.write(f"- {l}\n")
        fh.write("\nMethods: see the us_iso section of README.md. This check was requested by Billy to test the estimates before a full year of data.\n")
    print(open(a.checks_file, encoding="utf-8").read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
