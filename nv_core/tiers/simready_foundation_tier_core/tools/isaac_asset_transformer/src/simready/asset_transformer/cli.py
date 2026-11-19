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
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

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
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    input_stage = args.input_stage.expanduser().resolve()
    output_package = args.output_package.expanduser().resolve()
    if not input_stage.is_file():
        logging.error("Input USD does not exist: %s", input_stage)
        return 2
    if output_package.exists() and not args.overwrite:
        logging.error("Output package already exists: %s. Pass --overwrite to replace it.", output_package)
        return 2
    if input_stage.is_relative_to(output_package):
        parser.error("Output package must not contain the input USD.")

    interface_name = args.interface_name or f"{input_stage.stem}.usda"
    if Path(interface_name).name != interface_name or interface_name in {".", ".."}:
        parser.error("Interface name must be a filename within the output package.")
    try:
        output_package.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=f".{output_package.name}-", dir=output_package.parent) as temporary:
            staged_package = Path(temporary) / "package"
            report = transform_package(
                str(input_stage),
                staged_package,
                profile=args.profile,
                interface_asset_name=interface_name,
            )
            failures = [result for result in report.results if not result.success]
            composition_errors = list(getattr(report, "composition_errors", None) or [])
            if failures or composition_errors:
                for result in failures:
                    logging.error("%s: %s", result.rule.name, result.error)
                for error in composition_errors:
                    logging.error("Unresolved composition arc: %s", error)
                # Keep diagnostics outside a failed package; staging is discarded.
                report_path = (
                    (args.report or output_package.with_name(output_package.name + ".failed-transform.json"))
                    .expanduser()
                    .resolve()
                )
                if report_path.is_relative_to(output_package):
                    report_path = output_package.with_name(output_package.name + ".failed-transform.json")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report.to_json() + "\n", encoding="utf-8")
                logging.error("Transformation failed; report: %s", report_path)
                return 1

            def published_paths(value):
                if isinstance(value, str):
                    return value.replace(str(staged_package), str(output_package))
                if isinstance(value, list):
                    return [published_paths(item) for item in value]
                if isinstance(value, dict):
                    return {key: published_paths(item) for key, item in value.items()}
                return value

            report_data = published_paths(report.to_dict())
            previous_package = Path(temporary) / "previous"
            if output_package.exists():
                if not args.overwrite:
                    raise FileExistsError(f"Output package already exists: {output_package}")
                output_package.rename(previous_package)
            try:
                staged_package.rename(output_package)
            except OSError:
                if previous_package.exists():
                    previous_package.rename(output_package)
                raise
        report_path = (args.report or output_package / "transform_report.json").expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_data, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        logging.error("Transformation failed: %s", exc)
        return 1
    logging.info("Generated %s", report_data["output_stage_path"])
    logging.info("Wrote %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
