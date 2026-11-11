"""Regions without an ISO/RTO: groups of balancing authorities (BAs), for display only.

A balancing authority keeps supply and demand matched in its area; it is not a market.
These groups are this project's own grouping by geography (not official regions). Every
figure for a group is the sum of its member BAs:
  - customers, retail MWh and revenue: EIA-861, by the BA code each utility reports
  - generation: EIA-923, by the BA code of each power plant

Boundaries: HIFLD "Control Areas" (approximate; source dates 2018-2021). BA areas overlap and
can be non-contiguous, so each group's outline is the union of its members' areas with the
ISO/RTO areas and earlier groups removed.
"""

from __future__ import annotations

# Group id -> display name and member BA codes (EIA codes, as used in EIA-861 / EIA-923 / EIA-930).
GROUPS: dict[str, dict] = {
    "CA-OTHER": {"name": "California outside CAISO", "bas": ["LDWP", "BANC", "IID", "TIDC"]},
    "FLORIDA": {"name": "Florida", "bas": ["FPL", "FPC", "TEC", "SEC", "FMPP", "JEA", "TAL", "GVL", "HST"]},
    "SOUTHEAST": {"name": "Southeast", "bas": ["SOCO", "TVA", "DUK", "CPLE", "CPLW", "SC", "SCEG", "LGEE", "SEPA", "YAD"]},
    "CENTRAL": {"name": "Central (AECI, SPA)", "bas": ["AECI", "SPA"]},
    "SOUTHWEST": {"name": "Desert Southwest", "bas": ["AZPS", "SRP", "TEPC", "PNM", "EPE", "WALC", "NEVP", "DEAA", "GRIF", "GRIS"]},
    "ROCKIES": {"name": "Rocky Mountains", "bas": ["PSCO", "PACE", "WACM", "WAUW"]},
    "NORTHWEST": {"name": "Northwest", "bas": ["BPAT", "PACW", "PSEI", "PGE", "SCL", "TPWR", "AVA", "GCPD", "CHPD", "DOPD", "IPCO", "NWMT", "GWA", "WWA", "GRID", "AVRN"]},
}
GROUP_ORDER = list(GROUPS)
GROUP_OF = {ba: g for g, v in GROUPS.items() for ba in v["bas"]}

# BA codes deliberately left out of every region, with the reason (shown in the checks and on the page).
EXCLUDED = {
    "HECO": "Hawaii (island grid; most Hawaii and Alaska plants have no BA code in EIA-923)",
    "CEA": "Alaska (island grid)",
    "AMPL": "Alaska (island grid)",
    "NA": "No BA reported (mostly Alaska and Hawaii)",
    "": "No BA reported (mostly Alaska and Hawaii)",
    "None": "No BA reported",
    "State-Fuel Level Increment": "EIA-923 state-level estimate for small plants, not assigned to any BA",
    "NBSO": "Northern Maine, served through New Brunswick's system operator (its area is mostly in Canada)",
}

# Short names for each BA code.
BA_NAMES = {
    "LDWP": "Los Angeles Dept. of Water and Power", "BANC": "Balancing Authority of Northern California",
    "IID": "Imperial Irrigation District", "TIDC": "Turlock Irrigation District",
    "FPL": "Florida Power & Light", "FPC": "Duke Energy Florida", "TEC": "Tampa Electric",
    "SEC": "Seminole Electric Cooperative", "FMPP": "Florida Municipal Power Pool", "JEA": "JEA",
    "TAL": "City of Tallahassee", "GVL": "Gainesville Regional Utilities", "HST": "City of Homestead",
    "SOCO": "Southern Company Services", "TVA": "Tennessee Valley Authority", "DUK": "Duke Energy Carolinas",
    "CPLE": "Duke Energy Progress East", "CPLW": "Duke Energy Progress West", "SC": "Santee Cooper",
    "SCEG": "Dominion Energy South Carolina", "LGEE": "LG&E and KU", "SEPA": "Southeastern Power Administration",
    "YAD": "Alcoa Power Generating (Yadkin)",
    "AECI": "Associated Electric Cooperative", "SPA": "Southwestern Power Administration",
    "AZPS": "Arizona Public Service", "SRP": "Salt River Project", "TEPC": "Tucson Electric Power",
    "PNM": "Public Service Co. of New Mexico", "EPE": "El Paso Electric", "WALC": "WAPA Desert Southwest",
    "NEVP": "Nevada Power (NV Energy)", "DEAA": "Arlington Valley", "GRIF": "Griffith Energy",
    "GRIS": "Gridforce South",
    "PSCO": "Public Service Co. of Colorado (Xcel)", "PACE": "PacifiCorp East", "WACM": "WAPA Rocky Mountain",
    "WAUW": "WAPA Upper Great Plains West",
    "BPAT": "Bonneville Power Administration", "PACW": "PacifiCorp West", "PSEI": "Puget Sound Energy",
    "PGE": "Portland General Electric", "SCL": "Seattle City Light", "TPWR": "Tacoma Power", "AVA": "Avista",
    "GCPD": "Grant County PUD", "CHPD": "Chelan County PUD", "DOPD": "Douglas County PUD",
    "IPCO": "Idaho Power", "NWMT": "NorthWestern Energy (Montana)", "GWA": "NaturEner Power Watch",
    "WWA": "NaturEner Wind Watch", "GRID": "Gridforce Energy Management", "AVRN": "Avangrid Renewables",
}

