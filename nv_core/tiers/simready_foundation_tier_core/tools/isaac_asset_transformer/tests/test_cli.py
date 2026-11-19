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
from __future__ import annotations

import stat
from pathlib import Path

import pytest
from simready.asset_transformer import cli


def test_existing_output_is_refused_without_traceback(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    source = tmp_path / "asset.usda"
    source.write_text("#usda 1.0\n", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")

    assert cli.main([str(source), str(output)]) == 2

    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert "Pass --overwrite to replace it." in caplog.text


def test_missing_input_is_reported_without_traceback(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert cli.main([str(tmp_path / "missing.usda"), str(tmp_path / "out")]) == 2
    assert "Input USD does not exist" in caplog.text
    assert not (tmp_path / "out").exists()


def test_overwrite_removes_read_only_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "asset.usda"
    source.write_text("#usda 1.0\n", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    stale = output / "stale.usda"
    stale.write_text("#usda 1.0\n", encoding="utf-8")
    stale.chmod(stat.S_IREAD)

    from isaacsim.asset.transformer import ExecutionReport, RuleProfile

    def successful_transform(input_stage, package_root, **kwargs):
        package_root.mkdir(parents=True)
        return ExecutionReport(
            profile=RuleProfile(profile_name="Success"),
            input_stage_path=input_stage,
            package_root=str(package_root),
        )

    monkeypatch.setattr(cli, "transform_package", successful_transform)

    assert cli.main([str(source), str(output), "--overwrite"]) == 0
    assert not stale.exists()
