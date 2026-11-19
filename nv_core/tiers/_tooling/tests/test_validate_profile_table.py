# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The profile-table gate accepts native names without accepting wrong contracts."""

import importlib.util
from pathlib import Path

CHECK_PATH = Path(__file__).resolve().parents[3] / "sr_specs" / "tests" / "validate_profile_table.py"
spec = importlib.util.spec_from_file_location("validate_profile_table", CHECK_PATH)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_current_profile_table_matches_catalogs():
    assert check.main() == 0


def test_unknown_native_runtime_still_fails_the_gate(tmp_path, monkeypatch):
    table = tmp_path / "profiles.md"
    table.write_text(check.TABLE.read_text().replace("CAP026_Mates", "CAP026_Mates.Unknown"))
    monkeypatch.setattr(check, "TABLE", table)
    assert check.main() == 1


def test_short_neutral_selectors_share_catalog_wildcard_behavior(monkeypatch):
    monkeypatch.setattr(check, "_contract_ids", lambda: [
        "CAP024_BaseArticulation.0-1-0",
        "CAP024_BaseArticulation.PhysX.0-1-0",
    ])
    assert check._selected("CAP024.0-*") == ["CAP024_BaseArticulation"]
    assert check._selected("CAP024.PhysX") == ["CAP024_BaseArticulation.PhysX"]
    assert check._selected("CAP024.*") == ["CAP024_BaseArticulation", "CAP024_BaseArticulation.PhysX"]
