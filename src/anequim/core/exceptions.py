"""Exception hierarchy for anequim."""


class AnequimError(Exception):
    """Base class for all anequim errors."""


class UnsupportedSensorError(AnequimError):
    """Raised when a sensor name/granule cannot be matched to a registered
    :class:`~anequim.readers.base.SensorReader`."""


class NotImplementedSensorError(UnsupportedSensorError):
    """Raised by a registered but not-yet-implemented sensor reader
    (e.g. OLCI, VIIRS, MODIS placeholders)."""


class GranuleFormatError(AnequimError):
    """Raised when a granule is missing groups/variables expected by the
    reader that claims to support it."""


class OutsideTimeWindowError(AnequimError):
    """Raised/used internally when a granule's overpass time falls outside
    the requested temporal match-up window."""


class OutsideSpatialDomainError(AnequimError):
    """Raised when the requested location/ROI does not intersect a
    granule's geolocation footprint."""


class NoValidPixelsError(AnequimError):
    """Raised when quality control leaves zero usable pixels."""


class InsufficientValidFractionError(NoValidPixelsError):
    """Raised when the valid-pixel fraction is below the configured
    minimum (see :class:`anequim.core.config.QCConfig`)."""


class ROIError(AnequimError):
    """Raised for invalid or unsatisfiable region-of-interest requests."""


class HarmonizationNotAvailableError(AnequimError):
    """Raised by harmonization utilities that are currently stubs."""


class AlgorithmNotAvailableError(AnequimError):
    """Raised by bio-optical algorithm utilities that are currently stubs."""


class DownloadNotAvailableError(AnequimError):
    """Raised by the download module, which is a stub — anequim reads
    local files only in this release."""
