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
"""Kit-free feature-adapter definitions contributed by the core tier.

The public seam is the ``simready.feature_adapters`` package entry point.  A
consumer loads :func:`get_feature_adapters` only when it needs to derive an
asset; importing the tier descriptor or validator never imports these modules.
"""

from __future__ import annotations

import inspect
import logging
import re
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from typing import Callable

logger = logging.getLogger(__name__)

_SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?" r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_ADAPTER_MODULES = (
    "neutral_to_physx",
    "neutral_to_newton",
    "neutral_to_mujoco",
    "physx_to_isaacsim",
)
# Adapter modules whose callbacks need an optional extra, mapped to
# (a module that extra installs, the extra's name).
_OPTIONAL_EXTRA_ADAPTER_MODULES = {
    "physx_to_isaacsim": ("isaacsim.asset.transformer", "isaac"),
}


@dataclass(frozen=True)
class FeatureAdapterDefinition:
    """Portable description of one two-stage feature transformation."""

    name: str
    input_feature: str
    input_feature_version: str
    output_feature: str
    output_feature_version: str
    callback: Callable
    description: str = ""
    priority: int = 100
    version: str = "0.0.0"

    @property
    def module(self) -> str:
        return self.callback.__module__

    @property
    def function_name(self) -> str:
        return self.callback.__name__


_REGISTERED_ADAPTERS: dict[str, FeatureAdapterDefinition] = {}


def feature_adapter(
    name: str,
    input_feature_id: str,
    input_feature_version: str = "0.0.0",
    output_feature_id: str = "",
    output_feature_version: str = "0.0.0",
    description: str = "",
    priority: int = 100,
    version: str = "0.0.0",
):
    """Attach portable feature metadata to an adapter function and register it."""

    versions = (input_feature_version, output_feature_version, version)
    if any(not _SEMVER_RE.fullmatch(item) for item in versions):
        raise ValueError(f"Adapter {name!r} uses an invalid semantic version: {versions!r}")

    def decorate(func: Callable) -> Callable:
        if len(inspect.signature(func).parameters) != 2:
            raise ValueError(f"Feature adapter {func.__name__!r} must accept exactly " "(input_stage, output_stage)")
        definition = FeatureAdapterDefinition(
            name=name,
            input_feature=input_feature_id,
            input_feature_version=input_feature_version,
            output_feature=output_feature_id,
            output_feature_version=output_feature_version,
            callback=func,
            description=description,
            priority=priority,
            version=version,
        )
        existing = _REGISTERED_ADAPTERS.get(name)
        if existing is not None and existing != definition:
            raise ValueError(f"Feature adapter name {name!r} is already registered")
        _REGISTERED_ADAPTERS[name] = definition
        setattr(func, "__simready_feature_adapter__", definition)
        return func

    return decorate


def _module_installed(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _adapter_module_runnable(module_name: str) -> bool:
    requirement = _OPTIONAL_EXTRA_ADAPTER_MODULES.get(module_name)
    if requirement is None:
        return True
    required_module, extra = requirement
    if _module_installed(required_module):
        return True
    logger.info('%s adapters need pip install "simready-foundation-tier-core[%s]"', module_name, extra)
    return False


def get_feature_adapters() -> tuple[FeatureAdapterDefinition, ...]:
    """Import this tier's runnable adapters lazily and return their definitions.

    Adapters that need an optional extra are offered only when that extra is installed.
    """

    packages = tuple(
        f"{__name__}.{module_name}" for module_name in _ADAPTER_MODULES if _adapter_module_runnable(module_name)
    )
    for package in packages:
        import_module(package)
    return tuple(
        definition
        for definition in _REGISTERED_ADAPTERS.values()
        if any(definition.module == package or definition.module.startswith(f"{package}.") for package in packages)
    )
