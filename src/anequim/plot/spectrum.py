"""Plotting helpers for SpectralCube results.

``plot_spectrum`` is a real, working implementation (matplotlib is an
optional dependency: ``pip install anequim[plot]``). Other plot types
(multi-sensor comparison overlays, pixel maps, time series) are stubbed
for a future release — see the TODOs below — since this build pass
focuses on core retrieval, ROI, and statistics.
"""

from __future__ import annotations

from typing import Optional, Sequence

from ..core.spectral_cube import SpectralCube


def plot_spectrum(
    cube: SpectralCube,
    ax=None,
    show_std: bool = True,
    show_pixels: bool = False,
    label: Optional[str] = None,
    **plot_kwargs,
):
    """Plot a SpectralCube's representative Rrs spectrum.

    Parameters
    ----------
    cube:
        The SpectralCube to plot.
    ax:
        Existing matplotlib Axes to draw on; a new figure/axes is created
        if not given.
    show_std:
        If True, shade +/- one standard deviation around the spectrum.
    show_pixels:
        If True, also draw each individual valid pixel's spectrum as a
        thin line, for a quick look at within-ROI spread.
    label:
        Legend label; defaults to the cube's sensor name.

    Returns
    -------
    matplotlib.axes.Axes
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
        raise ImportError(
            "matplotlib is required for plotting; install anequim[plot]"
        ) from exc

    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4.5))

    wl = cube.wavelengths
    spectrum = cube.spectrum
    label = label or cube.sensor

    if show_pixels:
        pixel_values = cube.rrs[cube.valid_mask]
        for row in pixel_values:
            ax.plot(wl, row, color="gray", alpha=0.25, linewidth=0.5, zorder=1)

    (line,) = ax.plot(wl, spectrum, label=label, linewidth=2.0, zorder=3, **plot_kwargs)

    if show_std:
        std = cube.spectrum_std
        ax.fill_between(
            wl, spectrum - std, spectrum + std, color=line.get_color(), alpha=0.2, zorder=2
        )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel(r"$R_{rs}$ (sr$^{-1}$)")
    ax.set_title(f"{cube.sensor} Rrs — {cube.provenance.acquisition_time or 'unknown time'}")
    ax.legend()
    ax.grid(alpha=0.3)
    return ax


def compare_spectra(cubes: Sequence[SpectralCube], ax=None):
    """Not yet implemented. Planned: overlay multiple SpectralCubes
    (e.g. from different sensors matched to the same point/time) on one
    axes, using :func:`plot_spectrum` per cube plus consistent styling
    and a shared legend, for cross-sensor comparison figures.
    """
    raise NotImplementedError(
        "compare_spectra is planned but not yet implemented; call plot_spectrum() "
        "once per cube on a shared `ax` in the meantime."
    )


def plot_roi_map(cube: SpectralCube, ax=None):
    """Not yet implemented. Planned: a small map (e.g. via cartopy or a
    simple scatter of cube.longitude/cube.latitude colored by validity/
    flag status) showing exactly which pixels contributed to a match-up.
    """
    raise NotImplementedError("plot_roi_map is planned but not yet implemented.")
