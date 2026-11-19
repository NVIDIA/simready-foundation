# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the public neutral-to-runtimes API."""

from __future__ import annotations

import json

import pytest
from fixtures import write_neutral_package, write_non_mesh_package

from simready.multiphysics_upgrade import api
from simready.multiphysics_upgrade.api import (
    NeutralToRuntimesRequest,
    run_neutral_to_runtimes,
)


def _error_codes(result) -> set[str]:
    return {error.code for error in result.errors}


def _stages(result) -> set[str]:
    return {error.stage for error in result.errors}


def test_transforms_neutral_package_into_multiphysics_output(tmp_path):
    source_usd = write_neutral_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"

    result = run_neutral_to_runtimes(source_usd, output)

    assert result.ok, result.to_dict()
    assert result.errors == []
    payloads = output / "runnables" / "physics"
    assert (payloads / "physx.usda").is_file()
    assert (payloads / "newton.usda").is_file()
    assert (payloads / "mujoco.usda").is_file()
    assert result.output_usd is not None
    assert (output / "sm_test_neutral_01.usda").is_file()


def test_never_mutates_the_source_package(tmp_path):
    staging = tmp_path / "staging"
    source_usd = write_neutral_package(staging)
    before = source_usd.read_bytes()

    result = run_neutral_to_runtimes(source_usd, tmp_path / "simready_usd")

    assert result.ok
    assert not (staging / "runnables").exists()
    assert source_usd.read_bytes() == before


def test_rejects_missing_source(tmp_path):
    result = run_neutral_to_runtimes(tmp_path / "nope" / "sm_missing_01.usda", tmp_path / "out")

    assert not result.ok
    assert _error_codes(result) == {api.CODE_SOURCE_NOT_FOUND}
    assert _stages(result) == {api.STAGE_REQUEST}
    assert not (tmp_path / "out").exists()


def test_rejects_non_usd_source(tmp_path):
    source = tmp_path / "asset.txt"
    source.write_text("not usd", encoding="utf-8")

    result = run_neutral_to_runtimes(source, tmp_path / "out")

    assert _error_codes(result) == {api.CODE_SOURCE_NOT_USD}


def test_rejects_output_equal_to_source_package(tmp_path):
    source_usd = write_neutral_package(tmp_path / "staging")

    result = run_neutral_to_runtimes(source_usd, source_usd.parent)

    assert _error_codes(result) == {api.CODE_OUTPUT_IS_SOURCE}


def test_refuses_existing_output_without_replace(tmp_path):
    source_usd = write_neutral_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"
    output.mkdir()
    keeper = output / "previous.txt"
    keeper.write_text("previous", encoding="utf-8")

    result = run_neutral_to_runtimes(source_usd, output)

    assert _error_codes(result) == {api.CODE_OUTPUT_EXISTS}
    assert keeper.read_text(encoding="utf-8") == "previous"


def test_replaces_existing_output_when_requested(tmp_path):
    source_usd = write_neutral_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"
    output.mkdir()
    (output / "previous.txt").write_text("previous", encoding="utf-8")

    result = run_neutral_to_runtimes(source_usd, output, replace_existing=True)

    assert result.ok, result.to_dict()
    assert result.replaced_existing
    assert not (output / "previous.txt").exists()
    assert (output / "runnables" / "physics" / "physx.usda").is_file()
    assert not any(item.name.startswith(".simready_usd.backup_") for item in tmp_path.iterdir())


def test_preflight_blockers_are_reported_with_stable_codes(tmp_path):
    source_usd = write_non_mesh_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"

    result = run_neutral_to_runtimes(source_usd, output)

    assert not result.ok
    assert "NON_MESH_VISIBLE_GEOMETRY" in _error_codes(result)
    assert _stages(result) == {api.STAGE_PREFLIGHT}
    assert not output.exists()


def test_failed_run_preserves_previous_output_and_staging_diagnostics(tmp_path):
    source_usd = write_non_mesh_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"
    output.mkdir()
    (output / "previous.txt").write_text("previous", encoding="utf-8")
    diagnostics = tmp_path / ".diagnostics"

    result = run_neutral_to_runtimes(
        source_usd,
        output,
        replace_existing=True,
        diagnostics_dir=diagnostics,
    )

    assert not result.ok
    assert (output / "previous.txt").read_text(encoding="utf-8") == "previous"
    assert result.diagnostics_path is not None
    assert diagnostics.is_dir()
    assert not any(item.name.startswith(".multiphysics_stage_") for item in tmp_path.iterdir())


def test_promotion_failure_restores_previous_output(tmp_path, monkeypatch):
    source_usd = write_neutral_package(tmp_path / "staging")
    output = tmp_path / "simready_usd"
    output.mkdir()
    (output / "previous.txt").write_text("previous", encoding="utf-8")

    real_move = api.shutil.move

    def failing_move(src, dst):
        # Fail only the staged-package promotion, not moving the previous
        # output aside or restoring it.
        if ".multiphysics_stage_" in str(src):
            raise OSError("simulated promotion failure")
        return real_move(src, dst)

    monkeypatch.setattr(api.shutil, "move", failing_move)

    result = run_neutral_to_runtimes(source_usd, output, replace_existing=True)

    assert not result.ok
    assert _error_codes(result) == {api.CODE_PROMOTE_ROLLED_BACK}
    assert _stages(result) == {api.STAGE_PROMOTE}
    assert (output / "previous.txt").read_text(encoding="utf-8") == "previous"
    assert not any(item.name.startswith(".simready_usd.backup_") for item in tmp_path.iterdir())


def test_writes_machine_readable_report(tmp_path):
    source_usd = write_neutral_package(tmp_path / "staging")
    report = tmp_path / "reports" / "run.json"

    result = run_neutral_to_runtimes(source_usd, tmp_path / "simready_usd", report_path=report)

    assert result.ok
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["protocol_version"] == api.PROTOCOL_VERSION
    assert written["package_version"]
    assert written["errors"] == []


def test_request_from_dict_requires_paths():
    with pytest.raises(ValueError, match="source_usd"):
        NeutralToRuntimesRequest.from_dict({"output_folder": "out"})
    with pytest.raises(ValueError, match="output_folder"):
        NeutralToRuntimesRequest.from_dict({"source_usd": "in.usd"})
    with pytest.raises(ValueError, match="replace_existing"):
        NeutralToRuntimesRequest.from_dict(
            {"source_usd": "in.usd", "output_folder": "out", "replace_existing": "yes"}
        )


def test_request_from_dict_accepts_optional_fields():
    request = NeutralToRuntimesRequest.from_dict(
        {
            "source_usd": "in.usd",
            "output_folder": "out",
            "replace_existing": True,
            "report_path": "report.json",
            "diagnostics_dir": "diag",
        }
    )

    assert request.replace_existing is True
    assert request.report_path is not None
    assert request.diagnostics_dir is not None
