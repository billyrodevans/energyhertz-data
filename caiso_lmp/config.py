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

# Sum check tolerance ($/MWh). CAISO publishes 5 decimals, so 4 rounded parts can be off by < 0.00003.
SUM_TOLERANCE = 0.0001

# Values outside this range are flagged for review (warning, not dropped): they can be real.
# CAISO's energy bid floor is -$150/MWh and its hard bid cap is $2,000/MWh; LMPs can still
# fall outside this range under constraint relaxation or scarcity pricing.
PLAUSIBLE_MIN = -150.0
PLAUSIBLE_MAX = 2000.0

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
