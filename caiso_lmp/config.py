"""Settings in one place. Change values here, not inside the other modules."""

# Identify ourselves to CAISO in every request (polite, and lets them contact us).
USER_AGENT = "energyhertz-data/0.1 (+https://energyhertz.com)"

# CAISO OASIS group download: every node's Fifteen-Minute Market (RTPD) prices for a time window.
OASIS_GROUP_URL = "https://oasis.caiso.com/oasisapi/GroupZip"
OASIS_GROUP_ID = "RTPD_LMP_GRP"
OASIS_VERSION = "3"

# Node coordinates: the JSON feed behind CAISO's public price map
# (https://www.caiso.com/todays-outlook/prices). Approximate, substation-level positions.
PRICE_MAP_URL = "https://wwwmobile.caiso.com/Web.Service.Chart/api/v3/ChartService/PriceContourMap1"
NODES_MAX_AGE_HOURS = 24  # refresh node coordinates at most once a day

# Be gentle with CAISO.
SECONDS_BETWEEN_REQUESTS = 6
REQUEST_TIMEOUT_SECONDS = 120
RETRY_WAIT_SECONDS = 60  # one retry only, after this wait

# The five price files CAISO puts in each group download, and the names we use.
# LMP = MCE (energy) + MCC (congestion) + MCL (loss) + MGHG (greenhouse gas)  [CAISO Tariff Appendix C]
COMPONENTS = {
    "LMP": "lmp",
    "MCE": "energy",
    "MCC": "congestion",
    "MCL": "loss",
    "MGHG": "ghg",
}
FIELD_ORDER = ["lmp", "energy", "congestion", "loss", "ghg"]

INTERVAL_MINUTES = 15
INTERVALS_PER_HOUR = 4
KEEP_INTERVALS = 96  # 24 hours of 15-minute intervals

# Sum check precision. CAISO's published prices behave like single-precision numbers
# (about 7 significant digits) written with up to 5 decimals, so the last digit of a large
# price is uncertain: ~$0.00006 at $900, ~$0.00012 at $2,000. Each value's allowance is
# its single-precision step size plus one 5th-decimal step; the check allows the sum of the
# five allowances. Verified 2026-11-10 on 301,744 node-intervals (worst case used 54%).
# See validate.value_uncertainty().
FLOAT32_MANTISSA_BITS = 23
DECIMAL_STEP = 0.00001

# Sanity bounds, not market limits: catch corrupted data (e.g. wrong units, garbled numbers),
# not unusual-but-real prices. Real LMPs can go past CAISO's -$150 bid floor and $2,000 hard cap
# (seen 2026-11-07: -$150.19 at three nodes), so the bounds sit well outside both.
# Values outside are flagged for review (warning) and still published as-is.
PLAUSIBLE_MIN = -5000.0
PLAUSIBLE_MAX = 5000.0

# Rough box around the Western Interconnection, for checking node coordinates.
WEST_LAT = (25.0, 56.0)
WEST_LON = (-130.0, -100.0)

# Where files go in the R2 bucket (one folder per dashboard).
R2_PREFIX = "caiso-lmp"

# Attribution required by CAISO's Terms of Use: credit the California ISO.
SOURCE = {
    "publisher": "California ISO",
    "prices": "CAISO OASIS, Fifteen-Minute Market LMP (RTPD_LMP_GRP)",
    "prices_url": "https://oasis.caiso.com/",
    "locations": "California ISO price map (approximate, substation-level)",
    "locations_url": "https://www.caiso.com/todays-outlook/prices",
    "terms_url": "https://www.caiso.com/privacy-terms-of-use",
}
