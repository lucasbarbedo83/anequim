import numpy as np
import pytest

from anequim.core.flags import (
    OBPG_NAME_TO_BIT,
    build_exclusion_bitmask,
    flagged_mask,
    flag_meanings_to_bit_map,
)
from anequim.core.config import QCConfig
from anequim.core.qc import evaluate_roi
from anequim.core.exceptions import NoValidPixelsError, InsufficientValidFractionError


def test_flag_meanings_to_bit_map():
    mapping = flag_meanings_to_bit_map("ATMFAIL LAND HIGLINT", [1, 2, 8])
    assert mapping == {"ATMFAIL": 0, "LAND": 1, "HIGLINT": 3}


def test_build_exclusion_bitmask_default_table():
    mask = build_exclusion_bitmask(["ATMFAIL", "LAND"])
    assert mask == (1 << OBPG_NAME_TO_BIT["ATMFAIL"]) | (1 << OBPG_NAME_TO_BIT["LAND"])


def test_build_exclusion_bitmask_ignores_unknown():
    mask = build_exclusion_bitmask(["ATMFAIL", "NOT_A_REAL_FLAG"])
    assert mask == (1 << OBPG_NAME_TO_BIT["ATMFAIL"])


def test_flagged_mask():
    flags = np.array([0, 1, 2, 3])
    mask = flagged_mask(flags, exclusion_bitmask=1)
    np.testing.assert_array_equal(mask, [False, True, False, True])


def test_evaluate_roi_all_valid_homogeneous():
    values = np.tile([0.01, 0.02, 0.03], (9, 1)) + np.random.default_rng(0).normal(
        scale=1e-5, size=(9, 3)
    )
    valid = np.ones(9, dtype=bool)
    qc = QCConfig(min_valid_fraction=0.5, max_cv=0.5)
    result = evaluate_roi(values, valid, qc)
    assert result.n_valid == 9
    assert result.passed_valid_fraction
    assert result.homogeneous
    assert result.spectrum.shape == (3,)


def test_evaluate_roi_insufficient_valid_fraction():
    values = np.ones((10, 2))
    valid = np.zeros(10, dtype=bool)
    valid[:2] = True  # only 20% valid
    qc = QCConfig(min_valid_fraction=0.5)
    result = evaluate_roi(values, valid, qc)
    assert not result.passed_valid_fraction

    with pytest.raises(InsufficientValidFractionError):
        evaluate_roi(values, valid, qc, raise_on_failure=True)


def test_evaluate_roi_no_valid_pixels_raises():
    values = np.ones((5, 2))
    valid = np.zeros(5, dtype=bool)
    qc = QCConfig()
    with pytest.raises(NoValidPixelsError):
        evaluate_roi(values, valid, qc, raise_on_failure=True)

    result = evaluate_roi(values, valid, qc, raise_on_failure=False)
    assert result.n_valid == 0
    assert np.all(np.isnan(result.spectrum))


def test_evaluate_roi_detects_heterogeneity():
    rng = np.random.default_rng(1)
    values = rng.normal(loc=0.02, scale=0.02, size=(20, 3))  # high relative spread
    valid = np.ones(20, dtype=bool)
    qc = QCConfig(max_cv=0.05)
    result = evaluate_roi(values, valid, qc)
    assert not result.homogeneous


def test_evaluate_roi_outlier_trimming_changes_result():
    values = np.full((10, 1), 0.02)
    values[0, 0] = 5.0  # extreme outlier
    valid = np.ones(10, dtype=bool)

    qc_no_trim = QCConfig(exclude_outliers=False, max_cv=10.0)
    qc_trim = QCConfig(exclude_outliers=True, outlier_n_std=1.0, max_cv=10.0)

    result_no_trim = evaluate_roi(values, valid, qc_no_trim)
    result_trim = evaluate_roi(values, valid, qc_trim)

    assert result_trim.spectrum[0] < result_no_trim.spectrum[0]
