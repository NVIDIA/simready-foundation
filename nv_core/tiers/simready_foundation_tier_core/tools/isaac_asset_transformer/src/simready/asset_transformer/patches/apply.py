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
"""Apply SimReady hotfixes to the pinned public Asset Transformer."""

from __future__ import annotations

import inspect
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType
from typing import Any

from isaacsim.asset.transformer import manager
from isaacsim.asset.transformer.rules.perf.geometries import GeometriesRoutingRule
from isaacsim.asset.transformer.rules.structure import variants

from . import isolated_620

_DISTRIBUTION = "isaacsim-asset-isolated"
_SUPPORTED_DISTRIBUTION_VERSION = "6.2.0.1"
PATCH_VERSION = "simready-6.2.0.1-1"
_MARKER = "__simready_patch_version__"

# (owner, attribute, replacement). Owners are public classes or modules.
_PATCHES: tuple[tuple[Any, str, Any], ...] = (
    (
        GeometriesRoutingRule,
        "_make_references_non_instanceable",
        isolated_620._make_references_non_instanceable,
    ),
    (variants, "copy_file_to_directory", isolated_620.copy_file_to_directory),
    (manager, "_publish_staged_package", isolated_620._publish_staged_package),
)

_MARKER_TARGETS: tuple[Any, ...] = (GeometriesRoutingRule, variants, manager)

_EXPECTED_SIGNATURES = {
    (GeometriesRoutingRule, "_make_references_non_instanceable"): (
        ("self", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
    ),
    (variants, "copy_file_to_directory"): (
        ("src_path", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("dest_dir", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("existing_collected", inspect.Parameter.POSITIONAL_OR_KEYWORD, None),
    ),
    (manager, "_publish_staged_package"): (
        ("staging_root", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("output_root", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("output_stage_path", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
    ),
}


def _installed_version() -> str:
    try:
        return version(_DISTRIBUTION)
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"{_DISTRIBUTION} is required; install it with "
            f"pip install {_DISTRIBUTION}=={_SUPPORTED_DISTRIBUTION_VERSION}"
        ) from exc


def _signature_shape(method: Any) -> tuple[tuple[str, inspect._ParameterKind, Any], ...]:
    return tuple(
        (parameter.name, parameter.kind, parameter.default)
        for parameter in inspect.signature(method).parameters.values()
    )


def _owner_name(owner: Any, attribute: str) -> str:
    if isinstance(owner, ModuleType):
        return f"{owner.__name__}.{attribute}"
    return f"{owner.__module__}.{owner.__qualname__}.{attribute}"


def _validate_target() -> None:
    installed = _installed_version()
    if installed != _SUPPORTED_DISTRIBUTION_VERSION:
        raise RuntimeError(
            "SimReady Asset Transformer patches support "
            f"{_DISTRIBUTION}=={_SUPPORTED_DISTRIBUTION_VERSION}; found {installed}. "
            "Remove or update the patches before changing the public wheel."
        )

    for (owner, attribute), expected in _EXPECTED_SIGNATURES.items():
        if _signature_shape(getattr(owner, attribute)) != expected:
            raise RuntimeError(f"Refusing to patch changed upstream method signature: {_owner_name(owner, attribute)}")


def apply_simready_rule_patches() -> None:
    """Apply reviewed SimReady fixes exactly once to the public transformer."""
    states = {getattr(target, _MARKER, None) for target in _MARKER_TARGETS}
    if states == {PATCH_VERSION}:
        return
    states.discard(None)
    if states:
        raise RuntimeError(f"Inconsistent SimReady Asset Transformer patch state: {sorted(states)}")

    _validate_target()

    for owner, attribute, replacement in _PATCHES:
        setattr(owner, attribute, replacement)
    for target in _MARKER_TARGETS:
        setattr(target, _MARKER, PATCH_VERSION)
