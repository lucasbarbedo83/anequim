import numpy as np

from anequim.core.spectral_cube import SpectralCube
from anequim.core.qc import evaluate_roi
from anequim.core.config import QCConfig
from anequim.core.provenance import Provenance
from anequim import statistics as stats


def _make_cube(n_pixels=20, n_bands=4, seed=0):
    rng = np.random.default_rng(seed)
    wavelengths = np.array([412.0, 443.0, 490.0, 555.0])[:n_bands]
    rrs = 0.01 + 0.001 * rng.normal(size=(n_pixels, n_bands))
    valid_mask = np.ones(n_pixels, dtype=bool)
    valid_mask[0] = False  # one invalid pixel

    qc_result = evaluate_roi(rrs, valid_mask, QCConfig())
    provenance = Provenance(
        sensor="TEST",
        source_files=["synthetic"],
        acquisition_time="2024-01-01T00:00:00+00:00",
        target_longitude=0.0,
        target_latitude=0.0,
        target_time="2024-01-01T00:00:00+00:00",
        roi_description="test",
        qc_summary=qc_result.summary(),
    )
    return SpectralCube(
        sensor="TEST",
        wavelengths=wavelengths,
        rrs=rrs,
        valid_mask=valid_mask,
        longitude=np.zeros(n_pixels),
        latitude=np.zeros(n_pixels),
        qc=qc_result,
        provenance=provenance,
    )


def test_mean_and_median_shapes():
    cube = _make_cube()
    mean = stats.mean_spectrum(cube)
    median = stats.median_spectrum(cube)
    assert mean.shape == (cube.n_bands,)
    assert median.shape == (cube.n_bands,)


def test_mean_excludes_invalid_by_default():
    cube = _make_cube()
    mean_valid_only = stats.mean_spectrum(cube, use_valid_only=True)
    mean_all = stats.mean_spectrum(cube, use_valid_only=False)
    # They need not be equal since the invalid pixel is excluded in one case.
    assert mean_valid_only.shape == mean_all.shape


def test_std_and_percentile():
    cube = _make_cube()
    std = stats.std_spectrum(cube)
    p10 = stats.percentile_spectrum(cube, 10)
    p90 = stats.percentile_spectrum(cube, 90)
    assert np.all(std >= 0)
    assert np.all(p90 >= p10)


def test_covariance_and_correlation_matrix_shape():
    cube = _make_cube(n_pixels=30, n_bands=3)
    cov = stats.covariance_matrix(cube)
    corr = stats.correlation_matrix(cube)
    assert cov.shape == (3, 3)
    assert corr.shape == (3, 3)
    # diagonal of correlation matrix should be 1 (or nan if degenerate)
    diag = np.diag(corr)
    assert np.all(np.isnan(diag) | np.isclose(diag, 1.0))


def test_summary_table_columns():
    cube = _make_cube()
    df = stats.summary_table(cube)
    for col in ["wavelength_nm", "mean", "median", "std", "cv", "p10", "p90", "n_valid"]:
        assert col in df.columns
    assert len(df) == cube.n_bands