# Facts shown on a BA row (checked against primary sources).
BA_FLAGS = {
    "WACM": "Joined SPP's RTO on April 1, 2026 (now part of SPP West); figures are for the data year.",
    "WAUW": "Joined SPP's RTO on April 1, 2026 (now part of SPP West); figures are for the data year.",
}

# HIFLD Control Areas NAME (prefix) -> BA code. Polygons whose BA no longer exists are kept in the
# group outline where the area is still outside any ISO (PowerSouth, New Smyrna Beach, Harquahala, Gila River).
HIFLD_PREFIX = {
    "ALCOA POWER GENERATING": "YAD", "ARIZONA PUBLIC SERVICE": "AZPS", "ARLINGTON VALLEY": "DEAA",
    "ASSOCIATED ELECTRIC": "AECI", "AVANGRID": "AVRN", "AVISTA": "AVA",
    "BALANCING AUTHORITY OF NORTHERN CALIFORNIA": "BANC", "BONNEVILLE": "BPAT", "CITY OF HOMESTEAD": "HST",
    "CITY OF TACOMA": "TPWR", "CITY OF TALLAHASSEE": "TAL", "DUKE ENERGY CAROLINAS": "DUK",
    "DUKE ENERGY FLORIDA": "FPC", "DUKE ENERGY PROGRESS EAST": "CPLE", "DUKE ENERGY PROGRESS WEST": "CPLW",
    "EL PASO ELECTRIC": "EPE", "FLORIDA MUNICIPAL POWER POOL": "FMPP", "FLORIDA POWER & LIGHT": "FPL",
    "GAINESVILLE": "GVL", "GILA RIVER": "_SOUTHWEST", "GRIDFORCE ENERGY MANAGEMENT": "GRID", "GRIDFORCE SOUTH": "GRIS",
    "GRIFFITH": "GRIF", "IDAHO POWER": "IPCO", "IMPERIAL IRRIGATION": "IID", "JEA": "JEA",
    "LOS ANGELES DEPARTMENT": "LDWP", "LOUISVILLE GAS": "LGEE", "NATURENER POWER WATCH": "GWA",
    "NATURENER WIND WATCH": "WWA", "NEVADA POWER": "NEVP", "NEW HARQUAHALA": "_SOUTHWEST", "NEW SMYRNA BEACH": "_FLORIDA",
    "NORTHWESTERN ENERGY": "NWMT", "PACIFICORP - EAST": "PACE", "PACIFICORP - WEST": "PACW",
    "PORTLAND GENERAL": "PGE", "PUBLIC SERVICE COMPANY OF COLORADO": "PSCO",
    "PUBLIC SERVICE COMPANY OF NEW MEXICO": "PNM", "PUBLIC UTILITY DISTRICT NO. 1 OF CHELAN": "CHPD",
    "PUBLIC UTILITY DISTRICT NO. 2 OF GRANT": "GCPD", "PUD NO. 1 OF DOUGLAS": "DOPD", "PUGET SOUND": "PSEI",
    "SALT RIVER": "SRP", "SEATTLE CITY LIGHT": "SCL", "SEMINOLE": "SEC", "SOUTH CAROLINA ELECTRIC & GAS": "SCEG",
    "SOUTH CAROLINA PUBLIC SERVICE": "SC", "SOUTHEASTERN POWER ADMINISTRATION": "SEPA",
    "SOUTHERN COMPANY": "SOCO", "SOUTHWESTERN POWER ADMINISTRATION": "SPA", "TAMPA ELECTRIC": "TEC",
    "TENNESSEE VALLEY": "TVA", "TUCSON ELECTRIC": "TEPC", "TURLOCK": "TIDC",
    "WESTERN AREA POWER ADMINISTRATION - DESERT": "WALC", "WESTERN AREA POWER ADMINISTRATION - ROCKY": "WACM",
    "WESTERN AREA POWER ADMINISTRATION UGP WEST": "WAUW",
    "POWERSOUTH": "_SOUTHEAST",  # former BAs: areas drawn with their group, no figures of their own
}


