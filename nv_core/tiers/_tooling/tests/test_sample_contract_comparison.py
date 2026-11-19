# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Sample comparisons retain contract identity across neutral-ID aliases."""

import ast
import json
import re
from pathlib import Path

import pytest


_CHECK = Path(__file__).resolve().parents[3] / "sr_specs/tests/validate_sample_content.py"
_FUNCTIONS = {"_comparison_id", "_legacy_feature_ids", "_as_legacy_features"}
# These comparison helpers need no USD engine or validator initialization.
_TREE = ast.parse(_CHECK.read_text(encoding="utf-8"))
_HELPERS = {"Path": Path, "json": json, "re": re}
_BODY = [node for node in _TREE.body if isinstance(node, ast.FunctionDef) and node.name in _FUNCTIONS]
exec(compile(ast.Module(body=_BODY, type_ignores=[]), str(_CHECK), "exec"), _HELPERS)


@pytest.mark.parametrize("prefix", ["FET003_RigidBody", "CAP000_Core"])
def test_normalized_results_match_legacy_catalog_aliases(tmp_path, prefix):
    catalog = tmp_path / "nv_core/tiers/core/simready/foundation/tier_core/catalog-map.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({
        "contracts": [{"id": prefix + ".OpenUSD.0-2-0", "legacy_id": "FET_000_STANDARD"}],
    }))
    aliases = _HELPERS["_legacy_feature_ids"](str(tmp_path))
    current = _HELPERS["_as_legacy_features"]({prefix + ".0-2-0": {"passed": True}}, aliases)
    baseline = _HELPERS["_as_legacy_features"]({prefix + ".OpenUSD.0-2-0": {"passed": True}}, aliases)
    assert current == baseline == {"FET_000_STANDARD": {"passed": True}}


def test_native_aliases_fold_failures_without_merging_runtime_variants():
    result = _HELPERS["_as_legacy_features"](
        {
            "FET999_Native.OpenUSD.0-1-0": {"passed": True},
            "FET999_Native.0-1-0": {"passed": False},
            "FET999_Native.Newton.0-1-0": {"passed": True},
            "FET999_Native.0-2-0": {"passed": True},
        },
        {},
    )
    assert result == {
        "FET999_Native.0-1-0": {"passed": False},
        "FET999_Native.Newton.0-1-0": {"passed": True},
        "FET999_Native.0-2-0": {"passed": True},
    }
