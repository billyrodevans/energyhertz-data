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
    "CA-OTHER": {"name": "California outside CAISO", "bas": ["LDWP", "BANC", "IID", "TIDC", "PACW-CA", "NEVP-CA", "WALC-CA"]},
    "FLORIDA": {"name": "Florida", "bas": ["FPL", "FPC", "TEC", "SEC", "FMPP", "JEA", "TAL", "GVL", "HST"]},
    "SOUTHEAST": {"name": "Southeast", "bas": ["SOCO", "TVA", "DUK", "CPLE", "CPLW", "SC", "SCEG", "LGEE", "SEPA", "YAD"]},
    "CENTRAL": {"name": "Central (AECI, SPA)", "bas": ["AECI", "SPA"]},
    "SOUTHWEST": {"name": "Desert Southwest", "bas": ["AZPS", "SRP", "TEPC", "PNM", "EPE", "WALC", "NEVP", "DEAA", "GRIF", "GRIS"]},
    "ROCKIES": {"name": "Rocky Mountains", "bas": ["PSCO", "PACE", "WACM", "WAUW"]},
    "NORTHWEST": {"name": "Northwest", "bas": ["BPAT", "PACW", "PSEI", "PGE", "SCL", "TPWR", "AVA", "GCPD", "CHPD", "DOPD", "IPCO", "NWMT", "GWA", "WWA", "GRID", "AVRN"]},
}
GROUP_ORDER = list(GROUPS)

# BAs that reach into California from a neighboring state. Their California rows (EIA-861 by state,
# EIA-923 by plant state) are keyed "<BA>-CA" and belong to "California outside CAISO"; the rest of
# each BA stays in its own group. The California Energy Commission lists 8 BAs in California:
# CAISO, BANC, LADWP, IID, TID, PacifiCorp West, NV Energy and WALC (Balancing Authority Areas map).
SPLIT_CA = {"PACW", "NEVP", "WALC"}

# Corrections to the BA a utility reports on EIA-861, each with its primary source (shown on the page).
# Keyed by EIA utility number; "state" limits the correction to one state (None = all states).
BA_CORRECTIONS = {
    57483: {"name": "Liberty Utilities (CalPeco)", "state": "CA", "ba": "NEVP",
            "reason": "EIA-861 reports CAISO, but Liberty's California territory is in NV Energy's balancing authority "
                      "area, not CAISO's (CPUC filings; CEC Balancing Authority Areas map)."},
    19840: {"name": "Valley Electric Association", "state": None, "ba": "CISO",
            "reason": "EIA-861 reports NV Energy, but VEA joined the CAISO balancing authority area as a participating "
                      "transmission owner in 2013 (CAISO); CAISO publishes a VEA price area."},
    694: {"name": "Anza Electric Cooperative", "state": "CA", "ba": "CISO",
          "reason": "EIA-861 short form reports WALC, but the CEC Balancing Authority Areas map places Anza's territory "
                    "in CAISO, and EIA's plant record for the Anza solar plant on its lines reports CAISO."},
}


def corrected_ba(uid, state, ba):
    """BA code after BA_CORRECTIONS, then "-CA" for the California part of SPLIT_CA BAs."""
    c = BA_CORRECTIONS.get(uid)
    if c and (c["state"] is None or c["state"] == state):
        ba = c["ba"]
    if ba in SPLIT_CA and state == "CA":
        ba = f"{ba}-CA"
    return ba


def corrected_rows(rows):
    """EIA-861 rows (long layout) with the BA column corrected (see corrected_ba)."""
    from .eia861 import C_BA, C_ID, C_STATE
    out = []
    for r in rows:
        ba = corrected_ba(r[C_ID], r[C_STATE], r[C_BA])
        out.append(r if ba == r[C_BA] else r[:C_BA] + (ba,) + r[C_BA + 1:])
    return out
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
    "NEVP": "NV Energy", "DEAA": "Arlington Valley", "GRIF": "Griffith Energy",
    "GRIS": "Gridforce South",
    "PSCO": "Public Service Co. of Colorado (Xcel)", "PACE": "PacifiCorp East", "WACM": "WAPA Rocky Mountain",
    "WAUW": "WAPA Upper Great Plains West",
    "BPAT": "Bonneville Power Administration", "PACW": "PacifiCorp West", "PSEI": "Puget Sound Energy",
    "PGE": "Portland General Electric", "SCL": "Seattle City Light", "TPWR": "Tacoma Power", "AVA": "Avista",
    "GCPD": "Grant County PUD", "CHPD": "Chelan County PUD", "DOPD": "Douglas County PUD",
    "IPCO": "Idaho Power", "NWMT": "NorthWestern Energy (Montana)", "GWA": "NaturEner Power Watch",
    "WWA": "NaturEner Wind Watch", "GRID": "Gridforce Energy Management", "AVRN": "Avangrid Renewables",
    "PACW-CA": "PacifiCorp West (California part)", "NEVP-CA": "NV Energy (California part)",
    "WALC-CA": "WAPA Desert Southwest (California part)",
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


