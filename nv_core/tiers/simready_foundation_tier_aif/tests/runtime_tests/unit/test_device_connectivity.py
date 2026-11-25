# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Registration and outcome classification; adapters are mocked, no live lab."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

pytest.importorskip("simready.evaluate")
from simready.evaluate import RunContext  # noqa: E402
from simready.evaluate.core.discovery import discover_tests  # noqa: E402
from simready.foundation.tier_aif import dsx_air  # noqa: E402
from simready.foundation.tier_aif.runtime_tests.fet207_simulation_network_topology.device_connectivity import (  # noqa: E402
    device_connectivity,
)

PKG = Path(dsx_air.__file__).parent
TIER = PKG.parents[2]
FEATURE = "FET207_SimulationNetworkTopology.0-3-0"


def context(tmp_path, config=None):
    return RunContext(
        asset_path="synthetic.usda", asset_rel_path="synthetic.usda",
        output_dir=str(tmp_path), test_name="device_connectivity", test_version="0.3.0",
        feature_id=FEATURE, engine_name="unit-test", engine_version="0", session_id="unit",
        scene=None, config=config or {},
    )


def test_registration_and_manifest_binding_agree():
    definitions = discover_tests([str(PKG / "runtime_tests")])
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.name == "device_connectivity"
    assert definition.provider == "simready.foundation.tier_aif.runtime_tests"
    assert [(ref.id, ref.version) for ref in definition.features] == [(FEATURE, "*")]
    assert definition.engine is None
    assert definition.config_defaults == {"fixture_path": ""}
    manifest = json.loads((PKG / "features" / f"{FEATURE}.json").read_text())
    assert manifest["runtime_tests"] == [f"{definition.provider}:{definition.name}"]


@pytest.mark.parametrize("passed,received", [(True, 3), (False, 0)])
def test_completed_measurement_preserves_verdict(tmp_path, monkeypatch, passed, received):
    evidence = {"passed": passed, "transmitted": 3, "received": received}
    calls = []

    def adapter(asset, fixture):
        calls.append((asset, fixture))
        return evidence

    monkeypatch.setattr(dsx_air, "run_connectivity", adapter)
    ctx = context(tmp_path, {"fixture_path": "reviewed-fixture.json"})
    asyncio.run(device_connectivity(ctx))
    assert calls == [("synthetic.usda", "reviewed-fixture.json")]
    assert ctx.failed is not passed
    assert not ctx.skipped
    assert ctx.metrics["dsx_air_connectivity"]["value"] == evidence


def test_fixture_environment_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("DSX_AIR_CONNECTIVITY_FIXTURE", "environment-fixture.json")
    calls = []
    monkeypatch.setattr(dsx_air, "run_connectivity", lambda asset, fixture: (
        calls.append(fixture) or {"passed": True, "transmitted": 3, "received": 3}
    ))
    asyncio.run(device_connectivity(context(tmp_path)))
    assert calls == ["environment-fixture.json"]


def test_missing_fixture_is_execution_error(tmp_path, monkeypatch):
    monkeypatch.delenv("DSX_AIR_CONNECTIVITY_FIXTURE", raising=False)
    ctx = context(tmp_path)
    with pytest.raises(RuntimeError, match="Configure fixture_path"):
        asyncio.run(device_connectivity(ctx))
    assert not ctx.failed and not ctx.skipped


@pytest.mark.parametrize("exception", [ValueError("invalid fixture"), OSError("unavailable"), RuntimeError("invalid output")])
def test_adapter_error_is_not_asset_failure_or_skip(tmp_path, monkeypatch, exception):
    def unavailable(*args):
        raise exception

    monkeypatch.setattr(dsx_air, "run_connectivity", unavailable)
    ctx = context(tmp_path, {"fixture_path": "reviewed-fixture.json"})
    with pytest.raises(type(exception), match=str(exception)):
        asyncio.run(device_connectivity(ctx))
    assert not ctx.failed and not ctx.skipped
    assert not ctx.metrics


@pytest.mark.parametrize("evidence", [{}, {"passed": "true"}, {"passed": 1}])
def test_missing_explicit_boolean_verdict_is_execution_error(tmp_path, monkeypatch, evidence):
    monkeypatch.setattr(dsx_air, "run_connectivity", lambda *args: evidence)
    ctx = context(tmp_path, {"fixture_path": "reviewed-fixture.json"})
    with pytest.raises(RuntimeError, match="explicit boolean"):
        asyncio.run(device_connectivity(ctx))
    assert not ctx.failed and not ctx.skipped


def test_tier_descriptor_does_not_import_runtime_dependencies():
    code = '''
import importlib, importlib.abc, pathlib, sys
class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(part in fullname for part in ('evaluate', 'runtime_tests', 'rules_and_reqs', 'requirements')) or fullname.split('.')[0] in ('pxr', 'omni', 'isaacsim'):
            raise AssertionError('descriptor imported runtime dependency: ' + fullname)
sys.meta_path.insert(0, BlockRuntime())
module = importlib.import_module('simready.foundation.tier_aif._tier')
assert module.tier.runtime_tests_path == pathlib.Path(module.__file__).parent / 'runtime_tests'
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_evaluate_extra_and_docs_sources_are_packaged():
    metadata = tomllib.loads((TIER / "pyproject.toml").read_text())
    assert metadata["project"]["optional-dependencies"]["evaluate"] == ["simready-evaluate>=2026.10.0,<2026.11"]
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["simready"]
    sources = json.loads((TIER / "docs-sources.json").read_text())
    assert sources["sources"] == [{
        "path": "simready/foundation/tier_aif/runtime_tests/docs",
        "destination": "guides/evaluate/aif-tests",
    }]
    assert (TIER / sources["sources"][0]["path"] / "tests.md").is_file()
