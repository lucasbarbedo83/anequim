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

**Author:** Lucas Barbedo — Oceanographer, M.Sc. in Remote Sensing,
Ph.D. in Oceanography, currently at Météo-France.

**Citation:** If you use Anequim in a publication, please cite it — see
[`CITATION.cff`](CITATION.cff), or:
> Barbedo, L. (2026). *Anequim: A sensor-independent Python framework
> for ocean-color remote sensing reflectance and atmospheric product
> retrieval* (Version 0.1.0) [Computer software].
> https://github.com/lucasbarbedo83/anequim

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
   alongside Rrs through the same interface, when available. Total
   column ozone and water vapor/surface pressure can additionally be
   fetched on demand to compute downwelling irradiance just above the
   sea surface, Ed(0+) — see [Downwelling irradiance](#downwelling-irradiance-ed0-frouin-algorithm) below.
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
| `readers` — MODIS-Aqua/Terra (`sensor="MODIS"`) | **Working** |
| `readers` — VIIRS SNPP/NOAA-20 (`sensor="VIIRS"`) | **Working** |
| `readers` — Sentinel-3 OLCI (`sensor="OLCI"`) | **Working** (directory-based SAFE granules; see caveats below) |
| `roi` — pixel, rectangular, circular, bounding box | **Working** |
| `roi` — polygon | Stub (`NotImplementedError`) |
| `geometry` (haversine distance, nearest-pixel search, pixel size/footprint) | **Working** |
| `statistics` (mean, median, std, percentile, covariance, correlation) | **Working** |
| `download` — PACE OCI / MODIS / VIIRS via NASA Earthdata (`earthaccess`) | **Working** (`pip install anequim[download]`) |
| `download` — Sentinel-3 OLCI via EUMETSAT Data Store (`eumdac`, default) or CDSE (alternative) | **Working** (`pip install anequim[download]`) |
| `download.ancillary` — ozone (OMI/Aura) + water vapor/pressure (MERRA-2) via NASA Earthdata | **Working** (`pip install anequim[download]`) |
| `atmosphere` — Frouin-algorithm hyperspectral downwelling irradiance, Ed(0+) | **Working** |
| `harmonization` (wavelength interpolation, SRF convolution) | Stub, opt-in by design |
| `algorithms` (QAA, GIOP, GSM) | Stub — future bio-optical inversion |
| `plot` | `plot_spectrum` working; comparison/map plots stubbed |

All four NASA/ESA ocean color missions anequim targets (PACE OCI,
MODIS-Aqua, MODIS-Terra, VIIRS-SNPP/NOAA-20, Sentinel-3 OLCI) are now
readable **and** downloadable through the same one-call interface:
`Anequim.retrieve_online(longitude, latitude, time, sensor=...)`. Every
sensor returns the identical `SpectralCube` shape — same fields, same
methods — regardless of which agency or file format it came from.

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

## Quick start (download + retrieve in one call — any supported sensor)

The interaction is the same regardless of sensor: give a point, a time,
and a sensor; anequim finds the granule, downloads it, and returns a
`SpectralCube`. Only the one-time credential setup differs, since PACE
OCI and Sentinel-3 OLCI are distributed by different agencies.

Requires `pip install anequim[download]`.

**PACE OCI** — via NASA Earthdata (`earthaccess`):
```python
from anequim import Anequim
from anequim.download import login

login(strategy="netrc")  # or strategy="interactive", persist=True the first time

cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="OCI",
)
```
One-time setup: create a free NASA Earthdata Login account
(https://urs.earthdata.nasa.gov/), then either run
`anequim.download.login(strategy="interactive", persist=True)` once (it
saves credentials to `~/.netrc`), or write `~/.netrc` yourself.

**Sentinel-3 OLCI** — via EUMETSAT's Data Store (default backend, uses
the official `eumdac` client):
```python
import os
os.environ["EUMETSAT_CONSUMER_KEY"] = "..."
os.environ["EUMETSAT_CONSUMER_SECRET"] = "..."

from anequim import Anequim

cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="OLCI",
)
```
One-time setup: create a free EUMETSAT User Portal account
(https://user.eumetsat.int/register), then — **important, easy to
miss** — log in, open your profile, go to "My data licenses", and
enable "Meteosat > 1hr latency & Metop, Copernicus data & Third party
data" (Sentinel-3 products aren't accessible without this, even with
valid credentials). Then generate a consumer key/secret at
https://api.eumetsat.int/api-key and set them as environment variables.
This credential type is a static key pair — no 2FA interaction, unlike
CDSE below.

**Alternative OLCI backend** — Copernicus Data Space Ecosystem (CDSE),
same underlying data, different agency/account:
```python
import os
os.environ["CDSE_USERNAME"] = "you@example.com"
os.environ["CDSE_PASSWORD"] = "..."

from anequim import Anequim

cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="OLCI",
    download_kwargs={"backend": "cdse"},
)
```
One-time setup: create a free CDSE account
(https://dataspace.copernicus.eu/) with a direct email+password login
(not Google/institutional SSO — that login type isn't supported by the
API used here), then set `CDSE_USERNAME` / `CDSE_PASSWORD` as
environment variables.

**If two-factor authentication is enabled on your CDSE account** (check
your account settings), plain username/password isn't enough — call
`login()` once per session with your current 2FA code:
```python
from anequim.download.copernicus import login
login(totp="123456")  # current 6-digit code from your authenticator app
```
This caches a refresh token to `~/.anequim/cdse_refresh_token`, so every
`retrieve_online(sensor="OLCI", download_kwargs={"backend": "cdse"})`
call afterward — including from unattended scripts — works silently
without needing your password or a new 2FA code again, until that
refresh token eventually expires (at which point call `login()` again).

**MODIS / VIIRS** — via NASA Earthdata, same credentials as PACE OCI
above:
```python
cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="MODIS",
    download_kwargs={"platform": "Aqua"},   # or "Terra"
)
cube = Anequim.retrieve_online(
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z", sensor="VIIRS",
    download_kwargs={"platform": "SNPP"},   # or "NOAA-20"
)
```

All calls search the respective agency's catalog for granules covering
your point and time window, download to `~/.anequim/cache/...` (or
`cache_dir=` of your choosing), and run the same retrieval pipeline as
`Anequim.retrieve(files=..., ...)`. Note: PACE OCI/MODIS/VIIRS and
Sentinel-3 OLCI are distributed by different space agencies (NASA vs.
ESA/EU/EUMETSAT — and OLCI even has two independent portals) via
genuinely separate catalogs and credential systems — that's a fact
about the data providers, not a design choice of anequim's.

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

## Downwelling irradiance (Ed(0+)) — Frouin algorithm

Beyond Rrs, anequim can compute hyperspectral downwelling irradiance
just above the sea surface, Ed(0+, λ), using the Frouin algorithm
(Frouin & Chertock, 1992; Frouin, Franz & Werdell, 2003) — the same
physical framework NASA uses operationally for PAR and surface
irradiance products. This needs two things beyond what a granule alone
provides: ozone and water vapor/pressure, fetched from NASA Earthdata
(OMI/Aura and MERRA-2, respectively).

**One-call version** — fetch everything and get an `Ed(0+)` spectrum:

```python
from anequim import Anequim
from anequim.atmosphere import FrouinIrradiance, atmospheric_state_from_cube
import numpy as np

cube = Anequim.retrieve(
    files="PACE_OCI.20240615T144200.L2.OC_AOP.nc",
    longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z",
    sensor="OCI",
    include_ancillary_atmosphere=True,  # fetches ozone (OMI/Aura) + water vapor/pressure (MERRA-2)
)

state = atmospheric_state_from_cube(cube)   # builds AtmosphericState from cube.atmospheric + provenance
model = FrouinIrradiance()
wavelengths = np.arange(400.0, 700.0, 1.0)  # nm
ed = model.downwelling_irradiance(wavelengths, state)   # W m^-2 nm^-1
par = model.par_from_spectrum(wavelengths, ed)          # mol quanta m^-2 s^-1
```

`include_ancillary_atmosphere=True` requires the same NASA Earthdata
credentials as `Anequim.retrieve_online(sensor="OCI", ...)` above (see
that section for one-time setup) — ozone and water vapor/pressure are
fetched per match-up and merged into `cube.atmospheric` as `ozone_du`,
`water_vapor_cm`, `surface_pressure_hpa`. Aerosol optical depth is
**not** fetched separately: `atmospheric_state_from_cube` derives it
from the granule's own `aot_865` + `angstrom` (scene-matched, higher
resolution than any reanalysis aerosol field).

**Already have ozone/water vapor from elsewhere?** Pass them directly
instead of using `include_ancillary_atmosphere`:

```python
cube = Anequim.retrieve(files=..., longitude=-70.5, latitude=41.3, time=..., sensor="OCI")
state = atmospheric_state_from_cube(cube, ozone_du=290.0, water_vapor_cm=2.1)
```

**Accuracy note**: the built-in reference solar spectrum, ozone
absorption cross-section, and water-vapor absorption coefficients are
physically-reasonable placeholders (the solar spectrum integrates to
the correct ~1360 W/m² total solar irradiance), not NASA's
vicariously-calibrated operational tables. For quantitative work,
supply your own via `FrouinIrradiance.set_solar_spectrum()`,
`.set_ozone_cross_section()`, and `.set_water_vapor_coefficients()`
(e.g. TSIS-1 HSRS, Bogumil et al. 2003, Bird & Riordan 1986). See the
module docstring in `anequim/atmosphere/frouin_irradiance.py` for
details and references.



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