# ---- California outlines: California Energy Commission (CEC) layers ----
# HIFLD's CAISO outline covers nearly all of California, so inside California the CEC layers are used.
# CEC "Balancing Authority Areas": BANC, CALISO, IID, LADWP, NV Energy, TID, WALC, PacificCorp West.
CEC_NON_CAISO = {"BANC", "IID", "LADWP", "NV Energy", "TID", "WALC", "PacificCorp West"}
# Utilities listed under "California outside CAISO" (EIA-861 name -> CEC service-area name). Their
# CEC service areas are added to the outline so every listed utility is highlighted on the map.
CA_OTHER_UTILITY_AREAS = {
    "Los Angeles Department of Water & Power": "Los Angeles Department of Water & Power",
    "City of Burbank Water and Power - (CA)": "Burbank Water & Power",
    "City of Glendale - (CA)": "Glendale Water & Power",
    "Sacramento Municipal Util Dist": "Sacramento Municipal Utility District",
    "Modesto Irrigation District": "Modesto Irrigation District",
    "City of Roseville - (CA)": "Roseville Electric",
    "City of Redding - (CA)": "Redding Electric Utility",
    "City of Shasta Lake - (CA)": "City of Shasta Lake",
    "Trinity Public Utilities Dist": "Trinity Public Utilities District",
    "Imperial Irrigation District": "Imperial Irrigation District",
    "Turlock Irrigation District": "Turlock Irrigation District",
    "PacifiCorp": "PacifiCorp",
    "Surprise Valley Electrification": "Surprise Valley Electrification Corporation",
    "Truckee Donner P U D": "Truckee Donner Public Utilities District",
    "Liberty Utilities": "Liberty Utilities",
    "City of Needles - (CA)": "City of Needles",
    "Aha Macav Power Service": "Aha Macav Power Service",
}
# Listed, but not drawn: the CEC area for WAPA covers federal customers across the state (74% inside
# CAISO's area), which doesn't match the WALC code EIA-861 reports for its California customers.
CA_OTHER_NOT_DRAWN = {
    "WAPA-- Western Area Power Administration":
        "WAPA's California retail customers are reported under WALC (EIA-861), but its CEC service area lies "
        "mostly in CAISO's area; listed without a highlighted area.",
    "Colorado River Indian Irr Proj":
        "Bureau of Indian Affairs utility on the Colorado River Indian Reservation (Arizona and California), reported "
        "under WALC; the CEC has no service-area map for it, so it has no highlighted area of its own.",
}
# Areas inside a non-CAISO CEC polygon that are in CAISO: cut out of "California outside CAISO".
CEC_TO_CAISO = {
    "Merced Irrigation District": "Left TID's balancing authority area to join CAISO's (CAISO 2013 transition "
                                  "agreement); EIA-861 reports CAISO.",
}


def rings_to_shape(geometry: dict):
    """Shapely geometry from an ArcGIS-served GeoJSON (multi)polygon, keeping its holes.

    The HIFLD servers return every ring as its own polygon, with no inner rings: areas are clockwise
    and holes counter-clockwise (ArcGIS's convention). Merging all parts (as before 2026-11-12) filled
    the holes, e.g. ~47,000 km2 of Nebraska inside SPP that HIFLD shows as outside it. Here a
    counter-clockwise ring that lies inside the area built so far is cut out as a hole; any other ring
    is added. Largest rings go first, so an island inside a hole is added back after the hole is cut.
    Polygons that already carry inner rings are taken as they are."""
    from shapely.geometry import LinearRing, Polygon
    from shapely.ops import unary_union
    if not geometry:
        return Polygon()
    parts = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    rings = []
    for p in parts:
        if len(p[0]) < 4:
            continue
        poly = Polygon(p[0], [r for r in p[1:] if len(r) > 3]).buffer(0)
        hole = len(p) == 1 and LinearRing(p[0]).is_ccw
        rings.append((poly.area, hole, poly))
    out = Polygon()
    for _, hole, poly in sorted(rings, key=lambda r: -r[0]):
        if hole and out.buffer(1e-9).contains(poly):
            out = out.difference(poly)
        else:
            out = unary_union([out, poly])
    return _polygonal(out)


