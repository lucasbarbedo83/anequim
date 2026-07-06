"""Command-line interface: ``anequim --files ... --lon ... --lat ... --time ...``"""

from __future__ import annotations

import argparse
import sys

from .core.anequim import Anequim
from .core.config import QCConfig
from .core.exceptions import AnequimError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anequim",
        description="Retrieve Rrs close to a point and time from local ocean color granules.",
    )
    parser.add_argument("--files", nargs="+", required=True, help="Granule file(s), directory, or glob pattern(s)")
    parser.add_argument("--sensor", required=True, help="Sensor alias, e.g. OCI")
    parser.add_argument("--lon", type=float, required=True, help="Target longitude (decimal degrees)")
    parser.add_argument("--lat", type=float, required=True, help="Target latitude (decimal degrees)")
    parser.add_argument("--time", required=True, help="Target time, ISO-8601 (e.g. 2024-06-15T15:00:00Z)")
    parser.add_argument("--window-hours", type=float, default=3.0, help="Time window half-width, hours")
    parser.add_argument("--box-size", type=int, default=5, help="Square ROI side length in pixels (odd)")
    parser.add_argument("--min-valid-fraction", type=float, default=0.5)
    parser.add_argument("--max-cv", type=float, default=0.15)
    parser.add_argument("--output", "-o", default=None, help="Write representative spectrum to this CSV path")
    parser.add_argument(
        "--pixel-output", default=None, help="Also write the full per-pixel table to this CSV path"
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    qc = QCConfig(min_valid_fraction=args.min_valid_fraction, max_cv=args.max_cv)

    try:
        cube = Anequim.retrieve(
            files=args.files,
            longitude=args.lon,
            latitude=args.lat,
            time=args.time,
            sensor=args.sensor,
            time_window_hours=args.window_hours,
            box_size=args.box_size,
            qc=qc,
        )
    except AnequimError as exc:
        print(f"anequim: {exc}", file=sys.stderr)
        return 1

    print(cube)
    print(cube.spectrum_dataframe().to_string(index=False))
    print("QC summary:", cube.summary())

    if args.output:
        cube.to_csv(args.output, kind="spectrum")
        print(f"Wrote spectrum to {args.output}")
    if args.pixel_output:
        cube.to_csv(args.pixel_output, kind="pixel")
        print(f"Wrote pixel table to {args.pixel_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
