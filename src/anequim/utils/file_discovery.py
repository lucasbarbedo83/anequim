"""Local file discovery helpers.

Anequim reads local files only (aside from the opt-in NASA Earthdata
download path in :mod:`anequim.download`). These helpers turn a
directory, glob pattern, or explicit list into a clean, sorted list of
candidate granule paths.

Most sensors' Level-2 granules are a single file, but some (Sentinel-3
OLCI's SAFE-format products) are a *directory* containing many
per-variable NetCDF files that together make up one granule. This
module treats a directory as "one granule" rather than "a folder of
granule files" when it looks like a SAFE container (i.e. contains an
``xfdumanifest.xml`` manifest, the standard ESA SAFE format marker) —
otherwise a directory is treated as a folder of one-file-per-granule
products, as before.
"""

from __future__ import annotations

import glob
import os
from typing import Iterable, List, Sequence, Union

PathLike = Union[str, os.PathLike]

DEFAULT_EXTENSIONS = (".nc", ".nc4", ".h5", ".hdf")

#: Presence of this file marks a directory as a single ESA SAFE-format
#: granule (e.g. Sentinel-3 OLCI L2 WFR products) rather than a folder
#: containing multiple separate granule files.
SAFE_MANIFEST_NAME = "xfdumanifest.xml"


def _is_safe_granule_directory(path: str) -> bool:
    return os.path.isfile(os.path.join(path, SAFE_MANIFEST_NAME))


def resolve_files(
    files: Union[PathLike, Sequence[PathLike]],
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
) -> List[str]:
    """Normalize a flexible ``files`` argument into a sorted list of
    absolute granule paths (each either a single file, or a SAFE-format
    granule directory — see module docstring).

    Accepts:
    - a single file path, or a single SAFE granule directory path
    - a directory containing multiple granules (files and/or SAFE
      granule subdirectories, or a mix of both)
    - a glob pattern (e.g. ``"data/*.nc"``)
    - a list/tuple mixing any of the above
    """
    if isinstance(files, (str, os.PathLike)):
        candidates = [files]
    else:
        candidates = list(files)

    resolved: List[str] = []
    exts = tuple(e.lower() for e in extensions)

    for item in candidates:
        item = os.fspath(item)
        if os.path.isdir(item):
            if _is_safe_granule_directory(item):
                resolved.append(item)
            else:
                for name in sorted(os.listdir(item)):
                    sub = os.path.join(item, name)
                    if os.path.isdir(sub):
                        if _is_safe_granule_directory(sub):
                            resolved.append(sub)
                        # Plain subdirectories that aren't SAFE granules
                        # are not recursed into further.
                    elif name.lower().endswith(exts):
                        resolved.append(sub)
        elif any(ch in item for ch in "*?[]"):
            resolved.extend(sorted(glob.glob(item)))
        elif os.path.isfile(item):
            resolved.append(item)
        else:
            raise FileNotFoundError(f"No such file, directory, or glob match: {item}")

    # De-duplicate while preserving order, then return absolute paths.
    seen = set()
    out = []
    for path in resolved:
        abspath = os.path.abspath(path)
        if abspath not in seen:
            seen.add(abspath)
            out.append(abspath)
    return out
