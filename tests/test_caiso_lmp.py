"""Tests use small made-up inputs. They exist only to check the code and are never published."""

from datetime import datetime, timezone

from caiso_lmp import transform, validate
from caiso_lmp.publish import LocalStore, interval_key, prune_and_index

HEADER = "INTERVALSTARTTIME_GMT,INTERVALENDTIME_GMT,OPR_DT,OPR_HR,NODE_ID_XML,NODE_ID,NODE,MARKET_RUN_ID,LMP_TYPE,XML_DATA_ITEM,PNODE_RESMRID,GRP_TYPE,POS,PRC,OPR_INTERVAL,GROUP\n"
PARTS = {"LMP": 56.47017, "MCE": 42.53711, "MCC": 0.10926, "MCL": -2.01998, "MGHG": 15.84378}


def make_files(parts=PARTS, node="TEST_NODE", start="2026-11-08T03:00:00-00:00", end="2026-11-08T03:15:00-00:00"):
    return {
        f"x_{c}.csv": HEADER + f"{start},{end},2026-11-07,20,{node},{node},{node},RTPD,{c},X,{node},ALL,1,{v},1,1\n"
        for c, v in parts.items()
    }


def test_parse_keeps_values_exactly():
    values, meta, issues = transform.parse_hour(make_files())
    assert issues == []
    v = values["2026-11-08T03:00:00+00:00"]["TEST_NODE"]
    assert v == {"lmp": 56.47017, "energy": 42.53711, "congestion": 0.10926, "loss": -2.01998, "ghg": 15.84378}


def test_component_sum_passes_for_real_values():
    values, meta, _ = transform.parse_hour(make_files())
    start = "2026-11-08T03:00:00+00:00"
    assert validate.check_interval(start, values[start], meta[start]["end"]) == []


def test_component_sum_mismatch_is_an_error():
    bad = dict(PARTS, LMP=60.0)
    values, meta, _ = transform.parse_hour(make_files(bad))
    start = "2026-11-08T03:00:00+00:00"
    issues = validate.check_interval(start, values[start], meta[start]["end"])
    assert any(i.severity == "error" and i.check == "components" for i in issues)


def test_real_large_prices_pass_sum_check():
    # Real CAISO values that failed the old fixed 0.0001 tolerance (2026-11-09 to 11-11).
    cases = [
        {"LMP": 1093.5219, "MCE": 1000, "MCC": -1.37821, "MCL": 94.9, "MGHG": 0},           # diff 0.00011
        {"LMP": -2028.9929, "MCE": 41.06527, "MCC": -2072.7307, "MCL": -10.92759, "MGHG": 13.6},  # diff 0.00012
        {"LMP": 924.457, "MCE": 876.5918, "MCC": -4.73038, "MCL": 52.59551, "MGHG": 0},     # diff 0.00007
    ]
    start = "2026-11-08T03:00:00+00:00"
    for parts in cases:
        values, meta, _ = transform.parse_hour(make_files(parts))
        assert validate.check_interval(start, values[start], meta[start]["end"]) == [], parts


def test_large_price_real_mismatch_still_fails():
    # Off by one cent at $2,000: far beyond rounding, must be blocked.
    bad = {"LMP": -2029.0029, "MCE": 41.06527, "MCC": -2072.7307, "MCL": -10.92759, "MGHG": 13.6}
    values, meta, _ = transform.parse_hour(make_files(bad))
    start = "2026-11-08T03:00:00+00:00"
    issues = validate.check_interval(start, values[start], meta[start]["end"])
    assert any(i.check == "components" and i.severity == "error" for i in issues)


def test_value_uncertainty_grows_with_magnitude():
    assert validate.value_uncertainty(0) == 0.00001
    assert 0.0000138 < validate.value_uncertainty(52.6) < 0.0000139
    assert 0.0000710 < validate.value_uncertainty(876.6) < 0.0000711
    assert 0.0001320 < validate.value_uncertainty(-2028.99) < 0.0001321
    assert 0.0002541 < validate.value_uncertainty(-2072.73) < 0.0002542


