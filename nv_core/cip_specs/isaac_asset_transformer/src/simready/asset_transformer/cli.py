# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Command-line interface for standalone USD package transformation."""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

from .api import transform_package


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_stage", type=Path, help="Root USD stage to transform")
    parser.add_argument("output_package", type=Path, help="New output package directory")
    parser.add_argument(
        "--profile",
        default="simready_physx_to_isaac_prop",
        help=(
            "Bundled transform name (simready_physx_to_isaac_prop or "
            "simready_physx_to_isaac_robot) or profile JSON path"
        ),
    )
    parser.add_argument("--interface-name", help="Generated root layer filename")
    parser.add_argument("--report", type=Path, help="Report path; defaults inside output package")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output package")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    input_stage = args.input_stage.expanduser().resolve()
    output_package = args.output_package.expanduser().resolve()
    if not input_stage.is_file():
        raise FileNotFoundError(f"Input USD does not exist: {input_stage}")
    if output_package.exists():
        if not args.overwrite:
            raise FileExistsError(f"Output package already exists: {output_package}. Pass --overwrite to replace it.")
        shutil.rmtree(output_package)

    interface_name = args.interface_name or f"{input_stage.stem}.usda"
    report = transform_package(
        str(input_stage),
        output_package,
        profile=args.profile,
        interface_asset_name=interface_name,
    )
    report_path = (args.report or output_package / "transform_report.json").expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.to_json() + "\n", encoding="utf-8")

    failures = [result for result in report.results if not result.success]
    if failures:
        for result in failures:
            logging.error("%s: %s", result.rule.name, result.error)
        return 1
    logging.info("Generated %s", report.output_stage_path)
    logging.info("Wrote %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
