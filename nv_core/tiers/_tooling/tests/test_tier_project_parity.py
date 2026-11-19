# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parity checks that every tier project is wired the same way.

Both of the ways the sensors tier went missing were silent. The catalog
generator discovered package roots by directory name, so a tier not using the
``tier_`` prefix was skipped; and the validate loader reads the Foundations 2
contract paths with ``getattr(..., None)``, so a descriptor omitting them
registers nothing rather than failing. Neither produced an error, which is why
these are asserted across all tiers instead of per tier.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import migrate_foundations2_catalog as migrate  # noqa: E402

_CONTRACT_PATH_FIELDS = (
    "capability_contracts_path",
    "feature_contracts_path",
    "profile_contracts_path",
)


def _package_roots() -> list[Path]:
    roots = migrate._package_roots()
    assert roots, "no tier package roots discovered"
    return roots


def _descriptor(package_root: Path):
    module_name = f"_tier_parity_{package_root.name}"
    spec = importlib.util.spec_from_file_location(module_name, package_root / "_tier.py")
    module = importlib.util.module_from_spec(spec)
    # dataclass resolution needs the module registered before execution.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.tier


@pytest.mark.parametrize("package_root", _package_roots(), ids=lambda root: root.name)
def test_descriptor_advertises_foundations2_contract_paths(package_root):
    tier = _descriptor(package_root)
    for field in _CONTRACT_PATH_FIELDS:
        value = getattr(tier, field, None)
        assert value is not None, (
            f"{package_root.name} descriptor omits {field}; the validate loader "
            "reads it with getattr and would skip this tier's contracts silently"
        )
        assert Path(value).is_relative_to(package_root)


@pytest.mark.parametrize("package_root", _package_roots(), ids=lambda root: root.name)
def test_generated_requirements_tree_is_ignored_in_the_tier_project(package_root):
    """A tier force-including generated enums must ignore the checkout copy.

    `packages` ships the committed tree and `force-include` adds the generated
    one. Hatchling resolves VCS ignores against the directory holding
    pyproject.toml, so without a tier-local .gitignore a checkout that has run
    codegen packages the same path twice and the wheel build fails.
    """
    project_root = next(
        parent for parent in package_root.parents if (parent / "pyproject.toml").is_file()
    )
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {})
    force_include = wheel.get("wheel", {}).get("force-include", {})
    generated = [target for target in force_include.values() if target.endswith("/requirements")]
    if not generated:
        pytest.skip(f"{project_root.name} force-includes no generated requirements tree")

    gitignore = project_root / ".gitignore"
    assert gitignore.is_file(), (
        f"{project_root.name} force-includes {generated} but has no tier-local "
        ".gitignore, so a wheel build after codegen fails on a duplicate path"
    )
    ignored = gitignore.read_text(encoding="utf-8")
    for target in generated:
        assert f"/{target}/" in ignored
