# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""One-shot JSON sidecar for metadata conformance.

Reads exactly one JSON request on stdin and writes exactly one JSON response on
stdout. Diagnostics go to stderr. Host applications that cannot import USD
in-process (for example the SimReady Blender add-on running on Blender's
Python 3.13) invoke this in a bundled interpreter.

Request::

    {
      "protocol_version": 1,
      "op": "metadata_conform",
      "source_usd": "<path>",
      "output_folder": "<path>",
      "metadata": {"author": "...", "asset_license": "...", "...": "..."},
      "thumbnail_source": "<path to png>",
      "replace_existing": true,
      "report_path": "<path>",
      "diagnostics_dir": "<path>"
    }

Health check::

    {"protocol_version": 1, "op": "ping"}

Exit codes: ``0`` success, ``1`` conformance failure, ``2`` malformed or
unsupported request.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from typing import Any

from .api import (
    STAGE_REQUEST,
    MetadataConformRequest,
    ResultError,
    run_metadata_conform,
)
from .protocol import PROTOCOL_VERSION
from .version import __version__

OP_METADATA_CONFORM = "metadata_conform"
OP_PING = "ping"

CODE_INVALID_JSON = "INVALID_JSON"
CODE_INVALID_REQUEST = "INVALID_REQUEST"
CODE_UNSUPPORTED_OP = "UNSUPPORTED_OP"
CODE_PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
CODE_INTERNAL_ERROR = "INTERNAL_ERROR"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_REQUEST = 2


def _error_response(op: str, code: str, detail: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "package_version": __version__,
        "op": op,
        "ok": False,
        "errors": [
            ResultError(code=code, stage=STAGE_REQUEST, detail=detail).to_dict()
        ],
    }


def handle_request(payload: Any) -> tuple[dict[str, Any], int]:
    """Turn one decoded request into a response body and an exit code."""
    if not isinstance(payload, dict):
        return (
            _error_response(
                "", CODE_INVALID_REQUEST, "request must be a JSON object"
            ),
            EXIT_BAD_REQUEST,
        )

    op = payload.get("op", OP_METADATA_CONFORM)
    if not isinstance(op, str) or not op:
        return (
            _error_response("", CODE_INVALID_REQUEST, "'op' must be a string"),
            EXIT_BAD_REQUEST,
        )

    requested_protocol = payload.get("protocol_version", PROTOCOL_VERSION)
    if requested_protocol != PROTOCOL_VERSION:
        return (
            _error_response(
                op,
                CODE_PROTOCOL_MISMATCH,
                f"unsupported protocol_version {requested_protocol!r}; "
                f"this sidecar speaks {PROTOCOL_VERSION}",
            ),
            EXIT_BAD_REQUEST,
        )

    if op == OP_PING:
        return (
            {
                "protocol_version": PROTOCOL_VERSION,
                "package_version": __version__,
                "op": OP_PING,
                "ok": True,
                "python": sys.version,
            },
            EXIT_OK,
        )

    if op != OP_METADATA_CONFORM:
        return (
            _error_response(op, CODE_UNSUPPORTED_OP, f"unsupported op {op!r}"),
            EXIT_BAD_REQUEST,
        )

    try:
        request = MetadataConformRequest.from_dict(payload)
    except ValueError as exc:
        return (
            _error_response(op, CODE_INVALID_REQUEST, str(exc)),
            EXIT_BAD_REQUEST,
        )

    try:
        # Library logging must not land on stdout: exactly one JSON object is
        # written there, and a stray print would make the response unparseable.
        with contextlib.redirect_stdout(sys.stderr):
            result = run_metadata_conform(
                request.source_usd,
                request.output_folder,
                metadata=request.metadata,
                thumbnail_source=request.thumbnail_source,
                replace_existing=request.replace_existing,
                report_path=request.report_path,
                diagnostics_dir=request.diagnostics_dir,
            )
    except Exception as exc:  # noqa: BLE001 - sidecar boundary
        return (
            _error_response(op, CODE_INTERNAL_ERROR, str(exc)),
            EXIT_FAILED,
        )

    body = result.to_dict()
    body["op"] = op
    return body, EXIT_OK if result.ok else EXIT_FAILED


def main(argv: list[str] | None = None, stdin: io.TextIOBase | None = None) -> int:
    parser = argparse.ArgumentParser(description="SimReady metadata conform sidecar")
    parser.add_argument(
        "--protocol-version",
        action="store_true",
        help="Print the protocol and package version, then exit.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.protocol_version:
        print(
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "package_version": __version__,
                }
            )
        )
        return EXIT_OK

    source = stdin if stdin is not None else sys.stdin
    raw = source.read()
    try:
        payload = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError as exc:
        body, code = _error_response("", CODE_INVALID_JSON, str(exc)), EXIT_BAD_REQUEST
    else:
        if payload is None:
            body, code = (
                _error_response("", CODE_INVALID_JSON, "empty request"),
                EXIT_BAD_REQUEST,
            )
        else:
            body, code = handle_request(payload)

    print(json.dumps(body))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
