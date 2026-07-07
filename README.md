# Anequim

<p align="center">
  <img src="docs/images/anequim_logo.png" alt="Anequim — Catching the ocean spectrum" width="360">
</p>

**Catching the ocean spectrum.**

Anequim is a sensor-independent Python framework for retrieving ocean-color
remote sensing reflectance (Rrs) and associated atmospheric products from
local Level-2 satellite granules — fast, reliable, and without silently
resampling a sensor's native spectral bands.

> Retrieve the spectrum first. Everything else builds on that.

```python
from anequim import Anequim

cube = Anequim.retrieve(
    files="PACE_OCI.20240615T144200.L2.OC_AOP.nc",
    longitude=-70.5,
    latitude=41.3,
    time="2024-06-15T15:00:00Z",
    sensor="OCI",
)

print(cube)
print(cube.spectrum_dataframe())
```

## Design principles

1. **Sensor independence** — one API (`Anequim.get_rrs(...)`) across
   PACE OCI, Sentinel-3 OLCI, VIIRS, and MODIS. You interact with the
   same object regardless of sensor.
2. **Preserve native spectral bands** — anequim never interpolates
   automatically. Each sensor keeps its own wavelengths and spectral
   response; harmonization is opt-in (`anequim.harmonization`).
3. **Fast spectral retrieval** — answer "what is the ocean reflectance
   spectrum at this location?" in one call.
4. **Atmospheric products included** — AOT, Ångström exponent, solar/
   sensor zenith, relative azimuth, wind speed, and quality flags ride
   alongside Rrs through the same interface, when available.
5. **Region-of-interest tools** — single pixel, circular, rectangular,
   and lon/lat bounding-box ROIs today; polygon ROI is planned.
6. **`SpectralCube`** — every sensor returns the same container: Rrs,
   wavelengths, metadata, navigation, atmospheric products, and quality
   flags.
7. **Scientific reproducibility** — every result carries a `Provenance`
   record: package version, acquisition time, sensor identity,
   processing version, and the exact ROI/QC configuration used.

## What's implemented in this release (v0.1)

| Module | Status |
|---|---|
| `core` (config, QC, flags, `SpectralCube`, `Provenance`, `Anequim`) | **Working** |
| `readers` — PACE OCI (`sensor="OCI"`) | **Working** |
| `readers` — Sentinel-3 OLCI (`sensor="OLCI"`) | **Working** (directory-based SAFE granules; see caveats below) |
| `readers` — VIIRS / MODIS | Registered, raise `NotImplementedSensorError` (see module docstrings for the planned design — nearly identical file layout to PACE OCI, so these are the next-easiest to add) |
| `roi` — pixel, rectangular, circular, bounding box | **Working** |
| `roi` — polygon | Stub (`NotImplementedError`) |
| `geometry` (haversine distance, nearest-pixel search) | **Working** |
| `statistics` (mean, median, std, percentile, covariance, correlation) | **Working** |
| `download` — PACE OCI via NASA Earthdata (`earthaccess`) | **Working** (`pip install anequim[download]`) |
| `download` — Sentinel-3 OLCI via Copernicus Marine | Stub — blocked on an OLCI reader existing |
| `harmonization` (wavelength interpolation, SRF convolution) | Stub, opt-in by design |
| `algorithms` (QAA, GIOP, GSM) | Stub — future bio-optical inversion |
| `plot` | `plot_spectrum` working; comparison/map plots stubbed |

Anequim can now find and download PACE OCI granules for you
(`Anequim.retrieve_online(...)`), or you can still point it at files
you already have (`Anequim.retrieve(files=..., ...)`). For any other
sensor, use `earthaccess`/the Copernicus Marine Toolbox yourself and
hand the resulting paths to `Anequim(files=...)`.

## Match-up methodology

For a point/time query, Anequim follows the spirit of the widely-used
satellite ocean-color match-up protocol described by Bailey & Werdell
(2006):

1. Locate the pixel nearest the target longitude/latitude, then extract
   an odd-sized `N x N` box around it (default `5x5`) — or use a
   circular / bounding-box ROI instead.
2. Only use granules whose overpass time is within a configurable window
   of the target time (default ±3 hours).
3. Drop pixels flagged by the sensor's own quality flags (cloud, land,
   glint, extreme geometry, stray light, navigation failure, ...).
