"""
Anequim — catching the ocean spectrum.
=======================================

A sensor-independent Python framework for retrieving ocean-color remote
sensing reflectance (Rrs) and associated atmospheric products from local
Level-2 satellite granules.

Philosophy: retrieve the spectrum first, at native sensor resolution,
with full provenance — everything else (harmonization, bio-optical
inversion) builds on that and is opt-in.

Quick start
-----------
>>> from anequim import Anequim
>>> cube = Anequim.retrieve(
...     files="data/PACE_OCI.20240615T144200.L2.OC_AOP.nc",
...     longitude=-70.5, latitude=41.3, time="2024-06-15T15:00:00Z",
...     sensor="OCI",
... )
>>> cube.spectrum_dataframe()
"""

# __version__ must be defined before importing submodules: some of them
# (e.g. core.provenance) import it back from this package during their
# own initialization.
__version__ = "0.1.0"

from .core.config import QCConfig, RetrievalConfig
from .core.exceptions import (
    AnequimError,
    UnsupportedSensorError,
    NotImplementedSensorError,
    GranuleFormatError,
    OutsideTimeWindowError,
    OutsideSpatialDomainError,
    NoValidPixelsError,
    InsufficientValidFractionError,
    ROIError,
    HarmonizationNotAvailableError,
    AlgorithmNotAvailableError,
    DownloadNotAvailableError,
)
from .core.provenance import Provenance
from .core.qc import QCResult, evaluate_roi
from .core.spectral_cube import SpectralCube
from .core.anequim import Anequim
from .roi import ROI, ROISelection, PixelROI, RectangularROI, CircularROI, BoundingBoxROI, PolygonROI

__all__ = [
    "__version__",
    "Anequim",
    "QCConfig",
    "RetrievalConfig",
    "SpectralCube",
    "QCResult",
    "evaluate_roi",
    "Provenance",
    "AnequimError",
    "UnsupportedSensorError",
    "NotImplementedSensorError",
    "GranuleFormatError",
    "OutsideTimeWindowError",
    "OutsideSpatialDomainError",
    "NoValidPixelsError",
    "InsufficientValidFractionError",
    "ROIError",
    "HarmonizationNotAvailableError",
    "AlgorithmNotAvailableError",
    "DownloadNotAvailableError",
    "ROI",
    "ROISelection",
    "PixelROI",
    "RectangularROI",
    "CircularROI",
    "BoundingBoxROI",
    "PolygonROI",
]