def _features_by(features, key):
    from shapely.ops import unary_union
    out = {}
    for f in features:
        out.setdefault(f["properties"].get(key), []).append(rings_to_shape(f["geometry"]))
    return {k: unary_union(v) for k, v in out.items()}


def group_shapes(features: list[dict], iso_features: list[dict], cec_ba: list[dict], cec_utils: list[dict],
                 simplify: float = 0.01) -> tuple[list[dict], list[str], dict]:
    """One (multi)polygon per group, plus notes and the California shapes (for the utility check).

    California: "California outside CAISO" = CEC non-CAISO BA areas + CEC service areas of the utilities
    listed there, minus CEC_TO_CAISO areas. CAISO's outline inside California becomes the rest of the
    state (iso_features are changed in place); outside California it stays HIFLD's.
    Elsewhere: union of member BA areas (HIFLD Control Areas) minus ISO areas, California and earlier groups."""
    from shapely.geometry import MultiPolygon, mapping, shape
    from shapely.ops import unary_union

    notes = []
    ba_polys = _features_by(cec_ba, "NAME")
    util_polys = _features_by(cec_utils, "Utility")
    missing = CEC_NON_CAISO - set(ba_polys)
    if missing:
        notes.append(f"CEC BA layer is missing {sorted(missing)}")
    california = unary_union(list(ba_polys.values()))
    for name in CA_OTHER_UTILITY_AREAS.values():
        if name not in util_polys:
            notes.append(f"CEC service area {name!r} not found (utility listed, area not drawn)")
    ca_other = unary_union([ba_polys[n] for n in CEC_NON_CAISO if n in ba_polys]
                           + [util_polys[n] for n in CA_OTHER_UTILITY_AREAS.values() if n in util_polys])
    to_caiso = unary_union([util_polys[n] for n in CEC_TO_CAISO if n in util_polys])
    ca_other = _polygonal(ca_other.difference(to_caiso).intersection(california))
    caiso_ca = _polygonal(california.difference(ca_other))

    for f in iso_features:
        g0 = shape(f["geometry"]).buffer(0)
        if f["properties"].get("iso") == "CAISO":
            f["geometry"] = _round(mapping(_polygonal(g0.difference(california).union(caiso_ca).simplify(simplify / 2))))
            notes.append("CAISO outline: inside California from the CEC Balancing Authority Areas layer "
                         "(state area minus the non-CAISO areas); outside California from HIFLD")
        elif g0.intersection(california).area > 0.0025:
            f["geometry"] = _round(mapping(_polygonal(g0.difference(california))))
            notes.append(f"ISO outline {f['properties'].get('iso')}: California part removed")
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
        members[g].append(rings_to_shape(f["geometry"]))
    taken = unary_union([iso, california])
    out = []
    for g in GROUP_ORDER:
        if g == "CA-OTHER":
            geom, tol, keep = ca_other, simplify / 4, 0.0002  # keep small California districts (~2 km2 and up)
        elif not members[g]:
            notes.append(f"Group {g}: no boundary polygons found")
            continue
        else:
            geom = unary_union(members[g]).difference(taken)
            taken = unary_union([taken, geom])
            tol, keep = simplify, 0.0025  # drop slivers left by overlapping outlines (< ~25 km2)
        geom = _polygonal(geom.simplify(tol, preserve_topology=True))
        if geom.geom_type == "MultiPolygon":
            geom = MultiPolygon([p for p in geom.geoms if p.area > keep])
        out.append({"type": "Feature", "properties": {"group": g, "name": GROUPS[g]["name"]},
                    "geometry": _round(mapping(geom))})
    for g in GROUP_ORDER:
        if g == "CA-OTHER":
            continue  # California outlines come from the CEC layers
        for ba in GROUPS[g]["bas"]:
            if not any(hifld_code(f["properties"].get("NAME", "")) == ba for f in features):
                notes.append(f"{ba} ({g}) has no HIFLD control-area polygon; its figures are included, its area is not drawn")
    return out, notes, {"ca_other": ca_other, "caiso_ca": caiso_ca, "utils": util_polys}


