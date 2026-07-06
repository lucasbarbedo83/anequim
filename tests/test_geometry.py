import numpy as np
import pytest

from anequim.geometry.distance import haversine_km, bounding_box_contains
from anequim.geometry.nearest import find_nearest_pixel, box_slice


def test_haversine_zero_distance():
    assert haversine_km(10.0, 20.0, 10.0, 20.0) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance():
    # Roughly 1 degree of longitude at the equator is about 111.19 km.
    d = haversine_km(0.0, 0.0, 1.0, 0.0)
    assert d == pytest.approx(111.19, rel=0.01)


def test_haversine_vectorized():
    lon1 = np.array([0.0, 0.0])
    lat1 = np.array([0.0, 10.0])
    d = haversine_km(lon1, lat1, 0.0, 0.0)
    assert d[0] == pytest.approx(0.0, abs=1e-6)
    assert d[1] > 0


def test_bounding_box_contains_simple():
    assert bounding_box_contains(5, 5, 0, 10, 0, 10)
    assert not bounding_box_contains(15, 5, 0, 10, 0, 10)


def test_bounding_box_contains_antimeridian():
    # box spans 170 -> -170 (crossing the antimeridian)
    assert bounding_box_contains(175, 0, 170, -170, -10, 10)
    assert bounding_box_contains(-175, 0, 170, -170, -10, 10)
    assert not bounding_box_contains(0, 0, 170, -170, -10, 10)


def test_find_nearest_pixel_regular_grid():
    lon = np.array([[0.0, 1.0, 2.0], [0.0, 1.0, 2.0]])
    lat = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
    result = find_nearest_pixel(lon, lat, 1.05, 0.95)
    assert result is not None
    assert (result.row, result.col) == (1, 1)


def test_find_nearest_pixel_out_of_range():
    lon = np.array([[0.0, 1.0], [0.0, 1.0]])
    lat = np.array([[0.0, 0.0], [1.0, 1.0]])
    result = find_nearest_pixel(lon, lat, 50.0, 50.0, max_search_radius_km=10.0)
    assert result is None


def test_box_slice_clips_to_bounds():
    r, c = box_slice(0, 0, 2, (10, 10))
    assert r == slice(0, 3)
    assert c == slice(0, 3)

    r, c = box_slice(9, 9, 2, (10, 10))
    assert r == slice(7, 10)
    assert c == slice(7, 10)

    r, c = box_slice(5, 5, 2, (10, 10))
    assert r == slice(3, 8)
    assert c == slice(3, 8)
