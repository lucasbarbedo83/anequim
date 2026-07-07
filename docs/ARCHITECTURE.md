# Architecture

```
anequim/
    core/            configuration, QC, flags, SpectralCube, Provenance, the Anequim engine
    readers/          one class per sensor's file format; PACE OCI implemented, others stubbed
    download/         planned network/download layer (stub in this release)
    roi/              region-of-interest selectors (pixel, rectangular, circular, bbox, polygon)
    geometry/         great-circle distance, nearest-pixel search on curvilinear grids, pixel-size/ROI-footprint estimation
    statistics/       spectral statistics computed over a SpectralCube
    algorithms/       planned bio-optical inversion models (QAA, GIOP, GSM) — stubs
    harmonization/    opt-in wavelength interpolation / SRF convolution — stubs
    plot/             plot_spectrum (working); comparison/map plots — stubs
    utils/            file discovery, small validation helpers
    cli.py            command-line entry point
tests/                 pytest suite, uses a synthetic PACE OCI granule (no network needed)
examples/               synthetic-granule generator + quickstart script
docs/                   this file, plus METHODOLOGY.md
```

## Data flow for `Anequim.get_rrs(...)`

```
   Anequim(files, sensor)
          |
          v
   utils.file_discovery.resolve_files
          |
          v
   for each candidate file:
          |
          v
   readers.registry.open_reader(path, sensor)  -----> readers.pace_oci.PaceOciL2Reader
          |                                              (or a future OLCI/VIIRS/MODIS reader)
          v
   reader.get_time_coverage() ---> core.time_utils.quick_overlaps_window()  [cheap pre-filter]
          |
          v
   reader.get_navigation() ---> roi.<Type>ROI.select(lon_grid, lat_grid)
          |                           (uses geometry.nearest / geometry.distance)
          v
   ROISelection.mask (boolean, same shape as lon/lat grids)
          |
          v
   reader.get_scan_line_times() / get_time_coverage()
          ---> core.time_utils.nearest_scan_line_time() / granule_midtime()
          ---> core.time_utils.within_window()  [final temporal check]
          |
          v
   reader.get_rrs_cube()[mask], reader.get_quality_flags()[mask],
   reader.get_atmospheric_products()[*][mask]
          |
          v
   core.flags.build_exclusion_bitmask + flagged_mask   [pixel-level QC]
          |
          v
   core.qc.evaluate_roi(values, valid_mask, QCConfig)   [box-level QC + representative spectrum]
          |
          v
   core.provenance.Provenance(...)
          |
          v
   core.spectral_cube.SpectralCube(...)  <-- returned to the caller
```

Across every candidate granule, the one whose overpass time is closest
to the requested time is returned by default (`return_all_candidates=
True` returns them all, sorted by time proximity).

## Why sensor independence works

Every module downstream of `readers/` — `roi`, `core.qc`,
`core.anequim`, `statistics`, `plot` — is written against:

1. Plain numpy arrays (2D lon/lat grids; a `(rows, cols, bands)` Rrs
   cube; a `(rows, cols)` flag array), and
2. The `SensorReader` abstract interface (`readers/base.py`).

Adding a new sensor means writing exactly one new `SensorReader`
subclass that implements `get_navigation`, `get_wavelengths`,
`get_rrs_cube`, `get_quality_flags`, `get_time_coverage`, and (optionally)
`get_scan_line_times`, `get_atmospheric_products`, `get_flag_name_to_bit`,
`get_default_excluded_flags`, `get_platform_name`, `get_processing_version`
— then registering it in `readers/registry.py`. Nothing in `core`, `roi`,
`statistics`, or `plot` needs to change.

Sensors whose granules are a single file (PACE OCI) vs. a directory of
many files (Sentinel-3 OLCI's SAFE format) are both supported: a reader
just needs to accept whichever `path` its `matches()` claims. The one
shared piece of infrastructure this required was teaching
`utils.file_discovery.resolve_files` to recognize a directory containing
an `xfdumanifest.xml` marker as *one* granule rather than a folder of
files — a generic-enough convention (the ESA SAFE format marker) that it
doesn't need to know anything sensor-specific.

## Why the stub modules are structured the way they are

`download`, `harmonization`, and `algorithms` all raise a specific,
named exception (`DownloadNotAvailableError`,
`HarmonizationNotAvailableError`, `AlgorithmNotAvailableError`) rather
than not existing at all. This lets user code and documentation refer to
the intended final API today (e.g. `anequim.algorithms.QAA().invert(cube)`),
with a clear, catchable, specifically-named error instead of an
`AttributeError`/`ImportError` if a user reaches for something not built
yet — and each stub's docstring records the intended design so a future
implementation (by anyone) starts from an already-thought-through plan
rather than a blank file.
