# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Published requirement checks compare neutral IDs across the catalog rename."""

import importlib.util
import json
from pathlib import Path
import sys


CHECK_PATH = Path(__file__).resolve().parents[3] / "sr_specs" / "tests" / "validate_feature_versions.py"
spec = importlib.util.spec_from_file_location("validate_feature_versions", CHECK_PATH)
check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check
spec.loader.exec_module(check)


def test_neutral_id_rename_keeps_the_published_contract_identity():
    assert check._contract_id({"id": "FET003_RigidBody.OpenUSD.0-2-0"}) == "FET003_RigidBody.0-2-0"
    assert check._contract_id({"id": "CAP000_Core.OpenUSD.0-2-0"}) == "CAP000_Core.0-2-0"
    assert check._contract_id({"id": "FET003_RigidBody.PhysX.0-4-0"}) == "FET003_RigidBody.PhysX.0-4-0"


def test_renamed_contract_still_rejects_changed_requirements(tmp_path, monkeypatch):
    path = tmp_path / "FET003_RigidBody.0-2-0.json"
    path.write_text(json.dumps({"id": "FET003_RigidBody.0-2-0", "requirements": ["RB.002"]}))
    monkeypatch.setattr(check, "_baseline_ref", lambda: "main")
    monkeypatch.setattr(check, "_released", lambda baseline: {
        check._contract_id({"id": "FET003_RigidBody.OpenUSD.0-2-0"}): ["RB.001"],
    })
    monkeypatch.setattr(check, "_manifests", lambda: [path])
    problems = []

    check.check_released_versions_unchanged(problems, {})

    assert len(problems) == 1
    assert "RB.001" in problems[0] and "RB.002" in problems[0]