def check_ca_utilities(rows, shapes, warn, info):
    """Every utility listed under "California outside CAISO" must sit inside its highlighted area."""
    from .eia861 import C_BA, C_CUST, C_NAME, C_OWNER, C_PART, C_STATE
    listed, owner = {}, {}
    for r in rows:
        if (r[C_STATE] == "CA" and GROUP_OF.get(r[C_BA]) == "CA-OTHER" and r[C_PART] != "B"
                and isinstance(r[C_CUST], (int, float)) and r[C_CUST] > 0):
            listed[r[C_NAME]] = listed.get(r[C_NAME], 0) + r[C_CUST]
            owner[r[C_NAME]] = r[C_OWNER]
    utils, ca_other = shapes["utils"], shapes["ca_other"]
    for name, cust in sorted(listed.items(), key=lambda x: -x[1]):
        if name in CA_OTHER_NOT_DRAWN:
            info.append(f"California outside CAISO: {name} ({cust:,.0f} accounts) listed, not drawn: {CA_OTHER_NOT_DRAWN[name]}")
            continue
        area = CA_OTHER_UTILITY_AREAS.get(name)
        if area is None:
            if owner.get(name) == "Behind the Meter" or str(name).startswith("Adjustment"):
                # rooftop-solar sellers and EIA's adjustment rows have no service territory
                info.append(f"California outside CAISO: {name} ({cust:,.0f} accounts): {owner.get(name) or 'EIA adjustment'}, no territory")
            else:
                warn.append(f"California outside CAISO: {name} ({cust:,.0f} accounts) is a utility with no mapped service area")
            continue
        g = utils.get(area)
        inside = g.intersection(ca_other).area / g.area if g is not None and g.area else 0
        (info if inside > 0.95 else warn).append(
            f"California outside CAISO: {name} ({cust:,.0f} accounts): {inside:.0%} of its CEC service area highlighted")
    for name, why in CEC_TO_CAISO.items():
        g = utils.get(name)
        if g is not None:
            info.append(f"{name}: {g.intersection(ca_other).area / g.area:.0%} inside the highlighted area after correction ({why})")


def _polygonal(geom):
    """Keep only the polygon parts (intersections can add stray lines or points)."""
    from shapely.geometry import MultiPolygon, Polygon
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    parts = []
    for g in getattr(geom, "geoms", []):
        g = _polygonal(g)
        parts += list(g.geoms) if isinstance(g, MultiPolygon) else [g] if isinstance(g, Polygon) else []
    return MultiPolygon(parts)


def _round(geom: dict, nd: int = 3) -> dict:
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


def iso_overlaps(iso_features: list[dict], min_km2: float = 100, simplify: float = 0.01) -> list[dict]:
    """Areas where two ISO/RTO outlines overlap, one GeoJSON feature per pair.

    HIFLD builds each ISO outline from its members' service territories, which EIA-861 reports by county,
    so a county served by members of two ISOs falls inside both outlines. The overlap is often real
    (members' territories are interleaved), so it is shown as such rather than given to one ISO.
    """
    import math
    from shapely.geometry import mapping, shape
    shapes = [(f["properties"].get("iso"), shape(f["geometry"]).buffer(0)) for f in iso_features if f["properties"].get("iso")]
    out = []
    for i, (a, ga) in enumerate(shapes):
        for b, gb in shapes[i + 1:]:
            x = _polygonal(ga.intersection(gb))
            if x.is_empty:
                continue
            km2 = x.area * 111.32 ** 2 * math.cos(math.radians(x.centroid.y))
            if km2 < min_km2:  # slivers where simplified borders touch
                continue
            x = _polygonal(x.simplify(simplify, preserve_topology=True))
            out.append({"type": "Feature", "properties": {"isos": sorted([a, b]), "area_km2": round(km2, -2)},
                        "geometry": _round(mapping(x))})
    return out


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
    "california": "California outside CAISO includes every California balancing authority other than CAISO (the "
                  "California Energy Commission lists 8 in the state): BANC, LADWP, IID and TID, plus the California "
                  "parts of PacifiCorp West, NV Energy and WAPA Desert Southwest. California outlines are from the "
                  "California Energy Commission (balancing authority areas and utility service areas).",
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

    def cec(kind):
        return json.loads(sources.cec_layer(kind).read_text(encoding="utf-8"))["features"]

    shapes, snotes, ca_shapes = group_shapes(ca["features"], iso_features, cec("ba"), cec("utilities") + cec("utilities_other"))
    info += snotes
    check_ca_utilities(rows, ca_shapes, warn, info)
    for c in BA_CORRECTIONS.values():
        info.append(f"BA correction: {c['name']} -> {c['ba']}: {c['reason']}")
    return out, gutils, shapes
