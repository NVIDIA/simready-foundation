# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check the public import boundary without installing the optional Isaac stack."""

import builtins
import runpy
from pathlib import Path

import pytest


_ENTRYPOINT = Path(__file__).parents[1] / "src/simready/asset_transformer/__init__.py"


@pytest.mark.parametrize("missing", ["isaacsim", "isaacsim.asset", "isaacsim.asset.transformer"])
def test_missing_transformer_explains_how_to_install_extra(monkeypatch, missing):
    original_import = builtins.__import__

    def without_transformer(name, *args, **kwargs):
        if name == "isaacsim.asset.transformer":
            raise ModuleNotFoundError(f"No module named {missing!r}", name=missing)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_transformer)
    with pytest.raises(ImportError, match=r"Python 3\.12.*simready-foundation-tier-core\[isaac\]"):
        runpy.run_path(str(_ENTRYPOINT))


def test_broken_upstream_install_preserves_original_error(monkeypatch):
    original_import = builtins.__import__
    missing_dependency = ModuleNotFoundError("No module named 'pxr'", name="pxr")

    def broken_transformer(name, *args, **kwargs):
        if name == "isaacsim.asset.transformer":
            raise missing_dependency
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_transformer)
    with pytest.raises(ModuleNotFoundError) as caught:
        runpy.run_path(str(_ENTRYPOINT))
    assert caught.value is missing_dependency
