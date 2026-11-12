"""Tests for the US ISO calculations, using small made-up inputs (never published)."""

import numpy as np

from us_iso import eia861, eia930, residual


def row(uid, part, ba, cust, mwh, rev, name="U", state="CA", owner="Investor Owned"):
    r = [2025, uid, name, part, "", "O", state, owner, ba] + [None] * 12 + [rev, mwh, cust]
    return tuple(r)


def test_eia861_parts_count_each_customer_once():
    rows = [
        row(1, "A", "CISO", 100, 1000, 300),  # bundled
        row(1, "C", "CISO", 200, 2000, 200),  # delivery-only (wires utility)
        row(2, "B", "CISO", 200, 2000, 250),  # energy-only (CCA) = same customers as C
        row(3, "D", "ERCO", 50, 500, 60, state="TX"),  # Texas retail provider
    ]
    t, notes = eia861.iso_totals(rows)
    assert t["CAISO"]["customers"] == 300             # A + C, not + B
    assert t["CAISO"]["retail_mwh"] == 3000
    assert t["CAISO"]["avg_price_cents_kwh"] == round((300 + 200 + 250) / 3000 * 100, 2)  # revenue A+B+C
    assert t["ERCOT"]["customers"] == 50
    assert notes == []


def test_eia861_withheld_cells_are_missing_not_zero():
    rows = [row(1, "A", "CISO", ".", 1000, 300)]
    t, notes = eia861.iso_totals(rows)
    assert t["CAISO"]["customers"] == 0 and "withheld" in notes[0]


def test_flow_tracing_follows_power_through_an_intermediate_grid():
    # A (all hydro) exports 100 MW to B; B (all gas, 100 MW) exports 100 MW to TARGET.
    # B's power is half hydro, half gas, so TARGET's import should be 50/50.
    t = "01/01/2025 1:00:00 AM"
    gen = {
        ("A", t): np.eye(len(eia930.FUELS))[eia930.FI["hydro"]] * 100,
        ("B", t): np.eye(len(eia930.FUELS))[eia930.FI["gas"]] * 100,
        ("T", t): np.zeros(len(eia930.FUELS)),
    }
    flows = {t: {("A", "B"): 100.0, ("B", "T"): 100.0}}
    region = {"A": "NW", "B": "CAL", "T": "CAL"}
    mix, src, hours = eia930.traced_imports(gen, flows, region, {"T"})
    assert hours == 1
    assert abs(mix["hydro"] - 50) < 1e-6 and abs(mix["gas"] - 50) < 1e-6
    assert src == {"B": 100.0}


def test_flows_from_outside_the_traced_area_are_unattributed():
    t = "01/01/2025 1:00:00 AM"
    gen = {("T", t): np.zeros(len(eia930.FUELS))}
    flows = {t: {("CANADA", "T"): 40.0}}
    mix, _, _ = eia930.traced_imports(gen, flows, {"T": "CAL", "CANADA": "CAN"}, {"T"})
    assert mix["unattributed"] == 40.0


def test_residual_mix_subtracts_claims_and_never_goes_negative():
    supply = {c: 0.0 for c in residual.CATEGORIES}
    supply.update(gas=100.0, solar=100.0, hydro=50.0)
    claimed = {c: 0.0 for c in residual.CATEGORIES}
    claimed.update(solar=90.0, hydro=60.0)  # hydro over-claimed
    shares, notes = residual.residual_mix(supply, claimed)
    assert abs(shares["gas"] - 100 / 110) < 1e-9 and abs(shares["solar"] - 10 / 110) < 1e-9
    assert shares["hydro"] == 0 and "hydro" in notes[0]


def test_groups_are_disjoint_and_named():
    from us_iso import eia861, groups
    seen = {}
    for g, v in groups.GROUPS.items():
        for ba in v["bas"]:
            assert ba not in seen, f"{ba} in both {seen.get(ba)} and {g}"
            assert ba not in eia861.ISO_BY_BA, f"{ba} is an ISO"
            assert ba not in groups.EXCLUDED
            assert ba in groups.BA_NAMES
            seen[ba] = g


