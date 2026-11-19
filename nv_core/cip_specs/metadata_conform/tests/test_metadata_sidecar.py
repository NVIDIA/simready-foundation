# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""JSON sidecar protocol: one object in, exactly one object out."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from metadata_fixtures import COMPLETE_METADATA, write_metadata_package, write_png

from simready.metadata_conform import PROTOCOL_VERSION, __version__
from simready.metadata_conform.sidecar import (
    CODE_INVALID_JSON,
    CODE_INVALID_REQUEST,
    CODE_PROTOCOL_MISMATCH,
    CODE_UNSUPPORTED_OP,
    EXIT_BAD_REQUEST,
    EXIT_FAILED,
    EXIT_OK,
    OP_METADATA_CONFORM,
    handle_request,
    main,
)


def _run(payload, capsys) -> tuple[dict, int]:
    code = main(argv=[], stdin=io.StringIO(json.dumps(payload)))
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected one stdout line, got {lines}"
    return json.loads(lines[0]), code


def _source_package(root: Path) -> Path:
    asset = write_metadata_package(root)
    write_png(asset.parent / ".thumbs" / f"{asset.name}.png")
    return asset


def test_ping_reports_versions_without_touching_an_asset(capsys):
    body, code = _run({"protocol_version": PROTOCOL_VERSION, "op": "ping"}, capsys)

    assert code == EXIT_OK
    assert body["ok"] is True
    assert body["op"] == "ping"
    assert body["protocol_version"] == PROTOCOL_VERSION
    assert body["package_version"] == __version__
    assert body["python"] == sys.version


def test_conform_op_writes_exactly_one_json_object(tmp_path, capsys):
    asset = _source_package(tmp_path / "source")
    output = tmp_path / "dest" / "simready_usd"

    body, code = _run(
        {
            "protocol_version": PROTOCOL_VERSION,
            "op": OP_METADATA_CONFORM,
            "source_usd": str(asset),
            "output_folder": str(output),
            "metadata": dict(COMPLETE_METADATA),
        },
        capsys,
    )

    assert code == EXIT_OK
    assert body["ok"] is True
    assert body["op"] == OP_METADATA_CONFORM
    assert Path(body["output_usd"]).is_file()


def test_op_defaults_to_metadata_conform(tmp_path, capsys):
    asset = _source_package(tmp_path / "source")

    body, code = _run(
        {
            "source_usd": str(asset),
            "output_folder": str(tmp_path / "dest" / "simready_usd"),
            "metadata": dict(COMPLETE_METADATA),
        },
        capsys,
    )

    assert code == EXIT_OK
    assert body["op"] == OP_METADATA_CONFORM


def test_conformance_failure_exits_one_with_structured_errors(tmp_path, capsys):
    asset = write_metadata_package(tmp_path / "source")

    body, code = _run(
        {
            "op": OP_METADATA_CONFORM,
            "source_usd": str(asset),
            "output_folder": str(tmp_path / "dest" / "simready_usd"),
            "metadata": dict(COMPLETE_METADATA),
        },
        capsys,
    )

    assert code == EXIT_FAILED
    assert body["ok"] is False
    assert body["errors"]
    assert all({"code", "stage", "detail", "paths"} <= set(e) for e in body["errors"])


def test_protocol_mismatch_is_a_bad_request(capsys):
    body, code = _run({"protocol_version": 99, "op": "ping"}, capsys)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_PROTOCOL_MISMATCH


def test_unsupported_op_is_a_bad_request(capsys):
    body, code = _run({"op": "explode"}, capsys)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_UNSUPPORTED_OP


@pytest.mark.parametrize("payload", [[], "text", 7])
def test_non_object_requests_are_rejected(payload):
    body, code = handle_request(payload)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_INVALID_REQUEST


def test_malformed_json_is_rejected(capsys):
    code = main(argv=[], stdin=io.StringIO("{not json"))
    body = json.loads(capsys.readouterr().out)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_INVALID_JSON


def test_empty_stdin_is_rejected(capsys):
    code = main(argv=[], stdin=io.StringIO("   "))
    body = json.loads(capsys.readouterr().out)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_INVALID_JSON


def test_missing_required_field_is_rejected(capsys):
    body, code = _run({"op": OP_METADATA_CONFORM, "output_folder": "out"}, capsys)

    assert code == EXIT_BAD_REQUEST
    assert body["errors"][0]["code"] == CODE_INVALID_REQUEST


def test_protocol_version_flag(capsys):
    code = main(argv=["--protocol-version"], stdin=io.StringIO(""))
    body = json.loads(capsys.readouterr().out)

    assert code == EXIT_OK
    assert body == {
        "protocol_version": PROTOCOL_VERSION,
        "package_version": __version__,
    }


def test_stdout_carries_only_the_response_in_a_subprocess(tmp_path):
    """A real subprocess run proves library chatter cannot corrupt stdout."""
    asset = _source_package(tmp_path / "source")
    request = {
        "protocol_version": PROTOCOL_VERSION,
        "op": OP_METADATA_CONFORM,
        "source_usd": str(asset),
        "output_folder": str(tmp_path / "dest" / "simready_usd"),
        "metadata": dict(COMPLETE_METADATA),
    }
    src = str(Path(__file__).resolve().parents[1] / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {src!r}); "
            "from simready.metadata_conform.sidecar import main; "
            "raise SystemExit(main())",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    body = json.loads(completed.stdout)
    assert body["ok"] is True
