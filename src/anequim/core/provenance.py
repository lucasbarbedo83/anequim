"""Provenance / reproducibility metadata attached to every SpectralCube.

Anequim treats reproducibility as a first-class concern (principle 7):
every result records the software version, the sensor/processing
identity of its source granule(s), the acquisition time actually used,
and the exact ROI/QC configuration applied, so a result can be traced
back to how it was produced without external notes.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import platform
import sys
from typing import Any, Dict, List, Optional

from .. import __version__


@dataclasses.dataclass
class Provenance:
    """Reproducibility record for a single :class:`~anequim.core.spectral_cube.SpectralCube`.

    Attributes
    ----------
    anequim_version:
        Version of the anequim package that produced the result.
    sensor:
        Canonical sensor name (e.g. "PACE-OCI").
    platform_name:
        Satellite platform name as reported by the source granule, if any.
    processing_version:
        Processing/algorithm version string from the granule's global
        attributes (e.g. NASA OB.DAAC ``processing_version``).
    source_files:
        Absolute paths of the granule file(s) actually used.
    acquisition_time:
        The overpass time associated with the retrieved pixels (ISO-8601
        string, UTC).
    request_time:
        Wall-clock time (UTC) at which the retrieval was executed.
    target_longitude, target_latitude, target_time:
        The original request parameters.
    roi_description:
        Human-readable description of the ROI actually used (e.g.
        "5x5 pixel box centered on nearest pixel").
    qc_summary:
        Dict summarizing the QC decision (n_valid, n_total, valid_fraction,
        cv, homogeneous, flags_excluded, center_statistic).
    software_environment:
        Python / OS version strings, for debugging reproducibility issues.
    extra:
        Free-form dict for reader-specific provenance fields.
    """

    sensor: str
    source_files: List[str]
    acquisition_time: Optional[str]
    target_longitude: float
    target_latitude: float
    target_time: str
    roi_description: str
    qc_summary: Dict[str, Any]
    platform_name: Optional[str] = None
    processing_version: Optional[str] = None
    anequim_version: str = dataclasses.field(default_factory=lambda: __version__)
    request_time: str = dataclasses.field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    )
    software_environment: Dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
    )
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)
