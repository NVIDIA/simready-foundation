# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the one-shot JSON sidecar protocol."""

from __future__ import annotations

import io
import json

from fixtures import write_neutral_package, write_non_mesh_package

from simready.multiphysics_upgrade import sidecar
from simready.multiphysics_upgrade.api import PROTOCOL_VERSION


def _run(request: object, capsys) -> tuple[dict, int, str]:
    code = sidecar.main([], stdin=io.StringIO(json.dumps(request)))
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1, f"sidecar must emit exactly one stdout line, got {lines}"
    return json.loads(lines[0]), code, captured.err


def test_ping_reports_versions(capsys):
    response, code, _ = _run({"protocol_version": PROTOCOL_VERSION, "op": "ping"}, capsys)

    assert code == sidecar.EXIT_OK
    assert response["ok"] is True
    assert response["protocol_version"] == PROTOCOL_VERSION
    assert response["package_version"]
    assert response["python"].startswith("3.")


def test_transforms_package_and_emits_single_response(tmp_path, capsys):
    source_usd = write_neutral_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"

    response, code, _ = _run(
        {
            "protocol_version": PROTOCOL_VERSION,
            "op": "neutral_to_runtimes",
            "source_usd": str(source_usd),
            "output_folder": str(output),
        },
        capsys,
    )

    assert code == sidecar.EXIT_OK
    assert response["ok"] is True
    assert response["errors"] == []
    assert (output / "runnables" / "physics" / "physx.usda").is_file()


def test_library_stdout_does_not_corrupt_the_response(tmp_path, capsys, monkeypatch):
    source_usd = write_neutral_package(tmp_path / "staging")
    real_run = sidecar.run_neutral_to_runtimes

    def noisy_run(*args, **kwargs):
        print("library progress chatter")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(sidecar, "run_neutral_to_runtimes", noisy_run)

    response, code, stderr = _run(
        {
            "op": "neutral_to_runtimes",
            "source_usd": str(source_usd),
            "output_folder": str(tmp_path / "simready_usd"),
        },
        capsys,
    )

    assert code == sidecar.EXIT_OK
    assert response["ok"] is True
    assert "library progress chatter" in stderr


def test_transform_failure_returns_structured_errors(tmp_path, capsys):
    source_usd = write_non_mesh_package(tmp_path / "staging")

    response, code, _ = _run(
        {
            "op": "neutral_to_runtimes",
            "source_usd": str(source_usd),
            "output_folder": str(tmp_path / "simready_usd"),
        },
        capsys,
    )

    assert code == sidecar.EXIT_FAILED
    assert response["ok"] is False
    codes = {error["code"] for error in response["errors"]}
    assert "NON_MESH_VISIBLE_GEOMETRY" in codes
    assert all(error["stage"] for error in response["errors"])


def test_invalid_json_is_reported(capsys):
    code = sidecar.main([], stdin=io.StringIO("{not json"))
    out = json.loads(capsys.readouterr().out.strip())

    assert code == sidecar.EXIT_BAD_REQUEST
    assert out["errors"][0]["code"] == sidecar.CODE_INVALID_JSON


def test_missing_field_is_reported(capsys):
    response, code, _ = _run({"op": "neutral_to_runtimes", "output_folder": "out"}, capsys)

    assert code == sidecar.EXIT_BAD_REQUEST
    assert response["errors"][0]["code"] == sidecar.CODE_INVALID_REQUEST


def test_unsupported_op_is_reported(capsys):
    response, code, _ = _run({"op": "explode"}, capsys)

    assert code == sidecar.EXIT_BAD_REQUEST
    assert response["errors"][0]["code"] == sidecar.CODE_UNSUPPORTED_OP


def test_protocol_mismatch_is_reported(capsys):
    response, code, _ = _run({"protocol_version": PROTOCOL_VERSION + 1, "op": "ping"}, capsys)

    assert code == sidecar.EXIT_BAD_REQUEST
    assert response["errors"][0]["code"] == sidecar.CODE_PROTOCOL_MISMATCH


def test_non_object_request_is_reported(capsys):
    response, code, _ = _run(["not", "an", "object"], capsys)

    assert code == sidecar.EXIT_BAD_REQUEST
    assert response["errors"][0]["code"] == sidecar.CODE_INVALID_REQUEST


def test_protocol_version_flag(capsys):
    code = sidecar.main(["--protocol-version"])
    out = json.loads(capsys.readouterr().out.strip())

    assert code == sidecar.EXIT_OK
    assert out["protocol_version"] == PROTOCOL_VERSION
    assert out["package_version"]
