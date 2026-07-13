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

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RuleConfigurationParam:
    name: str
    display_name: str
    param_type: Any
    description: Optional[str] = None
    default_value: Any = None


@dataclass
class RuleSpec:
    name: str
    type: str
    destination: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert this specification to a plain dictionary.

        Returns:
            Dictionary suitable for JSON serialization.

        Example:

        .. code-block:: python

            >>> spec = RuleSpec(
            ...     name="MoveMeshes",
            ...     type="isaacsim.asset.transformer.organizer.rules.geometries.GeometriesRoutingRule",
            ...     params={"scope": "/World"},
            ... )
            >>> isinstance(spec.to_dict(), dict)
            True
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RuleSpec":
        """Create a :class:`RuleSpec` from a dictionary.

        Args:
            data: Mapping with rule fields.

        Returns:
            Parsed :class:`RuleSpec` instance.

        Raises:
            ValueError: If required fields are missing.
        """
        name = data.get("name")
        type_ = data.get("type")
        if not name or not type_:
            raise ValueError("RuleSpec requires 'name' and 'type'.")
        return RuleSpec(
            name=name,
            type=type_,
            destination=data.get("destination"),
            params=dict(data.get("params", {})),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class RuleProfile:
    profile_name: str
    version: Optional[str] = None
    rules: List[RuleSpec] = field(default_factory=list)
    interface_asset_name: Optional[str] = None
    output_package_root: Optional[str] = None
    flatten_source: bool = False
    base_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to a dictionary.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {
            "profile_name": self.profile_name,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "interface_asset_name": self.interface_asset_name,
            "output_package_root": self.output_package_root,
            "flatten_source": self.flatten_source,
            "base_name": self.base_name,
        }

    def to_json(self) -> str:
        """Serialize profile to a deterministic JSON string.

        Returns:
            JSON string with sorted keys and no trailing spaces.
        """
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RuleProfile":
        """Parse a :class:`RuleProfile` from a dictionary.

        Args:
            data: Mapping with profile fields.

        Returns:
            Parsed :class:`RuleProfile` instance.
        """
        profile_name = data.get("profile_name") or ""
        if not profile_name:
            raise ValueError("RuleProfile requires 'profile_name'.")
        rules_raw = data.get("rules", [])
        rules = [RuleSpec.from_dict(r) for r in rules_raw]
        return RuleProfile(
            profile_name=profile_name,
            version=data.get("version"),
            rules=rules,
            interface_asset_name=data.get("interface_asset_name"),
            output_package_root=data.get("output_package_root"),
            flatten_source=data.get("flatten_source", False),
            base_name=data.get("base_name"),
        )

    @staticmethod
    def from_json(json_str: str) -> "RuleProfile":
        """Parse a :class:`RuleProfile` from a JSON string.

        Args:
            json_str: JSON payload encoding a profile.

        Returns:
            Parsed :class:`RuleProfile` instance.
        """
        return RuleProfile.from_dict(json.loads(json_str))


@dataclass
class RuleExecutionResult:
    rule: RuleSpec
    success: bool
    log: List[Dict[str, Any]] = field(default_factory=list)
    affected_stages: List[str] = field(default_factory=list)
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="milliseconds") + "Z")
    finished_at: Optional[str] = None

    def close(self) -> None:
        """Mark the result as finished by setting the ``finished_at`` timestamp.

        Returns:
            None.
        """
        self.finished_at = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


@dataclass
class ExecutionReport:
    profile: RuleProfile
    input_stage_path: str
    package_root: str
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="milliseconds") + "Z")
    finished_at: Optional[str] = None
    results: List[RuleExecutionResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the report to a dictionary suitable for JSON.

        Returns:
            Dictionary with execution details.
        """
        return {
            "profile": self.profile.to_dict(),
            "input_stage_path": self.input_stage_path,
            "package_root": self.package_root,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": [asdict(r) for r in self.results],
        }

    def to_json(self) -> str:
        """Serialize the report to a deterministic JSON string.

        Returns:
            JSON string with sorted keys and compact separators.
        """
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def close(self) -> None:
        """Mark the report as finished by setting the ``finished_at`` timestamp.

        Returns:
            None.
        """
        self.finished_at = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