def hifld_code(name: str) -> str | None:
    n = (name or "").upper()
    for prefix, code in HIFLD_PREFIX.items():
        if n.startswith(prefix):
            return code
    return None


# HIFLD outlines overlap. Where a BA overlaps an ISO outline, the ISO normally wins: co-op and federal
# BAs (AECI, SPA, WAPA, ...) interleave county by county with ISO utilities. These BAs are compact
# city/district service areas that are known not to be in the ISO drawn over them, so their own
# outline wins and is cut out of the ISO outline (e.g. SMUD, Modesto ID, Roseville and Redding in BANC
# are not CAISO). Checked against PG&E/SCE towns nearby (none fall inside). Not El Paso Electric: its
# HIFLD outline is far too broad (covers ERCOT towns such as Fort Stockton, Alpine and Presidio).
BA_PRIORITY = {"BANC", "TIDC", "LDWP", "IID"}


def group_shapes(features: list[dict], iso_features: list[dict], simplify: float = 0.01) -> tuple[list[dict], list[str]]:
    """One (multi)polygon per group: union of member BA areas, minus ISO areas and earlier groups.

    BA_PRIORITY areas are cut out of the ISO outlines instead (iso_features are changed in place)."""
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    notes = []
    prio = unary_union([shape(f["geometry"]).buffer(0) for f in features
                        if hifld_code(f["properties"].get("NAME", "")) in BA_PRIORITY])
    for f in iso_features:
        g0 = shape(f["geometry"]).buffer(0)
        cut = g0.intersection(prio).area
        if cut > 0.0025:
            f["geometry"] = _round(mapping(g0.difference(prio)))
            notes.append(f"ISO outline {f['properties'].get('iso')}: {cut / g0.area:.1%} of its area cut out for "
                         f"BAs drawn with priority ({', '.join(sorted(BA_PRIORITY))})")
    iso = unary_union([shape(f["geometry"]).buffer(0) for f in iso_features])
    members: dict[str, list] = {g: [] for g in GROUP_ORDER}
    for f in features:
        name = f["properties"].get("NAME", "")
        code = hifld_code(name)
        if code is None:
            continue
        g = code[1:] if code.startswith("_") else GROUP_OF.get(code)
        if g is None:
            notes.append(f"Control area {name!r} ({code}) is not in any group")
            continue
        members[g].append(shape(f["geometry"]).buffer(0))
    taken = iso
    out = []
    for g in GROUP_ORDER:
        if not members[g]:
            notes.append(f"Group {g}: no boundary polygons found")
            continue
        geom = unary_union(members[g]).difference(taken)
        taken = unary_union([taken, geom])
        geom = geom.simplify(simplify, preserve_topology=True)
        # drop slivers left by overlapping outlines (< ~25 km2)
        if geom.geom_type == "MultiPolygon":
            from shapely.geometry import MultiPolygon
            geom = MultiPolygon([p for p in geom.geoms if p.area > 0.0025])
        out.append({"type": "Feature", "properties": {"group": g, "name": GROUPS[g]["name"]},
                    "geometry": _round(mapping(geom))})
    for g in GROUP_ORDER:
        for ba in GROUPS[g]["bas"]:
            if not any(hifld_code(f["properties"].get("NAME", "")) == ba for f in features):
                notes.append(f"{ba} ({g}) has no HIFLD control-area polygon; its figures are included, its area is not drawn")
    return out, notes


def _round(geom: dict, nd: int = 3) -> dict:
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


# Short notes published with the data (shown on the page).
NOTES = {
    "what": "Areas outside an ISO/RTO are run by balancing authorities (BAs): utilities or federal power agencies that "
            "keep supply and demand matched in their area. A BA is not a market; retail rates are mostly set by state "
            "commissions (or by public-power boards).",
    "grouping": "Groups are this site's own geographic grouping of BAs for display, not official regions. Each group's "
                "figures are the sum of its member BAs.",
    "assignment": "Customers and sales follow the BA each utility reports to EIA-861; generation follows the BA of each "
                  "power plant (EIA-923). A BA's area can be non-contiguous and overlap others; outlines are approximate.",
    "generation_only": "Some BAs only balance their own power plants and serve no retail customers; they count toward "
                       "generation only.",
}


