"""Registry mapping sensor names to reader classes, plus auto-detection
of a granule's sensor from the file itself.

This is the single place that needs updating when a new sensor reader is
implemented — everything else in the package (the ``Anequim`` engine,
ROI, QC, statistics) is written against the generic
:class:`~anequim.readers.base.SensorReader` interface only.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from ..core.exceptions import UnsupportedSensorError
from .base import SensorReader
from .modis import ModisL2Reader
from .olci import OlciL2Reader
from .pace_oci import PaceOciL2Reader
from .viirs import ViirsL2Reader

#: Canonical registry, in the order ``detect_reader`` will probe them.
READERS: List[Type[SensorReader]] = [
    PaceOciL2Reader,
    OlciL2Reader,
    ViirsL2Reader,
    ModisL2Reader,
]

#: User-facing aliases accepted by ``Anequim.get_rrs(..., sensor=...)``.
_ALIASES: Dict[str, Type[SensorReader]] = {
    "oci": PaceOciL2Reader,
    "pace": PaceOciL2Reader,
    "pace-oci": PaceOciL2Reader,
    "pace_oci": PaceOciL2Reader,
    "olci": OlciL2Reader,
    "sentinel3-olci": OlciL2Reader,
    "sentinel-3": OlciL2Reader,
    "viirs": ViirsL2Reader,
    "modis": ModisL2Reader,
    "modis-aqua": ModisL2Reader,
    "modis-terra": ModisL2Reader,
}


def reader_for_sensor_name(sensor: str) -> Type[SensorReader]:
    """Look up a reader class by user-facing sensor name (case-insensitive).

    Raises
    ------
    UnsupportedSensorError
        If ``sensor`` does not match any known alias.
    """
    key = sensor.strip().lower()
    reader_cls = _ALIASES.get(key)
    if reader_cls is None:
        known = ", ".join(sorted(set(_ALIASES.keys())))
        raise UnsupportedSensorError(f"Unknown sensor '{sensor}'. Known aliases: {known}")
    return reader_cls


def detect_reader(path: str) -> Optional[Type[SensorReader]]:
    """Probe ``path`` against every registered reader's ``matches()`` and
    return the first that claims it, or ``None`` if none do.
    """
    for reader_cls in READERS:
        try:
            if reader_cls.matches(path):
                return reader_cls
        except Exception:
            continue
    return None


def open_reader(path: str, sensor: Optional[str] = None) -> SensorReader:
    """Construct (but do not yet ``open()``) a reader instance for
    ``path``. If ``sensor`` is given, use it directly; otherwise
    auto-detect from the file's own metadata.
    """
    if sensor is not None:
        reader_cls = reader_for_sensor_name(sensor)
    else:
        reader_cls = detect_reader(path)
        if reader_cls is None:
            raise UnsupportedSensorError(
                f"Could not auto-detect sensor for '{path}'. Pass sensor= explicitly."
            )
    return reader_cls(path)
