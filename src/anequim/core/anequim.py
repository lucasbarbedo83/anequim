"""The main user-facing entry point: the :class:`Anequim` class.

``Anequim.get_rrs(...)`` is the single call most users need: given a
point, a time, a sensor, and a set of local granule files, it finds the
best-matching granule(s), extracts the requested ROI, applies quality
control, and returns a sensor-independent
:class:`~anequim.core.spectral_cube.SpectralCube`.
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional, Sequence, Union

from . import flags as flags_module
from . import qc as qc_module
from . import time_utils
from .config import QCConfig, RetrievalConfig, TimeLike, parse_time
from .exceptions import OutsideSpatialDomainError, OutsideTimeWindowError
from .provenance import Provenance
from .spectral_cube import SpectralCube
from ..geometry.pixel_size import estimate_pixel_size_km, estimate_roi_footprint_km
from ..readers.registry import open_reader
from ..roi.base import ROI
from ..roi.rectangular import RectangularROI
from ..utils.file_discovery import resolve_files
from ..utils.validation import nearest_index


@dataclasses.dataclass
class _Candidate:
    time_delta_hours: float
    cube: SpectralCube


class Anequim:
    """Sensor-independent ocean-color Rrs retrieval.

    Parameters
    ----------
    files:
        A file path, directory, glob pattern, or list of any of these,
        pointing at local Level-2 granule files. See
        :func:`anequim.utils.file_discovery.resolve_files`.
    sensor:
        Default sensor alias (e.g. "OCI") used for every granule unless
        overridden per-call. If ``None``, each granule's sensor is
        auto-detected from its own metadata.
    """

    def __init__(self, files: Union[str, Sequence[str]], sensor: Optional[str] = None):
        self.files: List[str] = resolve_files(files)
        self.sensor = sensor
        if not self.files:
            raise FileNotFoundError("No granule files resolved from the given `files` argument")

    # -- main API --------------------------------------------------------
    def get_rrs(
        self,
        longitude: float,
        latitude: float,
        time: TimeLike,
        sensor: Optional[str] = None,
        roi: Optional[ROI] = None,
        time_window_hours: float = 3.0,
        box_size: int = 5,
        max_search_radius_km: float = 15.0,
        qc: Optional[QCConfig] = None,
        wavelengths: Optional[Sequence[float]] = None,
        wavelength_tolerance_nm: float = 2.5,
        include_atmospheric: bool = True,
        return_all_candidates: bool = False,
    ) -> Union[SpectralCube, List[SpectralCube]]:
        """Retrieve Rrs (+ ancillary products) closest to a point and time.

        Returns
        -------
        SpectralCube
            The match-up from the granule whose overpass time is closest
            to ``time`` (default), or a list of every matching granule's
            SpectralCube, sorted by time proximity, if
            ``return_all_candidates=True``.

        Raises
        ------
        OutsideSpatialDomainError
            If no granule's footprint comes within ``max_search_radius_km``
            of (longitude, latitude).
        OutsideTimeWindowError
            If granules cover the location but none fall within
            ``time_window_hours`` of ``time``.
        """
        config = RetrievalConfig(
            longitude=longitude,
            latitude=latitude,
            target_time=time,
            time_window_hours=time_window_hours,
            box_size=box_size,
            max_search_radius_km=max_search_radius_km,
            qc=qc or QCConfig(),
            wavelengths=wavelengths,
            wavelength_tolerance_nm=wavelength_tolerance_nm,
            include_atmospheric=include_atmospheric,
        )
        sensor = sensor or self.sensor
        roi_obj = roi or RectangularROI(longitude, latitude, box_size=box_size)

        candidates: List[_Candidate] = []
        any_spatial_coverage = False

        for path in self.files:
            cube = self._try_granule(path, sensor, roi_obj, config)
            if cube is None:
                continue
            any_spatial_coverage = True
            delta_h = abs(
                (parse_time(cube.provenance.acquisition_time).timestamp()
                 - config.target_time_dt.timestamp()) / 3600.0
            ) if cube.provenance.acquisition_time else float("inf")
            candidates.append(_Candidate(time_delta_hours=delta_h, cube=cube))

        if not candidates:
            if any_spatial_coverage:
                raise OutsideTimeWindowError(
                    f"Granules cover ({longitude}, {latitude}) but none fall within "
                    f"+/-{time_window_hours}h of {config.target_time_dt.isoformat()}"
                )
            raise OutsideSpatialDomainError(
                f"No granule among {len(self.files)} file(s) covers ({longitude}, {latitude}) "
                f"within {max_search_radius_km} km"
            )

        candidates.sort(key=lambda c: c.time_delta_hours)
        if return_all_candidates:
            return [c.cube for c in candidates]
        return candidates[0].cube

    # -- per-granule internals -------------------------------------------
    def _try_granule(
        self, path: str, sensor: Optional[str], roi_obj: ROI, config: RetrievalConfig
    ) -> Optional[SpectralCube]:
        reader = open_reader(path, sensor=sensor)
        with reader as r:
            start, end = r.get_time_coverage()
            if not time_utils.quick_overlaps_window(
                start, end, config.target_time_dt, config.half_window
            ):
                return None

            lon_grid, lat_grid = r.get_navigation()
            selection = roi_obj.select(
                lon_grid, lat_grid, max_search_radius_km=config.max_search_radius_km
            )
            if selection.n_selected == 0:
                return None

            fallback_time = time_utils.granule_midtime(start, end)
            scan_times = r.get_scan_line_times()
            if selection.center_row is not None:
                try:
                    acq_time = time_utils.nearest_scan_line_time(
                        scan_times, selection.center_row, fallback_time
                    )
                except ValueError:
                    acq_time = fallback_time
            else:
                acq_time = fallback_time

            if acq_time is not None and not time_utils.within_window(
                acq_time, config.target_time_dt, config.half_window
            ):
                return None

            native_wavelengths = r.get_wavelengths()
            band_indices = self._select_band_indices(
                native_wavelengths, config.wavelengths, config.wavelength_tolerance_nm
            )
            wavelengths_used = (
                native_wavelengths[band_indices] if band_indices is not None else native_wavelengths
            )

            rrs_cube = r.get_rrs_cube()
            mask2d = selection.mask
            pixel_rrs = rrs_cube[mask2d]
            if band_indices is not None:
                pixel_rrs = pixel_rrs[:, band_indices]

            quality_flags = r.get_quality_flags()
            pixel_flags = quality_flags[mask2d]

            name_to_bit = r.get_flag_name_to_bit() or flags_module.OBPG_NAME_TO_BIT
            exclusion_names = (
                config.qc.flag_names
                or r.get_default_excluded_flags()
                or flags_module.DEFAULT_EXCLUDED_FLAGS
            )
            exclusion_bitmask = flags_module.build_exclusion_bitmask(exclusion_names, name_to_bit)
            flagged = flags_module.flagged_mask(pixel_flags, exclusion_bitmask)
            valid_mask = ~flagged

            qc_result = qc_module.evaluate_roi(pixel_rrs, valid_mask, config.qc)

            pixel_size = None
            if selection.center_row is not None and selection.center_col is not None:
                ps = estimate_pixel_size_km(
                    lon_grid, lat_grid, selection.center_row, selection.center_col
                )
                if ps is not None:
                    pixel_size = dataclasses.asdict(ps)
            roi_footprint = estimate_roi_footprint_km(lon_grid, lat_grid, mask2d)

            atmospheric = {}
            if config.include_atmospheric:
                for name, arr in r.get_atmospheric_products().items():
                    atmospheric[name] = arr[mask2d]

            provenance = Provenance(
                sensor=reader.sensor_name,
                source_files=[path],
                acquisition_time=acq_time.isoformat() if acq_time else None,
                target_longitude=config.longitude,
                target_latitude=config.latitude,
                target_time=config.target_time_dt.isoformat(),
                roi_description=selection.description,
                qc_summary=qc_result.summary(),
                platform_name=r.get_platform_name(),
                processing_version=r.get_processing_version(),
                pixel_size_km=pixel_size,
                roi_footprint_km=roi_footprint,
                nominal_pixel_size_m=reader.nominal_pixel_size_m,
                extra={
                    "center_row": selection.center_row,
                    "center_col": selection.center_col,
                    "center_distance_km": selection.center_distance_km,
                },
            )

            return SpectralCube(
                sensor=reader.sensor_name,
                wavelengths=wavelengths_used,
                rrs=pixel_rrs,
                valid_mask=valid_mask,
                longitude=lon_grid[mask2d],
                latitude=lat_grid[mask2d],
                qc=qc_result,
                provenance=provenance,
                quality_flags=pixel_flags,
                atmospheric=atmospheric,
            )

    @staticmethod
    def _select_band_indices(native_wavelengths, requested, tolerance_nm):
        if requested is None:
            return None
        indices = []
        native_list = list(native_wavelengths)
        for wl in requested:
            idx = nearest_index(native_list, wl, tolerance=tolerance_nm)
            if idx is None:
                raise ValueError(
                    f"Requested wavelength {wl} nm has no native band within "
                    f"{tolerance_nm} nm"
                )
            indices.append(idx)
        return indices

    # -- convenience one-shot classmethod ----------------------------------
    @classmethod
    def retrieve(
        cls,
        files: Union[str, Sequence[str]],
        longitude: float,
        latitude: float,
        time: TimeLike,
        sensor: Optional[str] = None,
        **kwargs,
    ) -> Union[SpectralCube, List[SpectralCube]]:
        """One-shot convenience wrapper:
        ``Anequim.retrieve(files, lon, lat, time, sensor="OCI")``
        equivalent to constructing an ``Anequim`` instance and calling
        ``get_rrs`` once.
        """
        return cls(files=files, sensor=sensor).get_rrs(longitude, latitude, time, sensor=sensor, **kwargs)

    @classmethod
    def retrieve_online(
        cls,
        longitude: float,
        latitude: float,
        time: TimeLike,
        sensor: str = "OCI",
        time_window_hours: float = 3.0,
        cache_dir: Optional[str] = None,
        download_kwargs: Optional[dict] = None,
        **kwargs,
    ) -> Union[SpectralCube, List[SpectralCube]]:
        """Search NASA Earthdata for granules covering (longitude,
        latitude, time), download them, and retrieve Rrs — all in one
        call. Requires the optional ``earthaccess`` dependency and prior
        Earthdata Login authentication; see
        :func:`anequim.download.earthdata.login`.

        This is the only sensor/backend combination implemented today
        (PACE OCI via NASA Earthdata); see :mod:`anequim.download` for
        what's planned next.

        Parameters
        ----------
        download_kwargs:
            Extra keyword arguments forwarded to
            :func:`anequim.download.fetch_granules` (e.g.
            ``{"near_real_time": True, "padding_deg": 0.25}``).
        **kwargs:
            Forwarded to :meth:`get_rrs` (e.g. ``box_size``, ``qc``).

        Raises
        ------
        OutsideSpatialDomainError
            If the download search returns zero granules.
        """
        from ..download import fetch_granules

        files = fetch_granules(
            sensor=sensor,
            longitude=longitude,
            latitude=latitude,
            target_time=time,
            time_window_hours=time_window_hours,
            cache_dir=cache_dir,
            **(download_kwargs or {}),
        )
        if not files:
            raise OutsideSpatialDomainError(
                f"No {sensor} granules found covering ({longitude}, {latitude}) within "
                f"+/-{time_window_hours}h of {parse_time(time).isoformat()}"
            )
        return cls(files=files, sensor=sensor).get_rrs(
            longitude, latitude, time, sensor=sensor, time_window_hours=time_window_hours, **kwargs
        )
