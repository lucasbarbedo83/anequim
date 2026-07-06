"""Local file discovery helpers.

Anequim reads local files only (see :mod:`anequim.download` for the
planned, not-yet-implemented network side). These helpers turn a
directory, glob pattern, or explicit list into a clean, sorted list of
candidate granule paths.
"""

from __future__ import annotations

import glob
import os
from typing import Iterable, List, Sequence, Union

PathLike = Union[str, os.PathLike]

DEFAULT_EXTENSIONS = (".nc", ".nc4", ".h5", ".hdf")


def resolve_files(
    files: Union[PathLike, Sequence[PathLike]],
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
) -> List[str]:
    """Normalize a flexible ``files`` argument into a sorted list of
    absolute file paths.

    Accepts:
    - a single file path
    - a directory path (all files with a matching extension inside it)
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
            for name in sorted(os.listdir(item)):
                if name.lower().endswith(exts):
                    resolved.append(os.path.join(item, name))
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