def test_hifld_names_map_to_group_bas():
    from us_iso import groups
    assert groups.hifld_code("TENNESSEE VALLEY AUTHORITY") == "TVA"
    assert groups.hifld_code("PACIFICORP - EAST") == "PACE"
    assert groups.hifld_code("POWERSOUTH ENERGY COOPERATIVE") == "_SOUTHEAST"
    assert groups.hifld_code("SOUTHWEST POWER POOL") is None  # ISOs come from their own layer
    for code in groups.HIFLD_PREFIX.values():
        assert code.startswith("_") and code[1:] in groups.GROUPS or code in groups.GROUP_OF


def test_california_outside_caiso_covers_all_cec_bas():
    # The CEC lists 8 BAs in California; every one except CAISO must be in "California outside CAISO".
    from us_iso import groups
    ca = set(groups.GROUPS["CA-OTHER"]["bas"])
    assert ca == {"LDWP", "BANC", "IID", "TIDC", "PACW-CA", "NEVP-CA", "WALC-CA"}
    assert groups.CEC_NON_CAISO == {"BANC", "IID", "LADWP", "NV Energy", "TID", "WALC", "PacificCorp West"}


def test_ba_corrections_and_california_split():
    from us_iso import groups
    assert groups.corrected_ba(57483, "CA", "CISO") == "NEVP-CA"   # Liberty (Lake Tahoe): NV Energy BA
    assert groups.corrected_ba(57483, "NH", "ISNE") == "ISNE"      # other Liberty companies untouched
    assert groups.corrected_ba(19840, "NV", "NEVP") == "CISO"      # Valley Electric: CAISO since 2013
    assert groups.corrected_ba(14354, "CA", "PACW") == "PACW-CA"   # PacifiCorp's California part
    assert groups.corrected_ba(14354, "OR", "PACW") == "PACW"
    assert groups.corrected_ba(16534, "CA", "BANC") == "BANC"      # SMUD


def test_short_form_rows_use_long_layout():
    from us_iso import eia861
    assert (eia861.C_ID, eia861.C_STATE, eia861.C_BA, eia861.C_CUST) == (1, 6, 8, 23)


def test_merge_split_adds_california_part_back():
    from us_iso import eia923
    merged = eia923.merge_split({"PACW": {"wind": 5.0}, "PACW-CA": {"wind": 1.0, "hydro": 2.0}})
    assert merged == {"PACW": {"wind": 6.0, "hydro": 2.0}}


def test_iso_overlaps_pairs_and_slivers():
    from us_iso import groups
    sq = lambda x0, y0, x1, y1: {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}
    feats = [
        {"properties": {"iso": "SPP"}, "geometry": sq(-100, 30, -96, 34)},
        {"properties": {"iso": "ERCOT"}, "geometry": sq(-98, 28, -94, 32)},       # overlaps SPP by 2x2 degrees
        {"properties": {"iso": "MISO"}, "geometry": sq(-96.0005, 33, -92, 36)},  # touches SPP: sliver only
    ]
    out = groups.iso_overlaps(feats)
    assert [o["properties"]["isos"] for o in out] == [["ERCOT", "SPP"]]
    assert out[0]["properties"]["area_km2"] > 40000


def test_rings_to_shape_keeps_arcgis_holes():
    from shapely.geometry import Point
    from us_iso import groups
    cw = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]       # area (clockwise)
    ccw = [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]]          # hole (counter-clockwise), sent as its own polygon
    island = [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]]       # area inside the hole (clockwise)
    g = groups.rings_to_shape({"type": "MultiPolygon", "coordinates": [[cw], [ccw], [island]]})
    assert g.contains(Point(1, 1)) and not g.contains(Point(3, 3)) and g.contains(Point(5, 5))
    assert abs(g.area - (100 - 36 + 4)) < 1e-6
