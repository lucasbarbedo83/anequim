"""Time parsing helpers for granule overpass times and window matching."""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import numpy as np

UTC = _dt.timezone.utc


def parse_iso(text: str) -> _dt.datetime:
    """Parse an ISO-8601 timestamp (trailing 'Z' accepted) into an aware
    UTC ``datetime``."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = _dt.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def yds_to_datetime(year: float, day_of_year: float, msec_of_day: float) -> _dt.datetime:
    """Convert the classic OBPG (year, day-of-year, millisecond-of-day)
    scan-line time encoding (``scan_line_attributes`` group in
    SeaWiFS/MODIS/VIIRS/OCI-style Level-2 files) into an aware UTC
    ``datetime``."""
    year_i = int(round(year))
    base = _dt.datetime(year_i, 1, 1, tzinfo=UTC)
    return base + _dt.timedelta(days=int(round(day_of_year)) - 1, milliseconds=float(msec_of_day))


def scan_line_times_from_yds(year: np.ndarray, day: np.ndarray, msec: np.ndarray) -> np.ndarray:
    """Vectorized :func:`yds_to_datetime`, returning ``datetime64[ns]``
    values (naive, implicitly UTC), one per scan line."""
    year = np.asarray(year)
    day = np.asarray(day)
    msec = np.asarray(msec)
    out = np.empty(year.shape, dtype="datetime64[ns]")
    for i in range(year.shape[0]):
        out[i] = np.datetime64(yds_to_datetime(year[i], day[i], msec[i]).replace(tzinfo=None))
    return out


def within_window(candidate: _dt.datetime, target: _dt.datetime, half_window: _dt.timedelta) -> bool:
    return abs(candidate - target) <= half_window


def time_delta_hours(candidate: _dt.datetime, target: _dt.datetime) -> float:
    return (candidate - target).total_seconds() / 3600.0


def nearest_scan_line_time(
    scan_times: Optional[np.ndarray], line_index: int, fallback: Optional[_dt.datetime] = None
) -> _dt.datetime:
    """Overpass time for a given scan line, falling back to a
    granule-level time if per-line times are unavailable/invalid."""
    if scan_times is not None and 0 <= line_index < len(scan_times):
        value = scan_times[line_index]
        if not np.isnat(value):
            seconds = value.astype("datetime64[s]").astype(int)
            return _dt.datetime.utcfromtimestamp(int(seconds)).replace(tzinfo=UTC)
    if fallback is not None:
        return fallback
    raise ValueError("No valid scan-line time and no fallback granule time provided")


def granule_time_bounds(
    time_coverage_start: Optional[str], time_coverage_end: Optional[str]
) -> "tuple[Optional[_dt.datetime], Optional[_dt.datetime]]":
    start = parse_iso(time_coverage_start) if time_coverage_start else None
    end = parse_iso(time_coverage_end) if time_coverage_end else None
    return start, end


def granule_midtime(
    time_coverage_start: Optional[str], time_coverage_end: Optional[str]
) -> Optional[_dt.datetime]:
    start, end = granule_time_bounds(time_coverage_start, time_coverage_end)
    if start is None and end is None:
        return None
    if start is None:
        return end
    if end is None:
        return start
    return start + (end - start) / 2


def quick_overlaps_window(
    time_coverage_start: Optional[str],
    time_coverage_end: Optional[str],
    target: _dt.datetime,
    half_window: _dt.timedelta,
) -> bool:
    """Cheap pre-filter used to skip opening files that cannot possibly
    match, based on granule-level coverage attributes alone."""
    start, end = granule_time_bounds(time_coverage_start, time_coverage_end)
    if start is None or end is None:
        return True
    window_start = target - half_window
    window_end = target + half_window
    return start <= window_end and end >= window_start