4. Require a minimum valid-pixel fraction in the ROI (default 50%), and
   flag (but don't silently discard) ROIs with excessive spatial
   heterogeneity via coefficient of variation (default threshold 0.15).
5. Report the mean or median of the valid pixels as the representative
   spectrum, with full statistics attached so you can apply your own,
   stricter or looser, acceptance criteria.

See `docs/METHODOLOGY.md` for the full write-up and references, and
`docs/ARCHITECTURE.md` for how the modules fit together.

## Installation

```bash
pip install -e ".[all]"   # editable install with plotting + xarray + test extras
```

Core runtime dependencies: `numpy`, `netCDF4`, `pandas`.

## Quick start (download + retrieve in one call)

Requires `pip install anequim[download]` and a free NASA Earthdata
Login account (https://urs.earthdata.nasa.gov/):

```python
from anequim import Anequim
from anequim.download import login

login(strategy="netrc")  # or strategy="interactive", persist=True the first time

cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="OCI",
)
print(cube.spectrum_dataframe())
```

This searches NASA CMR for PACE OCI L2 AOP granules covering your point
and time window, downloads any matches to `~/.anequim/cache` (or
`cache_dir=` of your choosing), and runs the same retrieval pipeline as
`Anequim.retrieve(files=..., ...)`.

## Quick start (CLI, local files)

```bash
anequim --files data/*.nc --sensor OCI --lon -70.5 --lat 41.3 \
    --time 2024-06-15T15:00:00Z --window-hours 3 --box-size 5 \
    --output matchup.csv
```

## Pixel size and ROI footprint

Every `SpectralCube` reports the *actual* ground pixel size, measured
directly from the granule's own geolocation grid at the matched
location — not a hardcoded nominal constant, since real pixel size
varies substantially off-nadir:

```python
cube.pixel_size_km        # {'along_track_km':.., 'cross_track_km':.., 'mean_km':.., 'area_km2':..}
cube.roi_footprint_km      # {'n_rows':.., 'n_cols':.., 'along_track_km':.., 'cross_track_km':.., 'diagonal_km':..}
cube.provenance.nominal_pixel_size_m   # sensor's documented nadir spec, for reference (300 for OLCI, ~1000 for PACE OCI)
```

## Sentinel-3 OLCI — known caveats

OLCI L2 WFR granules are a **directory** (ESA SAFE format,
`S3?_OL_2_WFR____....SEN3`), not a single file — pass the directory path
itself to `files=`. A couple of things to know:

- **Units**: EUMETSAT's Collection 4 (effective Feb 2026) switched the
  per-band product from water-leaving reflectance ρw to Rrs directly.
  The reader checks each band's own `units` attribute and converts
  automatically either way — no action needed.
- **Atmospheric geometry**: solar/sensor zenith and relative azimuth
  live on a coarser "tie-point" grid in OLCI files and aren't
  interpolated to the full-resolution grid yet, so
  `cube.atmospheric` may be sparse (AOT/Ångström are included when
  present; geometry is not, for now).
- **Default QC flags**: OLCI's WQSF flags have a different vocabulary
  than PACE/MODIS/VIIRS's `l2_flags`; a WQSF-appropriate default
  exclusion set is used automatically (see
  `anequim.readers.olci.DEFAULT_OLCI_EXCLUDED_FLAGS`) — verify it
  against your own file's `flag_meanings` for rigorous work.

## Testing without real satellite data

`examples/make_synthetic_pace_file.py` and
`examples/make_synthetic_olci_directory.py` generate small, structurally
realistic synthetic granules (correct group/variable or directory
layout, a plausible phytoplankton-like Rrs spectral shape, and a
scattering of flagged pixels) so the whole pipeline can be exercised
offline for either sensor. The test suite (`tests/`) uses them as
pytest fixtures (`synthetic_pace_file`, `synthetic_olci_directory`).

```bash
pytest
python examples/quickstart.py
```

## Long-term vision

Anequim aims to become a reference open-source library for ocean-color
spectral retrieval: one consistent interface across sensors, preserving
each sensor's scientific integrity. A companion project, **Anequim Lab**,
is planned as a collection of notebooks for tutorials, validation
exercises, inter-sensor comparisons, and advanced bio-optical workflows.

## References

- Bailey, S. W., & Werdell, P. J. (2006). A multi-sensor approach for the
  on-orbit validation of ocean color satellite data products. *Remote
  Sensing of Environment*, 102(1-2), 12-23.
- Lee, Z., Carder, K. L., & Arnone, R. A. (2002). Deriving inherent
  optical properties from water color: a multiband quasi-analytical
  algorithm for optically deep waters. *Applied Optics*, 41(27), 5755-5772.
- Werdell, P. J., et al. (2013). Generalized ocean color inversion model
  for retrieving marine inherent optical properties. *Applied Optics*,
  52(10), 2019-2037.
- Maritorena, S., Siegel, D. A., & Peterson, A. R. (2002). Optimization
  of a semianalytical ocean color model for global-scale applications.
  *Applied Optics*, 41(15), 2705-2714.
- NASA Ocean Biology Processing Group, PACE OCI Level-2 Data Format and
  `l2_flags` bit definitions (oceancolor.gsfc.nasa.gov).

## License

MIT.
