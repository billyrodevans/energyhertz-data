"""Build the yearly US ISO comparison and publish it.

    python -m us_iso.build --year 2025 --out output     # local test
    python -m us_iso.build --year 2025 --r2             # publish to Cloudflare R2

Outputs (folder "us-iso/" in the bucket):
    regions.json        per ISO: customers, average retail price, generation mix (+ CAISO imports)
    utilities.json      per ISO: every utility / retail provider (customers, bundled price, other-supplier share)
    residual.json       estimated mix of California's "unspecified" market power (residual mix)
    boundaries.geojson  HIFLD ISO boundaries (approximate, as of 2020), simplified
    groups.json         regions without an ISO: groups of balancing authorities, each with its
                        member BAs and their sums (see groups.py)
    groups.geojson      group outlines from HIFLD Control Areas (approximate, 2018-2021)
    checks.md           every check and warning from this run (also opened as a GitHub issue)

Generation mix for every region: EIA-923 (plant-level, final) = power plants located in the
region. CAISO imports: EIA-930 hourly flows traced to their source grids (estimated).
CAISO's own fuel data is used only as a cross-check.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone

from caiso_lmp.publish import LocalStore, R2Store  # same storage helpers as the price map

from . import caiso_mix, eia861, eia923, eia930, groups, residual, sources

PREFIX = "us-iso"
ISO_ORDER = ["CAISO", "ERCOT", "SPP", "MISO", "PJM", "NYISO", "ISO-NE"]
BA_OF = {v: k for k, v in eia861.ISO_BY_BA.items()}
HIFLD_NAMES = {
    "CALIFORNIA INDEPENDENT SYSTEM OPERATOR": "CAISO",
    "ELECTRIC RELIABILITY COUNCIL OF TEXAS, INC.": "ERCOT",
    "SOUTHWEST POWER POOL": "SPP",
    "MIDCONTINENT INDEPENDENT TRANSMISSION SYSTEM OPERATOR, INC..": "MISO",
    "PJM INTERCONNECTION, LLC": "PJM",
    "NEW YORK INDEPENDENT SYSTEM OPERATOR": "NYISO",
    "ISO NEW ENGLAND INC.": "ISO-NE",
}

SOURCES = {
    "customers_price": {"name": "EIA Form 861 (Sales to Ultimate Customers)", "url": "https://www.eia.gov/electricity/data/eia861/"},
    "generation": {"name": "EIA Form 923 (plant-level generation, final)", "url": "https://www.eia.gov/electricity/data/eia923/"},
    "flows": {"name": "EIA-930 Hourly Electric Grid Monitor (interchange)", "url": "https://www.eia.gov/electricity/gridmonitor/"},
    "boundaries": {"name": "HIFLD Independent System Operators (approximate, as of 2020)", "url": "https://hifld-geoplatform.hub.arcgis.com/"},
    "ba_boundaries": {"name": "HIFLD Control Areas (approximate, 2018-2021)", "url": "https://hifld-geoplatform.hub.arcgis.com/"},
    "labels": {"name": "CEC 2024 Power Content Labels", "url": "https://www.energy.ca.gov/programs-and-topics/programs/power-source-disclosure-program/power-content-label/annual-power-5"},
    "caiso_check": {"name": "California ISO, Today's Outlook fuel source history (cross-check)", "url": "https://www.caiso.com/todays-outlook/supply"},
}

NOTES = {
    "mix": "Generation from power plants located within each ISO's territory (EIA-923). The power a utility "
           "or customer actually buys can differ because of purchase agreements and imports.",
    "caiso_imports": "CAISO imports are estimated: hourly power flows between Western grids (EIA-930) traced "
                     "back to the generating grids, whose 'other' generation is split using EIA-923 plant data.",
    "renewable": "Renewable = solar, wind, hydro (all sizes), geothermal and biomass, following EIA. "
                 "California's RPS does not count large hydro as renewable, so California utility labels show lower shares.",
    "retail_price": "Average retail price = total retail revenue / retail sales, all customer classes (EIA-861).",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--out")
    where.add_argument("--r2", action="store_true")
    ap.add_argument("--year", type=int, default=date.today().year - 1)
    ap.add_argument("--label-year", type=int, default=2024, help="year of the CEC Power Content Labels (residual mix)")
    ap.add_argument("--checks-file", default="checks.md")
    a = ap.parse_args(argv)
    store = R2Store() if a.r2 else LocalStore(a.out)
    y, ly = a.year, a.label_year
    warn, info = [], []

    # ---- Customers and retail prices (EIA-861) ----
    rows = eia861.load_sales(sources.eia_861(y), y)
    totals, notes = eia861.iso_totals(rows)
    info += notes
    utils = eia861.utilities(rows)

    # ---- Generation mix by region (EIA-923) ----
    plants, n923 = eia923.load(sources.eia_923(y), y)
    info += n923

    # ---- CAISO imports: EIA-930 flows traced to source grids ----
    flows, region = eia930.read_interchange(sources.eia_930("INTERCHANGE", y))
    _, net_raw = eia930.read_generation(sources.eia_930("BALANCE", y))
    split = eia930.other_split(plants, net_raw)
    gen, _ = eia930.read_generation(sources.eia_930("BALANCE", y), split=split)
    imp, imp_by_src, hours = eia930.traced_imports(gen, flows, region, {"CISO"})
    imp_total = sum(imp.values())
    expected_hours = (date(y + 1, 1, 1) - date(y, 1, 1)).days * 24
    if hours < expected_hours:
        warn.append(f"Import tracing: {expected_hours - hours} hours of {y} have no EIA-930 flow data (skipped, not filled)")
    if imp_total and imp["unattributed"] / imp_total > 0.02:
        warn.append(f"{imp['unattributed']/imp_total:.1%} of CAISO imports could not be traced to a source grid")

    regions = {}
    for iso in ISO_ORDER:
        ba = BA_OF[iso]
        shares, ren, gen_total = eia923.mix(plants.get(ba, {}))
        if not shares:
            warn.append(f"{iso}: no EIA-923 generation found for balancing authority {ba}")
        r = dict(totals.get(iso, {}))
        r.update({
            "generation_mwh": round(gen_total),
            "mix": shares,
            "renewable_share": round(ren, 4),
            "storage_net_mwh": round(plants.get(ba, {}).get("storage", 0)),
        })
        if shares.get("other", 0) + shares.get("waste", 0) > 0.05:
            warn.append(f"{iso}: 'other' + 'waste' is {shares.get('other',0)+shares.get('waste',0):.1%} of the mix")
        if iso == "CAISO":
            imp_pos = {k: v for k, v in imp.items() if v > 0 and k != "storage"}
            ren_imp = sum(v for k, v in imp_pos.items() if k in eia923.RENEWABLE)
            combined = {k: v for k, v in plants[ba].items() if k != "storage" and v > 0}
            for k, v in imp_pos.items():
                combined[f"imports_{k}"] = v
            ctot = sum(combined.values())
            ren_in = ren * gen_total
            r.update({
                "imports_mwh": round(imp_total),
                "imports_mix_estimated": {k: round(v / imp_total, 5) for k, v in sorted(imp_pos.items(), key=lambda x: -x[1])},
                "imports_by_source_mwh": {k: round(v) for k, v in sorted(imp_by_src.items(), key=lambda x: -x[1])[:12]},
                "mix_with_imports": {k: round(v / ctot, 5) for k, v in sorted(combined.items(), key=lambda x: -x[1])},
                "renewable_share_with_imports": round((ren_in + ren_imp) / ctot, 4),
                "imports_hours_with_data": hours,
            })
        regions[iso] = r

    # ---- Cross-check: CAISO's own fuel data vs EIA-923 (never used for the published mix) ----
    caiso, gaps = caiso_mix.annual(sources.caiso_fuel_days(date(y, 1, 1), date(y, 12, 31)))
    info += [f"CAISO cross-check file gap: {g}" for g in gaps]
    inside = {k: v for k, v in caiso.items() if k not in ("imports", "batteries") and v > 0}
    ren_c = sum(inside.get(k, 0) for k in ("solar", "wind", "geothermal", "biomass", "biogas", "small_hydro", "large_hydro")) / sum(inside.values())
    gap = abs(ren_c - regions["CAISO"]["renewable_share"])
    msg = f"CAISO renewable share inside CAISO: EIA-923 {regions['CAISO']['renewable_share']:.1%} vs CAISO's own data {ren_c:.1%}"
    (warn if gap > 0.05 else info).append(msg + (" (difference over 5 points)" if gap > 0.05 else ""))
    info.append(f"Imports: EIA-930 gross into CAISO {imp_total/1e6:.1f} TWh; CAISO-reported {caiso.get('imports', 0)/1e6:.1f} TWh")

    # ---- Residual mix for California "unspecified" power (label year) ----
    lplants, _ = eia923.load(sources.eia_923(ly), ly)
    lflows, lregion = eia930.read_interchange(sources.eia_930("INTERCHANGE", ly))
    _, lnet = eia930.read_generation(sources.eia_930("BALANCE", ly))
    lgen, _ = eia930.read_generation(sources.eia_930("BALANCE", ly), split=eia930.other_split(lplants, lnet))
    ca_imports, _, _ = eia930.traced_imports(lgen, lflows, lregion, residual.CA_BAS)
    supply = residual.supply_from_plants(lplants, ca_imports)
    claimed, retail, unspec, rnotes = residual.claimed_specified(sources.pcl_2024())
    res_shares, res_notes = residual.residual_mix(supply, claimed)
    info += rnotes
    warn += [f"Residual mix: {n}" for n in res_notes]
    resid = {
        "label_year": ly,
        "method": "California supply (EIA-923 plants in California balancing authorities + imports traced with EIA-930) "
                  "minus all specified power claimed on the CEC Power Content Labels; annual, statewide approximation.",
        "note": "Estimate of what untraceable 'unspecified' market power is made of. Not reported by any utility.",
        "supply_mwh": {k: round(v) for k, v in supply.items()},
        "claimed_mwh": {k: round(v) for k, v in claimed.items()},
        "retail_sales_mwh": round(retail),
        "unspecified_mwh": round(unspec),
        "shares": {k: round(v, 5) for k, v in res_shares.items()},
        "sources": [SOURCES["labels"], SOURCES["generation"], SOURCES["flows"]],
    }

    # ---- Boundaries ----
    gj = json.loads(sources.hifld_iso_boundaries().read_text(encoding="utf-8"))
    for f in gj["features"]:
        f["properties"]["iso"] = HIFLD_NAMES.get(f["properties"].get("NAME"))
    unknown = [f["properties"].get("NAME") for f in gj["features"] if not f["properties"]["iso"]]
    if unknown:
        warn.append(f"Boundary names not recognised: {unknown}")

    # ---- Regions without an ISO: groups of balancing authorities ----
    gdata, gutils, gshapes = groups.build(rows, plants, gj["features"], warn, info)

    built = datetime.now(timezone.utc).isoformat()
    store.put_json(f"{PREFIX}/regions.json", {"year": y, "built_utc": built, "sources": SOURCES, "notes": NOTES, "regions": regions}, "public, max-age=86400")
    store.put_json(f"{PREFIX}/utilities.json", {"year": y, "built_utc": built, "source": SOURCES["customers_price"], "utilities": utils}, "public, max-age=86400")
    store.put_json(f"{PREFIX}/residual.json", resid, "public, max-age=86400")
    store.put_json(f"{PREFIX}/boundaries.geojson", gj, "public, max-age=86400")
    store.put_json(f"{PREFIX}/groups.json", {"year": y, "built_utc": built, "sources": SOURCES, "notes": groups.NOTES,
                                             "excluded": groups.EXCLUDED, "groups": gdata, "utilities": gutils}, "public, max-age=86400")
    store.put_json(f"{PREFIX}/groups.geojson", {"type": "FeatureCollection", "features": gshapes}, "public, max-age=86400")

    with open(a.checks_file, "w", encoding="utf-8") as fh:
        fh.write(f"## US ISO build {y} (labels {ly}): {'warnings' if warn else 'passed'}\n\n")
        for w in warn:
            fh.write(f"- [WARNING] {w}\n")
        for i in info:
            fh.write(f"- {i}\n")
    print(open(a.checks_file, encoding="utf-8").read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
