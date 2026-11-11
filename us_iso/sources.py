"""Download and cache the raw source files for the US ISO comparison.

Everything is cached under ./cache so a yearly rebuild doesn't download twice.
Requests are spaced out and identify the project (polite use of public servers).
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import requests

USER_AGENT = "energyhertz-data/0.1 (+https://energyhertz.com)"
CACHE = Path("cache")

EIA_861_URL = "https://www.eia.gov/electricity/data/eia861/zip/f861{year}.zip"
EIA_930_URL = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_{kind}_{year}_{half}.csv"
CAISO_FUEL_URL = "https://www.caiso.com/outlook/history/{ymd}/fuelsource.csv"
PCL_2024_URL = (
    "https://www.energy.ca.gov/sites/default/files/2026-01/"
    "2024_Power_Content_Labels_Sortable_Table_updated_01-05-2026_ADA.xlsx"
)
HIFLD_ISO_URL = (
    "https://services5.arcgis.com/D509rM2leyoHuJvj/arcgis/rest/services/"
    "Independent_System_Operators/FeatureServer/0/query"
)

# Public copy of HIFLD "Control Areas" (balancing authority areas; source dates 2018-2021).
# HIFLD Open data is US-government public domain; HIFLD Open itself was retired in 2025.
HIFLD_CONTROL_AREAS_URL = (
    "https://services.arcgis.com/jDGuO8tYggdCCnUJ/arcgis/rest/services/"
    "HIFLD_control_areas_geojson/FeatureServer/0/query"
)

_last = 0.0


def _get(url: str, params: dict | None = None, pause: float = 2.0, timeout: int = 600) -> bytes:
    global _last
    wait = pause - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    for attempt in (1, 2):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if r.status_code == 200:
                return r.content
            if attempt == 2:
                raise RuntimeError(f"HTTP {r.status_code} for {r.url}")
        except requests.RequestException:
            if attempt == 2:
                raise
        time.sleep(30)
    raise RuntimeError("unreachable")


def cached(name: str, url: str, params: dict | None = None, pause: float = 2.0) -> Path:
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _get(url, params, pause)
        # Guard against servers that answer a missing file with a web page instead of an error.
        if name.endswith(".zip") and not body.startswith(b"PK"):
            raise RuntimeError(f"{url} did not return a zip file (got {body[:40]!r})")
        if body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
            raise RuntimeError(f"{url} returned a web page, not data")
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(body)
        tmp.replace(path)
    return path


def eia_861(year: int) -> Path:
    return cached(f"eia861/f861{year}.zip", EIA_861_URL.format(year=year))


EIA_923_URLS = [  # latest year sits in xls/, earlier years move to archive/xls/
    "https://www.eia.gov/electricity/data/eia923/xls/f923_{year}.zip",
    "https://www.eia.gov/electricity/data/eia923/archive/xls/f923_{year}.zip",
]


def eia_923(year: int) -> Path:
    last = None
    for url in EIA_923_URLS:
        try:
            return cached(f"eia923/f923_{year}.zip", url.format(year=year))
        except RuntimeError as exc:
            last = exc
    raise RuntimeError(f"EIA-923 {year} not found: {last}")


def eia_930(kind: str, year: int) -> list[Path]:
    """kind: BALANCE or INTERCHANGE. Returns both six-month files for the year."""
    return [
        cached(f"eia930/EIA930_{kind}_{year}_{half}.csv", EIA_930_URL.format(kind=kind, year=year, half=half))
        for half in ("Jan_Jun", "Jul_Dec")
    ]


def caiso_fuel_days(start: date, end: date) -> list[Path]:
    """One CAISO Today's Outlook fuel-source file per day, start..end inclusive (3 s apart)."""
    out = []
    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        out.append(cached(f"caiso_fuel/{ymd}.csv", CAISO_FUEL_URL.format(ymd=ymd), pause=3.0))
        d += timedelta(days=1)
    return out


def pcl_2024() -> Path:
    return cached("cec/pcl2024.xlsx", PCL_2024_URL)


def hifld_iso_boundaries() -> Path:
    # Server-side simplification keeps the file small (about 0.02 degrees, roughly 2 km).
    return cached("hifld/iso_boundaries.geojson", HIFLD_ISO_URL, params={
        "where": "1=1",
        "outFields": "NAME,SOURCE,SOURCEDATE,VAL_DATE",
        "outSR": "4326",
        "maxAllowableOffset": "0.02",
        "geometryPrecision": "3",
        "f": "geojson",
    })


def hifld_control_areas() -> Path:
    return cached("hifld/control_areas.geojson", HIFLD_CONTROL_AREAS_URL, params={
        "where": "1=1",
        "outFields": "NAME,SOURCE,SOURCEDATE,VAL_DATE",
        "outSR": "4326",
        "maxAllowableOffset": "0.02",
        "geometryPrecision": "3",
        "f": "geojson",
    })


# California Energy Commission layers (free for public use with credit: energy.ca.gov/conditions-of-use).
CEC_LAYERS = {
    "ba": "Balancing_Authority",                             # California balancing authority areas (8 BAs)
    "utilities": "ElectricLoadServingEntities_IOU_POU",      # utility service areas (IOUs and public utilities)
    "utilities_other": "ElectricLoadServingEntities_Other",  # co-ops, federal, tribal, CCAs
}
CEC_URL = "https://services3.arcgis.com/bWPjFyq029ChCGur/ArcGIS/rest/services/{name}/FeatureServer/0/query"


def cec_layer(kind: str) -> Path:
    name = CEC_LAYERS[kind]
    return cached(f"cec/{name}.geojson", CEC_URL.format(name=name), params={
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "maxAllowableOffset": "0.005",
        "geometryPrecision": "4",
        "f": "geojson",
    })
