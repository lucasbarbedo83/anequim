import numpy as np
import pytest

from anequim import Anequim, QCConfig
from anequim.readers.olci import OlciL2Reader, OLCI_RRS_BANDS
from anequim.utils.file_discovery import resolve_files

from conftest import CENTER_LON, CENTER_LAT


def test_resolve_files_treats_safe_directory_as_one_granule(synthetic_olci_directory):
    resolved = resolve_files(synthetic_olci_directory)
    assert resolved == [synthetic_olci_directory] or resolved == [
        __import__("os").path.abspath(synthetic_olci_directory)
    ]


def test_olci_reader_matches(synthetic_olci_directory):
    assert OlciL2Reader.matches(synthetic_olci_directory)


def test_olci_reader_reads_expected_shapes(synthetic_olci_directory):
    with OlciL2Reader(synthetic_olci_directory) as reader:
        lon, lat = reader.get_navigation()
        wavelengths = reader.get_wavelengths()
        rrs_cube = reader.get_rrs_cube()
        flags = reader.get_quality_flags()

        assert lon.shape == lat.shape == (20, 20)
        assert wavelengths.shape[0] == len(OLCI_RRS_BANDS) == 16
        assert rrs_cube.shape == (20, 20, 16)
        assert flags.shape == (20, 20)
        assert reader.get_platform_name() == "Sentinel-3A"


def test_olci_reader_converts_rho_w_to_rrs(synthetic_olci_directory):
    """The synthetic file stores units='1' (rho_w convention); the reader
    should divide by pi to produce Rrs-scale values, matching the
    Rrs-scale spectrum the synthetic generator started from."""
    with OlciL2Reader(synthetic_olci_directory) as reader:
        rrs_cube = reader.get_rrs_cube()
    # Rrs at visible wavelengths should be O(1e-3 to 1e-2) sr^-1, not
    # O(1e-2 to 1e-1) (which is what it would be if left as rho_w).
    finite = rrs_cube[np.isfinite(rrs_cube)]
    assert finite.max() < 0.05


def test_anequim_get_rrs_with_olci(synthetic_olci_directory):
    cube = Anequim.retrieve(
        files=synthetic_olci_directory,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OLCI",
        box_size=5,
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0, min_signal_for_cv=0.0005),
    )
    assert cube.sensor == "Sentinel3-OLCI"
    assert cube.n_pixels == 25
    assert cube.n_bands == 16
    assert cube.qc.n_valid > 0
    # Pixel size should reflect OLCI's ~300 m resolution, not PACE's ~1km.
    assert cube.pixel_size_km is not None
    assert 0.2 < cube.pixel_size_km["mean_km"] < 0.5
    assert cube.provenance.nominal_pixel_size_m == 300.0


def test_anequim_get_rrs_pace_pixel_size_differs_from_olci(synthetic_pace_file, synthetic_olci_directory):
    """Cross-sensor sanity check: PACE OCI's ~1km pixels should be
    reported as clearly larger than OLCI's ~300m pixels."""
    pace_cube = Anequim.retrieve(
        files=synthetic_pace_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OCI",
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0),
    )
    olci_cube = Anequim.retrieve(
        files=synthetic_olci_directory,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OLCI",
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0, min_signal_for_cv=0.0005),
    )
    assert pace_cube.pixel_size_km["mean_km"] > olci_cube.pixel_size_km["mean_km"]


def test_olci_default_excluded_flags_used_when_not_overridden(synthetic_olci_directory):
    """Without an explicit QCConfig.flag_names, Anequim should use
    OlciL2Reader's own WQSF-appropriate defaults (not the OBPG ones),
    so the synthetic LAND-flagged corner pixels actually get excluded.
    """
    cube = Anequim.retrieve(
        files=synthetic_olci_directory,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OLCI",
        box_size=21,  # clipped to the whole 20x20 grid, guaranteed to include the flagged corner
        qc=QCConfig(min_valid_fraction=0.0, max_cv=100.0),
    )
    assert cube.qc.n_valid < cube.qc.n_total
