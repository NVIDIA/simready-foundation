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
"""Stable public API for standalone asset transformation."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from .manager import AssetTransformerManager
from .models import ExecutionReport, RuleProfile

_PROFILE_ALIASES = {
    "simready_physx_to_isaac_prop": "simready_physx_to_isaac_prop.json",
    "simready_physx_to_isaac_robot": "simready_physx_to_isaac_robot.json",
}


def profile_transforms_dir() -> Path:
    """Return the directory that holds the bundled profile-transform JSON files.

    Resolves against the installed/importable ``simready.asset_transformer``
    package so callers can build an explicit profile path without hard-coding
    repository layout.
    """
    return Path(str(files("simready.asset_transformer").joinpath("profile_transforms")))


def load_profile(profile: str | Path = "simready_physx_to_isaac_prop") -> RuleProfile:
    """Load a bundled profile alias or an explicit JSON profile path."""
    requested = str(profile)
    candidate = Path(requested)
    if candidate.is_file():
        profile_text = candidate.read_text(encoding="utf-8")
    else:
        filename = _PROFILE_ALIASES.get(requested, requested)
        if not filename.endswith(".json"):
            filename += ".json"
        resource = files("simready.asset_transformer").joinpath("profile_transforms", filename)
        if not resource.is_file():
            choices = ", ".join(sorted(_PROFILE_ALIASES))
            raise FileNotFoundError(f"Unknown transformer profile '{requested}'. Aliases: {choices}")
        profile_text = resource.read_text(encoding="utf-8")
    return RuleProfile.from_json(profile_text)


def transform_package(
    input_stage: str,
    package_root: str | Path,
    *,
    profile: str | Path | RuleProfile = "simready_physx_to_isaac_prop",
    interface_asset_name: str | None = None,
) -> ExecutionReport:
    """Transform an input USD into a new package directory."""
    from .rules import register_all_rules

    selected_profile = load_profile(profile) if not isinstance(profile, RuleProfile) else profile
    if interface_asset_name:
        selected_profile.interface_asset_name = interface_asset_name
    register_all_rules()
    return AssetTransformerManager().run(
        input_stage=input_stage,
        profile=selected_profile,
        package_root=str(package_root),
    )
