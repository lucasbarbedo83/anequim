# Methodology

## Point/time Rrs retrieval

Anequim's default point-and-time retrieval (`Anequim.get_rrs` /
`Anequim.retrieve`) follows the general approach standardized for ocean
color calibration/validation ("cal/val") work by Bailey & Werdell
(2006), *"A multi-sensor approach for the on-orbit validation of
ocean-color satellite data products,"* and used in spirit across NASA
OB.DAAC and Copernicus match-up tools since. This is a general
implementation of a published protocol with literature-typical default
thresholds — not a byte-for-byte reproduction of any single program's
code. Always re-check the specific thresholds against whatever exact
protocol or paper you are trying to reproduce.

### 1. Spatial selection

By default, Anequim locates the granule pixel nearest the requested
longitude/latitude (great-circle distance, see
`anequim.geometry.distance.haversine_km`), then extracts an odd-sized
`N x N` pixel box centered on it (`box_size`, default 5 — i.e. a 5x5
box, 2 pixels on each side of the center). This is implemented as
`anequim.roi.rectangular.RectangularROI`.

Alternative ROI shapes are available and follow the same interface
(`anequim.roi.base.ROI.select`):

- `PixelROI` — the single nearest pixel only.
- `CircularROI` — all pixels within a given great-circle radius.
- `BoundingBoxROI` — all pixels within an explicit lon/lat rectangle.
- `PolygonROI` — planned, not yet implemented.

A `max_search_radius_km` sanity check (default 15 km) prevents silently
matching to the closest pixel in a swath that doesn't actually cover the
requested point.

### 2. Temporal selection

Only granules whose overpass time falls within `time_window_hours`
(default ±3 hours) of the requested time are used. Overpass time is
taken from the scan line nearest the matched pixel when per-scan-line
timing is available (the classic OBPG `scan_line_attributes` encoding:
`year`, `day`-of-year, `msec`-of-day), falling back to the granule's
`time_coverage_start`/`time_coverage_end` midpoint otherwise. A cheap
granule-level pre-filter (`anequim.core.time_utils.quick_overlaps_window`)
avoids doing spatial work on granules that cannot possibly match.

When multiple granules match, Anequim returns the one whose overpass
time is closest to the requested time (or all matches, sorted by time
proximity, via `return_all_candidates=True`).

### 3. Pixel-level quality control

Each pixel's quality-flag integer (e.g. OBPG `l2_flags`) is tested
against an exclusion bitmask built from a list of flag names
(`QCConfig.flag_names`). If not overridden, a literature-typical default
exclusion set is used (`anequim.core.flags.DEFAULT_EXCLUDED_FLAGS`):
`ATMFAIL, LAND, HIGLINT, HILT, HISATZEN, STRAYLIGHT, CLDICE, LOWLW,
CHLFAIL, NAVFAIL, NAVWARN, FILTER, SEAICE`. Readers prefer a granule's
own `flag_meanings`/`flag_masks` attributes when available over the
generic default bit table, guarding against a future sensor reordering
or renaming bits.

Non-finite pixels (NaN, typically from the sensor's own fill values)
are excluded regardless of flag status.

### 4. Box-level quality control

Given the pixels that survive step 3:

- **Valid fraction** — the fraction of the ROI's pixels that passed
  pixel-level QC must meet `QCConfig.min_valid_fraction` (default 0.5).
- **Spatial homogeneity** — the coefficient of variation (population
  std / mean) of the valid pixels is computed per wavelength band, then
  reduced to a single number via `QCConfig.cv_reduction` ("mean" by
  default; "any" or "median" also available). If this exceeds
  `QCConfig.max_cv` (default 0.15), the ROI is marked
  `homogeneous=False` — but is **not** silently discarded; the caller
  decides how to treat it (`SpectralCube.is_reliable()` requires both
  criteria to pass).
- **Optional outlier trimming** — if `QCConfig.exclude_outliers=True`,
  pixels beyond `QCConfig.outlier_n_std` standard deviations from the
  ROI mean (per band) are excluded before computing the representative
  statistic, mirroring an optional step used in several AERONET-OC and
  OB.DAAC-adjacent match-up pipelines.

### 5. Representative spectrum

The reported Rrs spectrum is the mean or median (`QCConfig.
center_statistic`) of the valid (and, if requested, outlier-trimmed)
pixels, with per-band standard deviation, per-band valid pixel count,
and per-band CV all retained in `SpectralCube.qc` for downstream
analysis.

## Wavelength handling

By default, Anequim returns every native band a sensor provides for a
given granule — no interpolation, no resampling. If `wavelengths=` is
given, the nearest available native band (within
`wavelength_tolerance_nm`) is selected per requested value; requesting a
wavelength with no sufficiently close native band raises a `ValueError`
rather than silently interpolating. True cross-sensor harmonization
(linear interpolation, or the more rigorous spectral-response-function
convolution) lives in `anequim.harmonization` and is opt-in by design —
see that module's docstrings for the planned implementation.

## Provenance

Every `SpectralCube` carries a `Provenance` record: the anequim package
version, sensor and platform identity, the source granule's own
processing version (when available), the acquisition time actually
used, the original request parameters, a description of the ROI
actually applied, the QC summary, and the software environment — so a
result can always be traced back to exactly how it was produced.

## References

- Bailey, S. W., & Werdell, P. J. (2006). A multi-sensor approach for the
  on-orbit validation of ocean color satellite data products. *Remote
  Sensing of Environment*, 102(1-2), 12-23.
- Zibordi, G., Melin, F., & Berthon, J.-F. (2009). A time series of
  above-water radiometric measurements for coastal water monitoring and
  satellite ocean color applications. *Journal of Atmospheric and
  Oceanic Technology*, 26(7), 1263-1274.
- Lee, Z., Carder, K. L., & Arnone, R. A. (2002). Deriving inherent
  optical properties from water color. *Applied Optics*, 41(27),
  5755-5772. (QAA — planned, `anequim.algorithms.qaa`)
- Werdell, P. J., et al. (2013). Generalized ocean color inversion model
  for retrieving marine inherent optical properties. *Applied Optics*,
  52(10), 2019-2037. (GIOP — planned, `anequim.algorithms.giop`)
- Maritorena, S., Siegel, D. A., & Peterson, A. R. (2002). Optimization
  of a semianalytical ocean color model for global-scale applications.
  *Applied Optics*, 41(15), 2705-2714. (GSM — planned,
  `anequim.algorithms.gsm`)
- NASA Ocean Biology Processing Group, PACE OCI Level-2 Data Format and
  `l2_flags` bit definitions (oceancolor.gsfc.nasa.gov).
