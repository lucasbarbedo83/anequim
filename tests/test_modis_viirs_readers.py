import numpy as np

from anequim import Anequim, QCConfig
from anequim.readers.modis import ModisL2Reader
from anequim.readers.viirs import ViirsL2Reader

from conftest import CENTER_LON, CENTER_LAT


def test_modis_reader_matches_and_reads(synthetic_modis_file):
    assert ModisL2Reader.matches(synthetic_modis_file)
    with ModisL2Reader(synthetic_modis_file) as reader:
        lon, lat = reader.get_navigation()
        wavelengths = reader.get_wavelengths()
        rrs_cube = reader.get_rrs_cube()
        flags = reader.get_quality_flags()
        assert lon.shape == (20, 20)
        assert sorted(wavelengths.tolist()) == [412, 443, 469, 488, 531, 547, 555, 645, 667, 678]
        assert rrs_cube.shape == (20, 20, 10)
        assert flags.shape == (20, 20)
        assert reader.get_platform_name() == "Aqua"


def test_viirs_reader_matches_and_reads(synthetic_viirs_file):
    assert ViirsL2Reader.matches(synthetic_viirs_file)
    with ViirsL2Reader(synthetic_viirs_file) as reader:
        wavelengths = reader.get_wavelengths()
        rrs_cube = reader.get_rrs_cube()
        assert sorted(wavelengths.tolist()) == [410, 443, 486, 551, 671]
        assert rrs_cube.shape == (20, 20, 5)
        assert reader.get_platform_name() == "SNPP"


def test_modis_reader_does_not_match_viirs_file(synthetic_viirs_file):
    assert not ModisL2Reader.matches(synthetic_viirs_file)


def test_viirs_reader_does_not_match_modis_file(synthetic_modis_file):
    assert not ViirsL2Reader.matches(synthetic_modis_file)


def test_anequim_get_rrs_with_modis(synthetic_modis_file):
    cube = Anequim.retrieve(
        files=synthetic_modis_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="MODIS",
        box_size=5,
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0),
    )
    assert cube.sensor == "MODIS"
    assert cube.n_pixels == 25
    assert cube.n_bands == 10
    assert cube.provenance.nominal_pixel_size_m == 1000.0


def test_anequim_get_rrs_with_viirs(synthetic_viirs_file):
    cube = Anequim.retrieve(
        files=synthetic_viirs_file,
        longitude=CENTER_LON,
        latitude=CENTER_LAT,
        time="2024-06-15T14:45:00Z",
        sensor="VIIRS",
        box_size=5,
        qc=QCConfig(min_valid_fraction=0.3, max_cv=1.0),
    )
    assert cube.sensor == "VIIRS"
    assert cube.n_bands == 5
    assert cube.provenance.nominal_pixel_size_m == 750.0
