"""Quickstart: retrieve an Rrs spectrum from a (synthetic, for this demo)
PACE OCI granule.

Run with:
    python examples/quickstart.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from anequim import Anequim, QCConfig  # noqa: E402
from make_synthetic_pace_file import make_synthetic_pace_oci_file  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        granule_path = os.path.join(tmp, "PACE_OCI.20240615T144200.L2.OC_AOP.nc")
        make_synthetic_pace_oci_file(granule_path, center_lon=-70.5, center_lat=41.3)

        cube = Anequim.retrieve(
            files=granule_path,
            longitude=-70.5,
            latitude=41.3,
            time="2024-06-15T14:45:00Z",
            sensor="OCI",
            time_window_hours=3.0,
            box_size=5,
            qc=QCConfig(
                min_valid_fraction=0.5,
                max_cv=0.25,
                # Exclude near-zero-signal bands (e.g. the far red/NIR edge)
                # from the CV homogeneity check, since std/mean blows up
                # there even for an otherwise spatially uniform ROI.
                min_signal_for_cv=0.0005,
            ),
        )

        print(cube)
        print()
        print(cube.spectrum_dataframe().to_string(index=False))
        print()
        print("Summary:", cube.summary())
        print()
        print("Reliable match-up:", cube.is_reliable())


if __name__ == "__main__":
    main()
