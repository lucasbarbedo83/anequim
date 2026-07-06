import numpy as np

from anequim.roi.pixel import PixelROI
from anequim.roi.rectangular import RectangularROI
from anequim.roi.circular import CircularROI
from anequim.roi.bbox import BoundingBoxROI


def _grid():
    lon = np.linspace(-1.0, 1.0, 11)
    lat = np.linspace(-1.0, 1.0, 11)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    return lon_grid, lat_grid


def test_pixel_roi_selects_one_pixel():
    lon_grid, lat_grid = _grid()
    roi = PixelROI(0.0, 0.0)
    sel = roi.select(lon_grid, lat_grid)
    assert sel.n_selected == 1
    assert sel.center_row is not None and sel.center_col is not None


def test_rectangular_roi_box_size():
    lon_grid, lat_grid = _grid()
    roi = RectangularROI(0.0, 0.0, box_size=5)
    sel = roi.select(lon_grid, lat_grid)
    assert sel.n_selected == 25


def test_rectangular_roi_clips_at_edge():
    lon_grid, lat_grid = _grid()
    roi = RectangularROI(-1.0, -1.0, box_size=5)
    sel = roi.select(lon_grid, lat_grid)
    # centered near a corner, box should be clipped smaller than 25
    assert 0 < sel.n_selected < 25


def test_circular_roi_selects_within_radius():
    lon_grid, lat_grid = _grid()
    roi = CircularROI(0.0, 0.0, radius_km=150.0)
    sel = roi.select(lon_grid, lat_grid)
    assert sel.n_selected > 0
    # every pixel outside the mask should indeed be farther than the radius
    from anequim.geometry.distance import haversine_km

    distances = haversine_km(lon_grid, lat_grid, 0.0, 0.0)
    assert np.all(distances[sel.mask] <= 150.0)
    assert np.all(distances[~sel.mask] > 150.0)


def test_bbox_roi_basic():
    lon_grid, lat_grid = _grid()
    roi = BoundingBoxROI(lon_min=-0.5, lon_max=0.5, lat_min=-0.5, lat_max=0.5)
    sel = roi.select(lon_grid, lat_grid)
    assert sel.n_selected > 0
    assert np.all(lon_grid[sel.mask] >= -0.5)
    assert np.all(lon_grid[sel.mask] <= 0.5)


def test_bbox_roi_no_coverage():
    lon_grid, lat_grid = _grid()
    roi = BoundingBoxROI(lon_min=50, lon_max=51, lat_min=50, lat_max=51)
    sel = roi.select(lon_grid, lat_grid)
    assert sel.n_selected == 0
    assert "no coverage" in sel.description
