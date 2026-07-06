"""Quality-flag bit definitions and mask construction.

Ocean Biology Processing Group (OBPG) Level-2 ocean color products
(SeaWiFS, MODIS, VIIRS, and PACE OCI) share a common 32-bit per-pixel
``l2_flags`` layout. The canonical bit -> name mapping below matches the
standard OBPG definition and is used as the default for any reader that
does not override it; however, every reader is expected to prefer the
``flag_meanings`` / ``flag_masks`` attributes actually present on its own
``l2_flags`` variable when available, and fall back to this table only if
those attributes are missing. This guards against silently mis-masking
pixels if a future sensor reorders or renames bits.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

import numpy as np

# Standard OBPG l2_flags bit layout (bit index -> flag name), used across
# SeaWiFS/MODIS/VIIRS/OCI Level-2 ocean products.
OBPG_L2_FLAGS: Dict[int, str] = {
    0: "ATMFAIL",
    1: "LAND",
    2: "PRODWARN",
    3: "HIGLINT",
    4: "HILT",
    5: "HISATZEN",
    6: "COASTZ",
    7: "SPARE",
    8: "STRAYLIGHT",
    9: "CLDICE",
    10: "COCCOLITH",
    11: "TURBIDW",
    12: "HISOLZEN",
    13: "SPARE2",
    14: "LOWLW",
    15: "CHLFAIL",
    16: "NAVWARN",
    17: "ABSAER",
    18: "SPARE3",
    19: "MAXAERITER",
    20: "MODGLINT",
    21: "CHLWARN",
    22: "ATMWARN",
    23: "SPARE4",
    24: "SEAICE",
    25: "NAVFAIL",
    26: "FILTER",
    27: "SPARE5",
    28: "BOWTIEDEL",
    29: "HIPOL",
    30: "PRODFAIL",
    31: "SPARE6",
}

OBPG_NAME_TO_BIT: Dict[str, int] = {name: bit for bit, name in OBPG_L2_FLAGS.items()}

#: Literature-typical exclusion set for open-ocean Rrs match-ups, following
#: the spirit of Bailey & Werdell (2006): reject clouds/ice, land, glint,
#: extreme geometry, stray light, and processing failures. This is a
#: default — stricter or looser sets are appropriate depending on the
#: study (e.g. coastal work may need to relax HIGLINT or COASTZ).
DEFAULT_EXCLUDED_FLAGS: Sequence[str] = (
    "ATMFAIL",
    "LAND",
    "HIGLINT",
    "HILT",
    "HISATZEN",
    "STRAYLIGHT",
    "CLDICE",
    "LOWLW",
    "CHLFAIL",
    "NAVFAIL",
    "NAVWARN",
    "FILTER",
    "SEAICE",
)


def flag_meanings_to_bit_map(flag_meanings: str, flag_masks: Iterable[int]) -> Dict[str, int]:
    """Build a {flag_name: bit_index} map from a granule's own
    ``flag_meanings`` (space-separated string) and ``flag_masks``
    (parallel array of bit-mask integers, each a power of two)
    attributes, as actually stored in the file.
    """
    names = flag_meanings.split()
    masks = list(flag_masks)
    if len(names) != len(masks):
        raise ValueError(
            f"flag_meanings has {len(names)} names but flag_masks has {len(masks)} values"
        )
    out = {}
    for name, mask in zip(names, masks):
        bit = int(mask).bit_length() - 1
        out[name] = bit
    return out


def build_exclusion_bitmask(
    flag_names: Sequence[str], name_to_bit: Optional[Dict[str, int]] = None
) -> int:
    """Combine named flags into a single bitmask suitable for a bitwise
    AND test against an ``l2_flags`` array.

    Unknown flag names are ignored with no error, since not every sensor
    defines every flag (e.g. COCCOLITH is not meaningful for all sensors).
    """
    mapping = name_to_bit or OBPG_NAME_TO_BIT
    mask = 0
    for name in flag_names:
        bit = mapping.get(name)
        if bit is not None:
            mask |= 1 << bit
    return mask


def flagged_mask(l2_flags: np.ndarray, exclusion_bitmask: int) -> np.ndarray:
    """Boolean array, True where a pixel trips any bit in
    ``exclusion_bitmask`` (i.e. should be excluded)."""
    l2_flags = np.asarray(l2_flags)
    return (l2_flags.astype(np.int64) & exclusion_bitmask) != 0


def flags_tripped_per_pixel(
    l2_flags: np.ndarray, name_to_bit: Optional[Dict[str, int]] = None
) -> np.ndarray:
    """Return an object array of the same shape as ``l2_flags`` where each
    element is a list of flag names tripped by that pixel. Intended for
    small ROI arrays (diagnostics), not full-scene use.
    """
    mapping = name_to_bit or OBPG_NAME_TO_BIT
    l2_flags = np.asarray(l2_flags)
    out = np.empty(l2_flags.shape, dtype=object)
    it = np.nditer(l2_flags, flags=["multi_index"])
    for value in it:
        idx = it.multi_index
        tripped = [name for name, bit in mapping.items() if (int(value) >> bit) & 1]
        out[idx] = tripped
    return out
