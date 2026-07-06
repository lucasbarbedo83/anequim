"""Shared scaffolding for sensor readers that are planned but not yet
implemented (OLCI, VIIRS, MODIS). Each still participates correctly in
sensor detection (``matches``) so that requesting an unimplemented sensor
gives a clear, specific error rather than a generic "no reader found".
"""

from __future__ import annotations

from ..core.exceptions import NotImplementedSensorError
from .base import SensorReader


class _StubReader(SensorReader):
    """Base class for readers whose file-format support is planned but
    not yet written. Instantiating and using one raises
    :class:`~anequim.core.exceptions.NotImplementedSensorError` with a
    message naming the sensor, rather than failing silently or with a
    generic AttributeError partway through a retrieval.
    """

    _global_attr_hints: "tuple[str, ...]" = ()

    def _not_implemented(self):
        raise NotImplementedSensorError(
            f"{self.sensor_name} support is planned but not yet implemented in anequim. "
            f"Currently only PACE OCI (sensor='OCI') is supported end-to-end."
        )

    def open(self) -> None:
        self._not_implemented()

    def close(self) -> None:
        return None

    def get_navigation(self):
        self._not_implemented()

    def get_time_coverage(self):
        self._not_implemented()

    def get_wavelengths(self):
        self._not_implemented()

    def get_rrs_cube(self):
        self._not_implemented()

    def get_quality_flags(self):
        self._not_implemented()