def build(rows, plants, iso_features, warn, info):
    """Per group: sums of member BAs, the per-BA rows, utilities, and outlines."""
    import json

    from . import eia861, eia923, sources

    per_ba, notes = eia861.iso_totals(rows, {ba: ba for ba in GROUP_OF})
    info += [f"BA totals: {n}" for n in notes]

    # Every BA code in the source files must be in an ISO, a group, or the excluded list.
    known = set(eia861.ISO_BY_BA) | set(GROUP_OF) | set(EXCLUDED)
    seen = {"None" if r[eia861.C_BA] is None else str(r[eia861.C_BA]) for r in rows} | set(map(str, plants))
    for ba in sorted(seen - known):
        warn.append(f"BA code {ba!r} appears in EIA data but is in no ISO, group or exclusion list (left out)")
    for ba, why in EXCLUDED.items():
        c = sum(r[eia861.C_CUST] for r in rows if str(r[eia861.C_BA]) == ba and r[eia861.C_PART] != "B"
                and isinstance(r[eia861.C_CUST], (int, float)))
        g = sum(v for k, v in plants.get(ba, {}).items() if k != "storage" and v > 0)
        if c or g:
            info.append(f"Excluded {ba!r} ({why}): {c:,.0f} customers, {g/1e6:.1f} TWh")

    out = {}
    for gid in GROUP_ORDER:
        bas, gen_sum, n_cust, n_mwh, n_other, revenue = [], {}, 0, 0, 0, 0.0
        for ba in GROUPS[gid]["bas"]:
            t = per_ba.get(ba, {})
            p = plants.get(ba, {})
            _, ren, gen_total = eia923.mix(p)
            if not t and not p:
                info.append(f"{gid}: BA {ba} has no data in EIA-861 or EIA-923 for this year (listed without figures)")
            row = {
                "code": ba,
                "name": BA_NAMES.get(ba, ba),
                "customers": t.get("customers"),
                "avg_price_cents_kwh": t.get("avg_price_cents_kwh"),
                "generation_mwh": round(gen_total) if p else None,
                "renewable_share": round(ren, 4) if gen_total else None,
            }
            if ba in BA_FLAGS:
                row["note"] = BA_FLAGS[ba]
            bas.append(row)
            for k, v in p.items():
                gen_sum[k] = gen_sum.get(k, 0) + v
            n_cust += t.get("customers") or 0
            n_mwh += t.get("retail_mwh") or 0
            n_other += t.get("customers_other_supplier") or 0
            # revenue back from price x MWh (price = revenue / MWh, so this is exact up to rounding)
            if t.get("avg_price_cents_kwh") is not None and t.get("retail_mwh"):
                revenue += t["avg_price_cents_kwh"] * t["retail_mwh"]
        shares, ren, gen_total = eia923.mix(gen_sum)
        price = round(revenue / n_mwh, 2) if n_mwh else None  # MWh-weighted average of member prices
        member_prices = [b["avg_price_cents_kwh"] for b in bas if b["avg_price_cents_kwh"] is not None]
        if price is not None and member_prices and not (min(member_prices) - 0.01 <= price <= max(member_prices) + 0.01):
            warn.append(f"{gid}: group price {price} outside its members' range {min(member_prices)}-{max(member_prices)}")
        if sum(b["customers"] or 0 for b in bas) != n_cust:
            warn.append(f"{gid}: customer sum mismatch")
        out[gid] = {
            "name": GROUPS[gid]["name"],
            "customers": round(n_cust),
            "retail_mwh": round(n_mwh),
            "avg_price_cents_kwh": price,
            "customers_other_supplier": round(n_other),
            "generation_mwh": round(gen_total),
            "mix": shares,
            "renewable_share": round(ren, 4),
            "storage_net_mwh": round(gen_sum.get("storage", 0)),
            "bas": sorted(bas, key=lambda b: (-(b["customers"] or 0), -(b["generation_mwh"] or 0))),
        }
        if shares.get("other", 0) + shares.get("waste", 0) > 0.05:
            warn.append(f"{gid}: 'other' + 'waste' is {shares.get('other', 0) + shares.get('waste', 0):.1%} of the mix")

    gutils = eia861.utilities(rows, GROUP_OF)
    ca = json.loads(sources.hifld_control_areas().read_text(encoding="utf-8"))
    shapes, snotes = group_shapes(ca["features"], iso_features)
    info += snotes
    return out, gutils, shapes
