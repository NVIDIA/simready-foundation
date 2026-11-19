# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Single-asset metadata conformance CLI.

    simready-metadata-conform source.usda out_folder --author "Asset Team" \
        --asset-license Apache-2.0 --category prop --source-file source.blend

Add ``--validate-profile`` to run a profile gate after conformance. That needs
the ``validate`` extra and does not change the conformance result; it only
reports the end state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import run_metadata_conform
from .core import STRING_FIELDS
from .version import __version__

# Provenance strings a caller may supply, mapped to their CLI flag names.
_STRING_FLAGS = tuple(sorted(STRING_FIELDS))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_usd", type=Path, help="Root USD of the source package.")
    parser.add_argument(
        "output_folder", type=Path, help="Destination package directory."
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Allow transactional replacement of an existing output folder.",
    )
    parser.add_argument(
        "--thumbnail-source",
        type=Path,
        default=None,
        help="PNG to install as the SR.002 thumbnail instead of discovering one.",
    )
    parser.add_argument("--qcode", default=None, help="Wikidata Q-Code override.")
    parser.add_argument("--report", type=Path, default=None, help="JSON report path.")
    parser.add_argument(
        "--diagnostics-dir",
        type=Path,
        default=None,
        help="Where to preserve staging output when a run fails.",
    )
    for name in _STRING_FLAGS:
        parser.add_argument(
            f"--{name.replace('_', '-')}",
            dest=name,
            default=None,
            help=f"SR.003 {name} value.",
        )
    parser.add_argument(
        "--validate-profile",
        default=None,
        help="Optional end-state profile gate (needs the 'validate' extra).",
    )
    parser.add_argument(
        "--validate-version", default="1.2.0", help="Version for --validate-profile."
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    metadata = {
        name: getattr(args, name)
        for name in _STRING_FLAGS
        if getattr(args, name) is not None
    }
    if args.qcode is not None:
        metadata["qcode"] = args.qcode

    result = run_metadata_conform(
        args.source_usd,
        args.output_folder,
        metadata=metadata,
        thumbnail_source=args.thumbnail_source,
        replace_existing=args.replace_existing,
        report_path=args.report,
        diagnostics_dir=args.diagnostics_dir,
    )

    payload = result.to_dict()
    if result.ok and args.validate_profile:
        from .validation import ValidatorUnavailableError, validate_asset

        try:
            validation = validate_asset(
                Path(result.output_usd),
                args.validate_profile,
                args.validate_version,
            )
        except ValidatorUnavailableError as exc:
            payload["validation"] = {"passed": None, "detail": str(exc)}
        else:
            payload["validation"] = validation.to_dict()

    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result.ok:
        for error in result.errors:
            print(f"{error.stage}/{error.code}: {error.detail}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
