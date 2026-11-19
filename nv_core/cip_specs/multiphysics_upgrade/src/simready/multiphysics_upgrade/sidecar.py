# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""One-shot JSON sidecar for host applications such as the Blender add-on.

Reads exactly one JSON request object from stdin and writes exactly one JSON
response object to stdout. Everything else, including USD and library chatter,
belongs on stderr. The process is deliberately single-shot: the host pays a
process start per transformation and gets full crash and dependency isolation
in return.

Request::

    {
      "protocol_version": 1,
      "op": "neutral_to_runtimes",
      "source_usd": "<path>",
      "output_folder": "<path>",
      "replace_existing": true,
      "report_path": "<path>",
      "diagnostics_dir": "<path>"
    }

Response::

    {
      "protocol_version": 1,
      "package_version": "0.1.0",
      "ok": false,
      "errors": [{"code": "...", "stage": "...", "detail": "...", "paths": []}],
      ...
    }
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from typing import Any

from .api import (
    PROTOCOL_VERSION,
    STAGE_REQUEST,
    STAGE_SETUP,
    NeutralToRuntimesRequest,
    ResultError,
    run_neutral_to_runtimes,
)
from .version import __version__

OP_NEUTRAL_TO_RUNTIMES = "neutral_to_runtimes"
OP_PING = "ping"

CODE_INVALID_JSON = "INVALID_JSON"
CODE_INVALID_REQUEST = "INVALID_REQUEST"
CODE_UNSUPPORTED_OP = "UNSUPPORTED_OP"
CODE_PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
CODE_INTERNAL_ERROR = "INTERNAL_ERROR"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_REQUEST = 2


def _error_response(code: str, stage: str, detail: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "package_version": __version__,
        "ok": False,
        "errors": [ResultError(code=code, stage=stage, detail=detail).to_dict()],
    }


def _ping_response() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "package_version": __version__,
        "ok": True,
        "op": OP_PING,
        "python": sys.version.split()[0],
        "errors": [],
    }


def handle_request(payload: Any) -> tuple[dict[str, Any], int]:
    """Route one decoded request payload to its handler.

    Returns:
        The response object and the process exit code to use.
    """
    if not isinstance(payload, dict):
        return (
            _error_response(
                CODE_INVALID_REQUEST,
                STAGE_REQUEST,
                f"request must be a JSON object, got {type(payload).__name__}",
            ),
            EXIT_BAD_REQUEST,
        )

    requested_protocol = payload.get("protocol_version", PROTOCOL_VERSION)
    if requested_protocol != PROTOCOL_VERSION:
        return (
            _error_response(
                CODE_PROTOCOL_MISMATCH,
                STAGE_SETUP,
                f"sidecar speaks protocol {PROTOCOL_VERSION}, host requested {requested_protocol}",
            ),
            EXIT_BAD_REQUEST,
        )

    op = payload.get("op", OP_NEUTRAL_TO_RUNTIMES)
    if op == OP_PING:
        return _ping_response(), EXIT_OK
    if op != OP_NEUTRAL_TO_RUNTIMES:
        return (
            _error_response(CODE_UNSUPPORTED_OP, STAGE_REQUEST, f"unsupported op: {op}"),
            EXIT_BAD_REQUEST,
        )

    try:
        request = NeutralToRuntimesRequest.from_dict(payload)
    except ValueError as exc:
        return (
            _error_response(CODE_INVALID_REQUEST, STAGE_REQUEST, str(exc)),
            EXIT_BAD_REQUEST,
        )

    try:
        # Library progress output must not corrupt the single stdout response.
        with contextlib.redirect_stdout(sys.stderr):
            result = run_neutral_to_runtimes(
                request.source_usd,
                request.output_folder,
                replace_existing=request.replace_existing,
                report_path=request.report_path,
                diagnostics_dir=request.diagnostics_dir,
            )
    except Exception as exc:  # noqa: BLE001 - process boundary
        return (
            _error_response(CODE_INTERNAL_ERROR, STAGE_SETUP, f"{type(exc).__name__}: {exc}"),
            EXIT_FAILED,
        )

    response = result.to_dict()
    response["op"] = OP_NEUTRAL_TO_RUNTIMES
    return response, EXIT_OK if result.ok else EXIT_FAILED


def main(argv: list[str] | None = None, stdin: io.TextIOBase | None = None) -> int:
    parser = argparse.ArgumentParser(description="SimReady multiphysics one-shot JSON sidecar")
    parser.add_argument(
        "--protocol-version",
        action="store_true",
        help="Print the supported protocol and package versions, then exit.",
    )
    args = parser.parse_args([] if argv is None else argv)

    if args.protocol_version:
        print(json.dumps({"protocol_version": PROTOCOL_VERSION, "package_version": __version__}))
        return EXIT_OK

    raw = (stdin or sys.stdin).read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps(_error_response(CODE_INVALID_JSON, STAGE_REQUEST, str(exc))))
        return EXIT_BAD_REQUEST

    response, code = handle_request(payload)
    print(json.dumps(response))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
