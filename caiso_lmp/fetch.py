"""Download raw data from CAISO. No changes to the data happen here."""

from __future__ import annotations

import io
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from . import config


class FetchError(Exception):
    """CAISO did not return usable data."""


@dataclass
class RawHour:
    """One hour of OASIS group files, exactly as downloaded."""

    hour_start: datetime  # UTC
    url: str
    retrieved_utc: datetime
    files: dict[str, str]  # file name -> CSV text


_last_request = 0.0


def _get(url: str, params: dict | None = None) -> requests.Response:
    """GET with a polite pause between requests and a single delayed retry."""
    global _last_request
    for attempt in (1, 2):
        wait = config.SECONDS_BETWEEN_REQUESTS - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise FetchError(f"Request failed: {exc}") from exc
        else:
            if resp.status_code == 200:
                return resp
            if attempt == 2 or resp.status_code not in (429, 500, 502, 503, 504):
                raise FetchError(f"HTTP {resp.status_code} from {resp.url}")
        time.sleep(config.RETRY_WAIT_SECONDS)
    raise FetchError("unreachable")


def oasis_time(dt: datetime) -> str:
    """OASIS wants times like 20261108T03:00-0000 (UTC)."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H:%M-0000")


def fetch_hour(hour_start: datetime) -> RawHour:
    """Download every node's FMM prices for one UTC hour (one request)."""
    hour_start = hour_start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    params = {
        "groupid": config.OASIS_GROUP_ID,
        "startdatetime": oasis_time(hour_start),
        "enddatetime": oasis_time(hour_start + timedelta(hours=1)),
        "resultformat": "6",  # CSV
        "version": config.OASIS_VERSION,
    }
    resp = _get(config.OASIS_GROUP_URL, params)
    retrieved = datetime.now(timezone.utc)
    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
    except zipfile.BadZipFile as exc:
        raise FetchError(f"OASIS did not return a zip file ({len(resp.content)} bytes)") from exc

    files: dict[str, str] = {}
    for name in zf.namelist():
        text = zf.read(name).decode("utf-8", errors="strict")
        if name.lower().endswith(".xml"):
            # OASIS reports problems (no data, bad request, too many requests) as an XML file.
            raise FetchError(f"OASIS returned a message instead of data: {text[:500]}")
        files[name] = text
    if not files:
        raise FetchError("OASIS zip was empty")
    return RawHour(hour_start=hour_start, url=resp.url, retrieved_utc=retrieved, files=files)


def fetch_price_map() -> tuple[dict, datetime]:
    """Download the price map feed (used only for node coordinates)."""
    resp = _get(config.PRICE_MAP_URL)
    try:
        return resp.json(), datetime.now(timezone.utc)
    except ValueError as exc:
        raise FetchError("Price map feed was not valid JSON") from exc
