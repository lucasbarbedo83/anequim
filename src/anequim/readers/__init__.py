from .base import SensorReader
from .pace_oci import PaceOciL2Reader
from .olci import OlciL2Reader
from .viirs import ViirsL2Reader
from .modis import ModisL2Reader
from .registry import READERS, reader_for_sensor_name, detect_reader, open_reader

__all__ = [
    "SensorReader",
    "PaceOciL2Reader",
    "OlciL2Reader",
    "ViirsL2Reader",
    "ModisL2Reader",
    "READERS",
    "reader_for_sensor_name",
    "detect_reader",
    "open_reader",
]
