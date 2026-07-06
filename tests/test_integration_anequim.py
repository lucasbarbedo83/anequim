import numpy as np
import pytest

from anequim import Anequim, QCConfig
from anequim.core.exceptions import OutsideSpatialDomainError, OutsideTimeWindowError
from anequim.readers.pace_oci import PaceOciL2Reader
from anequim.roi.circular import CircularROI

from conftest import CENTER_LON, CENTER_LAT


def test_pace_oci_reader_matches(synthetic_pace_file):
    assert PaceOciL2Reader.matches(synthetic_pace_file)


def test_pace_oci_reader_reads_expected_shapes(synthetic_pace_file):
    with PaceOciL2Reader(synthetic_pace_file) as reader:
        lon, lat = reader.get_navigation()
        wavelengths = reader.get_wavelengths()
        rrs_cube = reader.get_rrs_cube()
        flags = reader.get_quality_flags()

        assert lon.shape == lat.shape
        assert rrs_cube.shape[:2] == lon.shape
        assert rrs_cube.shape[2] == wavelengths.shape[0]
        assert flags.shape == lon.shape
        assert reader.get_platform_name() == "PACE"


def test_anequim_get_rrs_basic(synthetic_pace_file):
    cube = Anequim.retrieve(
        files=synthetic_pace_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OCI",
        box_size=5,
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0),
    )
    assert cube.sensor == "PACE-OCI"
    assert cube.n_pixels == 25  # 5x5 box, fully within the synthetic grid
    assert cube.n_bands == 12
    assert cube.qc.n_valid > 0
    assert cube.provenance.acquisition_time is not None


def test_anequim_get_rrs_outside_time_window_raises(synthetic_pace_file):
    with pytest.raises(OutsideTimeWindowError):
        Anequim.retrieve(
            files=synthetic_pace_file,
            longitude=CENTER_LON,
            latitude=CENTER_LAT,
            time="2024-06-16T14:45:00Z",  # one day off
            sensor="OCI",
            time_window_hours=1.0,
        )


def test_anequim_get_rrs_outside_spatial_domain_raises(synthetic_pace_file):
    with pytest.raises(OutsideSpatialDomainError):
        Anequim.retrieve(
            files=synthetic_pace_file,
            longitude=CENTER_LON + 50.0,
            latitude=CENTER_LAT,
            time="2024-06-15T14:45:00Z",
            sensor="OCI",
            max_search_radius_km=5.0,
        )


def test_anequim_get_rrs_with_circular_roi(synthetic_pace_file):
    roi = CircularROI(CENTER_LON, CENTER_LAT, radius_km=2.0)
    cube = Anequim.retrieve(
        files=synthetic_pace_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OCI",
        roi=roi,
        qc=QCConfig(min_valid_fraction=0.2, max_cv=1.0),
    )
    assert cube.n_pixels > 0


def test_anequim_get_rrs_wavelength_subset(synthetic_pace_file):
    cube = Anequim.retrieve(
        files=synthetic_pace_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OCI",
        wavelengths=[443.0, 555.0],
        wavelength_tolerance_nm=15.0,
        qc=QCConfig(min_valid_fraction=0.2, max_cv=1.0),
    )
    assert cube.n_bands == 2


def test_spectral_cube_exports(synthetic_pace_file, tmp_path):
    cube = Anequim.retrieve(
        files=synthetic_pace_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="OCI",
        qc=QCConfig(min_valid_fraction=0.2, max_cv=1.0),
    )
    spectrum_csv = tmp_path / "spectrum.csv"
    pixel_csv = tmp_path / "pixels.csv"
    cube.to_csv(str(spectrum_csv), kind="spectrum")
    cube.to_csv(str(pixel_csv), kind="pixel")
    assert spectrum_csv.exists()
    assert pixel_csv.exists()

    df = cube.spectrum_dataframe()
    assert len(df) == cube.n_bands
    summary = cube.summary()
    assert "reliable" in summary