def test_missing_component_is_an_error():
    files = make_files()
    files.pop("x_MGHG.csv")
    _, _, issues = transform.parse_hour(files)
    assert any(i.severity == "error" and "MGHG" in i.message for i in issues)


def test_duplicate_row_is_an_error():
    files = make_files()
    files["x_LMP.csv"] += files["x_LMP.csv"].splitlines()[1] + "\n"
    _, _, issues = transform.parse_hour(files)
    assert any(i.check == "duplicate" for i in issues)


def test_out_of_range_is_a_warning_not_dropped():
    big = {"LMP": 9999.0, "MCE": 9999.0, "MCC": 0.0, "MCL": 0.0, "MGHG": 0.0}
    values, meta, _ = transform.parse_hour(make_files(big))
    start = "2026-11-08T03:00:00+00:00"
    issues = validate.check_interval(start, values[start], meta[start]["end"])
    assert [i.severity for i in issues] == ["warning"]


def test_real_prices_past_bid_floor_do_not_alert():
    # -150.19 was a real CAISO LMP on 2026-11-07
    real = {"LMP": -150.19243, "MCE": -150.0, "MCC": 0.0, "MCL": -0.19243, "MGHG": 0.0}
    values, meta, _ = transform.parse_hour(make_files(real))
    start = "2026-11-08T03:00:00+00:00"
    assert validate.check_interval(start, values[start], meta[start]["end"]) == []


def test_outliers_are_listed_for_the_map():
    nodes = {
        "NORMAL": {"lmp": 42.0},
        "HIGH": {"lmp": 9999.0},
        "LOW": {"lmp": -6000.0},
        "EDGE": {"lmp": 5000.0},  # on the bound: not an outlier
    }
    assert validate.find_outliers(nodes) == ["HIGH", "LOW"]


def test_missing_interval_is_info_first_then_warning_on_retry():
    hour = datetime(2026, 11, 8, 3, tzinfo=timezone.utc)
    got = ["2026-11-08T03:00:00+00:00"]
    assert validate.check_hour(hour, got)[0].severity == "info"
    assert validate.check_hour(hour, got, is_retry=True)[0].severity == "warning"


def test_unpriced_nodes_warn_only_when_list_changes():
    located = {f"N{i:02d}": {} for i in range(40)}
    priced = set(located) - {"N39"}
    issues, unpriced = validate.check_locations(priced, located, None)
    assert unpriced == ["N39"] and [i.severity for i in issues] == ["warning"]
    issues, _ = validate.check_locations(priced, located, ["N39"])
    assert issues == []


def test_poor_location_match_is_an_error():
    located = {f"N{i:02d}": {} for i in range(10)}
    issues, _ = validate.check_locations({"N00"}, located, None)
    assert any(i.severity == "error" for i in issues)


def test_retention_keeps_newest_100(tmp_path):
    store = LocalStore(tmp_path)
    entries = []
    for i in range(104):
        start = datetime(2026, 11, 7, tzinfo=timezone.utc).timestamp() + i * 900
        iso = datetime.fromtimestamp(start, timezone.utc).isoformat()
        key = interval_key(iso)
        store.put_json(key, {}, "")
        entries.append({"start": iso, "file": key.rsplit("/", 1)[-1]})
    index = prune_and_index(store, entries, {"finished_utc": "now"})
    assert len(index["intervals"]) == 100
    assert len(store.list_keys("caiso-lmp/intervals/")) == 100
    assert index["intervals"][0]["start"] == entries[4]["start"]


def test_price_map_rejects_points_outside_west():
    feed = {"l": [{"m": [
        {"t": "Node", "n": "OK", "c": [37.0, -120.0], "a": "CA", "p": "GEN"},
        {"t": "Node", "n": "BAD", "c": [0.0, 0.0], "a": "CA", "p": "GEN"},
    ]}]}
    nodes, issues = transform.parse_price_map(feed)
    assert list(nodes) == ["OK"]
    assert issues[0].check == "location"
