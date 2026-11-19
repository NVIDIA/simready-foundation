# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Foundations 2 capability, feature, and profile contract helpers.

The legacy SimReady loader identifies a feature with separate ``id``,
``runtime``, and ``version`` fields.  Foundations 2 uses one dotted identifier
instead::

    <name>[.<runtime>].<version>

Neutral IDs omit the OpenUSD runtime segment. The parsed runtime remains
``OpenUSD`` for consumers that choose the base composition. Older explicit
OpenUSD IDs are accepted and serialize to the shorter canonical spelling.

Runtime-tested contracts and their declared source contracts are features.
Other static requirement bundles use ``CAP``-prefixed capability IDs instead.
Profiles refer to both contract types with selectors.  Selectors may use shell
wildcards and may omit trailing segments.  For example, ``FET004.*`` selects
every runtime and version in feature family 004, while
``FET004.PhysX.*`` selects every PhysX version in that family.

This module is dependency-light so tier packages, validation clients, search,
and adapters can share exactly the same resolution behavior.  It deliberately
does not read profile identity from an asset: callers provide one or more
profile targets and each profile is resolved independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
import json
import re
import tomllib
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar


_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FET_FAMILY_RE = re.compile(r"^FET\d+$", re.IGNORECASE)
_FET_NAME_RE = re.compile(r"^FET\d+(?:_[A-Za-z0-9_-]+)?$", re.IGNORECASE)
_CAP_FAMILY_RE = re.compile(r"^CAP\d+$", re.IGNORECASE)
_CAP_NAME_RE = re.compile(r"^CAP\d+(?:_[A-Za-z0-9_-]+)?$", re.IGNORECASE)


class ContractError(ValueError):
    """Raised when a Foundations 2 feature or profile contract is invalid."""


@dataclass(frozen=True, order=True)
class FeatureId:
    """A canonical ``<name>[.<runtime>].<version>`` feature identifier."""

    name: str
    runtime: str
    version: str

    @classmethod
    def parse(cls, value: str) -> "FeatureId":
        if not isinstance(value, str):
            raise ContractError("Feature id must be a string.")
        parts = value.strip().split(".")
        if len(parts) == 2:
            parts.insert(1, "OpenUSD")
        if len(parts) != 3 or any(not part for part in parts):
            raise ContractError(
                f"Feature id '{value}' must use '<name>.<version>' or '<name>.<runtime>.<version>'."
            )
        if any(not _SEGMENT_RE.fullmatch(part) for part in parts):
            raise ContractError(
                f"Feature id '{value}' contains an invalid segment; use letters, digits, '_' or '-'."
            )
        if not _FET_NAME_RE.fullmatch(parts[0]):
            raise ContractError(
                f"Feature id '{value}' must use an FET-prefixed name such as 'FET004_Multibody'."
            )
        return cls(*parts)

    @property
    def family(self) -> str:
        """Return the numeric FET family token, if the name has a suffix."""

        return self.name.split("_", 1)[0]

    def __str__(self) -> str:
        if self.runtime.casefold() == "openusd":
            return f"{self.name}.{self.version}"
        return f"{self.name}.{self.runtime}.{self.version}"


@dataclass(frozen=True)
class FeatureSelector:
    """Match name/runtime/version globs and short neutral version selectors.

    Two segments match a runtime or a neutral version. This preserves runtime
    shorthand while accepting opaque neutral version tokens without guessing
    which runtimes or version spellings may exist in an installed tier.
    """

    name: str
    runtime: str = "*"
    version: str = "*"
    _short: bool = field(default=False, repr=False)

    @classmethod
    def parse(cls, value: str) -> "FeatureSelector":
        if not isinstance(value, str):
            raise ContractError("Feature selector must be a string.")
        parts = value.strip().split(".")
        if not 1 <= len(parts) <= 3 or any(not part for part in parts):
            raise ContractError(
                f"Feature selector '{value}' must contain one to three non-empty dotted segments."
            )
        short = len(parts) == 2 and parts[1] != "*"
        parts.extend(["*"] * (3 - len(parts)))
        return cls(*parts, _short=short)

    def matches(self, feature_id: FeatureId) -> bool:
        name_matches = fnmatchcase(feature_id.name.casefold(), self.name.casefold())
        if not name_matches and _FET_FAMILY_RE.fullmatch(self.name):
            name_matches = feature_id.family.casefold() == self.name.casefold()
        return (
            name_matches
            and (
                (
                    fnmatchcase(feature_id.runtime.casefold(), self.runtime.casefold())
                    and fnmatchcase(feature_id.version.casefold(), self.version.casefold())
                )
                or (
                    self._short
                    and feature_id.runtime.casefold() == "openusd"
                    and fnmatchcase(feature_id.version.casefold(), self.runtime.casefold())
                )
            )
        )

    def __str__(self) -> str:
        if self._short:
            return f"{self.name}.{self.runtime}"
        return f"{self.name}.{self.runtime}.{self.version}"


@dataclass(frozen=True)
class CapabilitySelector:
    """A wildcard selector over capability name, runtime, and version.

    Identical in shape to :class:`FeatureSelector`, because a capability id is
    identical in shape to a feature id. Neutral IDs omit the runtime segment;
    two-segment selectors match a runtime or a neutral version.

    The ``CAP`` prefix is not enforced here. It is enforced on capability *ids*,
    which is what guarantees a well-formed catalog; requiring it of a selector
    too would forbid a leading wildcard such as ``*articulation*`` and make
    globbing behave differently in the first segment than in the other two.
    """

    name: str
    runtime: str = "*"
    version: str = "*"
    _short: bool = field(default=False, repr=False)

    @classmethod
    def parse(cls, value: str) -> "CapabilitySelector":
        if not isinstance(value, str):
            raise ContractError("Capability selector must be a string.")
        parts = value.strip().split(".")
        if not 1 <= len(parts) <= 3 or any(not part for part in parts):
            raise ContractError(
                f"Capability selector '{value}' must contain one to three non-empty dotted segments."
            )
        short = len(parts) == 2 and parts[1] != "*"
        parts.extend(["*"] * (3 - len(parts)))
        return cls(*parts, _short=short)

    def matches(self, capability_id: "CapabilityId") -> bool:
        name_matches = fnmatchcase(capability_id.name.casefold(), self.name.casefold())
        if not name_matches and _CAP_FAMILY_RE.fullmatch(self.name):
            name_matches = capability_id.family.casefold() == self.name.casefold()
        return (
            name_matches
            and (
                (
                    fnmatchcase(capability_id.runtime.casefold(), self.runtime.casefold())
                    and fnmatchcase(capability_id.version.casefold(), self.version.casefold())
                )
                or (
                    self._short
                    and capability_id.runtime.casefold() == "openusd"
                    and fnmatchcase(capability_id.version.casefold(), self.runtime.casefold())
                )
            )
        )

    def __str__(self) -> str:
        if self._short:
            return f"{self.name}.{self.runtime}"
        return f"{self.name}.{self.runtime}.{self.version}"


@dataclass(frozen=True, order=True)
class CapabilityId:
    """A canonical ``<name>[.<runtime>].<version>`` capability identifier."""

    name: str
    runtime: str
    version: str

    @classmethod
    def parse(cls, value: str) -> "CapabilityId":
        if not isinstance(value, str):
            raise ContractError("Capability id must be a string.")
        parts = value.strip().split(".")
        if len(parts) == 2:
            parts.insert(1, "OpenUSD")
        if len(parts) != 3 or any(not part for part in parts):
            raise ContractError(
                f"Capability id '{value}' must use '<name>.<version>' or '<name>.<runtime>.<version>'."
            )
        if any(not _SEGMENT_RE.fullmatch(part) for part in parts):
            raise ContractError(
                f"Capability id '{value}' contains an invalid segment; use letters, digits, '_' or '-'."
            )
        if not _CAP_NAME_RE.fullmatch(parts[0]):
            raise ContractError(
                f"Capability id '{value}' must use a CAP-prefixed name such as 'CAP007_NonVisualMaterials'."
            )
        return cls(*parts)

    @property
    def family(self) -> str:
        """Return the numeric CAP family token, if the name has a suffix."""

        return self.name.split("_", 1)[0]

    def __str__(self) -> str:
        if self.runtime.casefold() == "openusd":
            return f"{self.name}.{self.version}"
        return f"{self.name}.{self.runtime}.{self.version}"


@dataclass(frozen=True)
class CapabilityDefinition:
    """A static requirement contract identified with a ``CAP`` prefix."""

    id: CapabilityId
    requirements: tuple[str, ...] = ()
    dependencies: tuple[CapabilityId, ...] = ()
    features: tuple[FeatureId, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, CapabilityId):
            object.__setattr__(self, "id", CapabilityId.parse(self.id))
        if not self.requirements and not self.dependencies and not self.features:
            raise ContractError(
                f"Capability '{self.id}' must declare requirements or capability dependencies."
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CapabilityDefinition":
        if "id" not in data:
            raise ContractError("Capability definition is missing 'id'.")
        requirements = _string_tuple(data.get("requirements", ()), "requirements")
        dependencies = tuple(
            CapabilityId.parse(value)
            for value in _string_tuple(data.get("dependencies", ()), "dependencies")
        )
        features = tuple(
            FeatureId.parse(value)
            for value in _string_tuple(data.get("features", ()), "features")
        )
        if not requirements and not dependencies and not features:
            raise ContractError(
                f"Capability '{data['id']}' must declare requirements or capability dependencies."
            )
        known = {"id", "requirements", "dependencies", "features"}
        return cls(
            id=CapabilityId.parse(data["id"]),
            requirements=requirements,
            dependencies=dependencies,
            features=features,
            metadata={key: value for key, value in data.items() if key not in known},
        )


@dataclass(frozen=True)
class FeatureDefinition:
    """A Foundations 2 feature definition.

    Identity is carried only by :attr:`id`.  Runtime-tested features carry
    runtime tests, runtime additions, and adapters.  A testless feature is
    valid only when it is a source FET for a tested derived feature; unrelated
    static contracts are :class:`CapabilityDefinition` instances.
    """

    id: FeatureId
    requirements: tuple[str, ...] = ()
    dependencies: tuple[FeatureId, ...] = ()
    capabilities: tuple[CapabilityId, ...] = ()
    source_feature: FeatureId | None = None
    source: bool = False
    additional_requirements: tuple[str, ...] = ()
    adapters: tuple[str, ...] = ()
    runtime_tests: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FeatureDefinition":
        if "id" not in data:
            raise ContractError("Feature definition is missing 'id'.")
        redundant = sorted({"name", "runtime", "version"}.intersection(data))
        if redundant:
            raise ContractError(
                "Feature identity must exist only in 'id'; remove redundant field(s): "
                + ", ".join(redundant)
            )

        if "runnable" in data and not isinstance(data["runnable"], bool):
            raise ContractError(f"Feature '{data['id']}' runnable must be true or false.")
        additional_requirements = _string_tuple(
            data.get("additional_requirements", ()), "additional_requirements"
        )
        adapters = _string_tuple(data.get("adapters", ()), "adapters")
        runtime_tests = _string_tuple(data.get("runtime_tests", ()), "runtime_tests")
        if runtime_tests and (not additional_requirements or not adapters):
            raise ContractError(
                f"Runtime-tested feature '{data['id']}' must declare additional_requirements and adapters."
            )
        if not runtime_tests and (additional_requirements or adapters):
            raise ContractError(
                f"Source feature '{data['id']}' cannot declare runtime-only fields without runtime_tests."
            )
        source = bool(data.get("source", False))
        if not runtime_tests and not source:
            raise ContractError(
                f"Feature '{data['id']}' has no runtime_tests; mark it as a source FET with tested derivatives or use a CAP-prefixed capability."
            )

        dependencies = tuple(
            FeatureId.parse(value)
            for value in _string_tuple(data.get("dependencies", ()), "dependencies")
        )
        capabilities = tuple(
            CapabilityId.parse(value)
            for value in _string_tuple(data.get("capabilities", ()), "capabilities")
        )
        source_feature_value = data.get("source_feature")
        source_feature = (
            FeatureId.parse(source_feature_value)
            if source_feature_value is not None
            else None
        )
        known = {
            "id",
            "requirements",
            "dependencies",
            "capabilities",
            "source_feature",
            "source",
            "runnable",
            "additional_requirements",
            "adapters",
            "runtime_tests",
        }
        return cls(
            id=FeatureId.parse(data["id"]),
            requirements=_string_tuple(data.get("requirements", ()), "requirements"),
            dependencies=dependencies,
            capabilities=capabilities,
            source_feature=source_feature,
            source=source,
            additional_requirements=additional_requirements,
            adapters=adapters,
            runtime_tests=runtime_tests,
            metadata={key: value for key, value in data.items() if key not in known},
        )

    @property
    def all_requirements(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.requirements, *self.additional_requirements)))

    @property
    def runnable(self) -> bool:
        """Whether this FET directly declares runtime evidence."""

        return bool(self.runtime_tests)


@dataclass(frozen=True)
class ProfileSelector:
    selector: FeatureSelector | CapabilitySelector
    optional: bool = False


@dataclass(frozen=True)
class ProfileDefinition:
    name: str
    version: str
    features: tuple[ProfileSelector, ...] = ()
    capabilities: tuple[ProfileSelector, ...] = ()


@dataclass(frozen=True)
class ResolvedItem:
    id: str
    optional: bool
    selectors: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedProfile:
    name: str
    version: str
    features: tuple[ResolvedItem, ...]
    capabilities: tuple[ResolvedItem, ...]


@dataclass(frozen=True)
class ProfileTarget:
    name: str
    version: str


T = TypeVar("T")


def load_feature_definitions(paths: Iterable[str | Path]) -> dict[str, FeatureDefinition]:
    """Load strict Foundations 2 feature JSON files from files/directories."""

    definitions: dict[str, FeatureDefinition] = {}
    for path in _expand_paths(paths, "*.json"):
        with path.open("r", encoding="utf-8") as stream:
            definition = FeatureDefinition.from_mapping(json.load(stream))
        key = str(definition.id)
        if key in definitions:
            raise ContractError(f"Duplicate feature id '{key}' in '{path}'.")
        definitions[key] = definition
    validate_feature_catalog(definitions)
    return definitions


def validate_feature_catalog(
    features: Mapping[str, FeatureDefinition] | Iterable[FeatureDefinition],
) -> None:
    """Validate source/derived relationships across a complete FET catalog."""

    values = features.values() if isinstance(features, Mapping) else features
    catalog = {str(definition.id): definition for definition in values}
    tested_derivatives: dict[str, list[str]] = {}
    for feature_id, definition in catalog.items():
        if definition.source_feature is None:
            continue
        source_id = str(definition.source_feature)
        if source_id not in catalog:
            raise ContractError(
                f"Feature '{feature_id}' names unknown source feature '{source_id}'."
            )
        if not catalog[source_id].source:
            raise ContractError(
                f"Feature '{feature_id}' source '{source_id}' is not marked source=true."
            )
        if definition.id.name.casefold() != catalog[source_id].id.name.casefold():
            raise ContractError(
                f"Feature '{feature_id}' and source '{source_id}' must share one FET name."
            )
        if definition.runtime_tests:
            tested_derivatives.setdefault(source_id, []).append(feature_id)

    for feature_id, definition in catalog.items():
        if not definition.runtime_tests and not tested_derivatives.get(feature_id):
            raise ContractError(
                f"Source feature '{feature_id}' has no tested derived features; use a CAP-prefixed capability."
            )


def load_capability_definitions(
    paths: Iterable[str | Path],
) -> dict[str, CapabilityDefinition]:
    """Load strict Foundations 2 capability JSON files from files/directories."""

    definitions: dict[str, CapabilityDefinition] = {}
    for path in _expand_paths(paths, "*.json"):
        with path.open("r", encoding="utf-8") as stream:
            definition = CapabilityDefinition.from_mapping(json.load(stream))
        key = str(definition.id)
        if key in definitions:
            raise ContractError(f"Duplicate capability id '{key}' in '{path}'.")
        definitions[key] = definition
    return definitions


def load_profile_definitions(paths: Iterable[str | Path]) -> dict[tuple[str, str], ProfileDefinition]:
    """Load Foundations 2 profile TOMLs from files/directories."""

    definitions: dict[tuple[str, str], ProfileDefinition] = {}
    for path in _expand_paths(paths, "*.toml"):
        with path.open("rb") as stream:
            document = tomllib.load(stream)
        for profile_name, versions in document.items():
            if not isinstance(versions, Mapping):
                raise ContractError(f"Profile '{profile_name}' in '{path}' must be a table.")
            for version, body in versions.items():
                if not isinstance(body, Mapping):
                    raise ContractError(f"Profile '{profile_name}@{version}' in '{path}' must be a table.")
                definition = ProfileDefinition(
                    name=profile_name,
                    version=str(version),
                    features=_parse_profile_selectors(body.get("features", ()), feature=True),
                    capabilities=_parse_profile_selectors(body.get("capabilities", ()), feature=False),
                )
                if not definition.features and not definition.capabilities:
                    raise ContractError(f"Profile '{profile_name}@{version}' has no selectors.")
                key = (profile_name, str(version))
                if key in definitions:
                    raise ContractError(f"Duplicate profile '{profile_name}@{version}' in '{path}'.")
                definitions[key] = definition
    return definitions


def resolve_profile(
    profile: ProfileDefinition,
    features: Mapping[str, FeatureDefinition] | Iterable[FeatureDefinition],
    capabilities: Mapping[str, CapabilityDefinition] | Iterable[CapabilityDefinition | str] = (),
) -> ResolvedProfile:
    """Expand a profile's feature/capability selectors deterministically."""

    feature_values = features.values() if isinstance(features, Mapping) else features
    feature_catalog = {str(definition.id): definition for definition in feature_values}
    validate_feature_catalog(feature_catalog)
    capability_catalog = _capability_catalog(capabilities)
    selected_features = _resolve_selectors(
        profile.features,
        sorted((definition.id for definition in feature_catalog.values()), key=str),
        lambda item: str(item),
    )
    selected_capabilities = _resolve_selectors(
        profile.capabilities,
        sorted((CapabilityId.parse(key) for key in capability_catalog), key=str),
        lambda item: str(item),
    )
    resolved_features, resolved_capabilities = _expand_contract_dependencies(
        selected_features,
        selected_capabilities,
        feature_catalog,
        capability_catalog,
    )
    return ResolvedProfile(
        name=profile.name,
        version=profile.version,
        features=resolved_features,
        capabilities=resolved_capabilities,
    )


def resolve_profiles(
    targets: Sequence[ProfileTarget],
    profiles: Mapping[tuple[str, str], ProfileDefinition],
    features: Mapping[str, FeatureDefinition] | Iterable[FeatureDefinition],
    capabilities: Mapping[str, CapabilityDefinition] | Iterable[CapabilityDefinition | str] = (),
) -> tuple[ResolvedProfile, ...]:
    """Resolve multiple profile targets independently and in caller order."""

    resolved: list[ResolvedProfile] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target.name, target.version)
        if key in seen:
            continue
        seen.add(key)
        try:
            profile = profiles[key]
        except KeyError as exc:
            raise ContractError(f"Unknown profile '{target.name}@{target.version}'.") from exc
        resolved.append(resolve_profile(profile, features, capabilities))
    return tuple(resolved)


def validate_asset_against_profiles(
    asset: str | Path,
    resolved_profiles: Sequence[ResolvedProfile],
    validate_one: Callable[[str | Path, ResolvedProfile], T],
) -> dict[tuple[str, str], T]:
    """Validate one asset against many independently resolved profiles.

    ``validate_one`` is intentionally injected: the contract layer can be used
    with ``simready.validate``, Kit, or another validation engine without
    coupling tier packages to one runner.
    """

    return {
        (profile.name, profile.version): validate_one(asset, profile)
        for profile in resolved_profiles
    }


def _parse_profile_selectors(entries: Any, *, feature: bool) -> tuple[ProfileSelector, ...]:
    if not isinstance(entries, list | tuple):
        raise ContractError("Profile selectors must be a list.")
    parsed: list[ProfileSelector] = []
    for entry in entries:
        if isinstance(entry, str):
            selector_text = entry
            optional = False
        elif isinstance(entry, Mapping):
            optional = bool(entry.get("optional", False))
            if "selector" in entry:
                selector_text = entry["selector"]
            else:
                keys = [key for key in entry if key != "optional"]
                if len(keys) != 1:
                    raise ContractError("A profile selector entry must contain one selector plus optional=true/false.")
                selector_text = keys[0]
        else:
            raise ContractError("Each profile selector must be a string or table.")
        selector = FeatureSelector.parse(selector_text) if feature else CapabilitySelector.parse(selector_text)
        parsed.append(ProfileSelector(selector=selector, optional=optional))
    return tuple(parsed)


def _resolve_selectors(
    selectors: Sequence[ProfileSelector],
    candidates: Sequence[Any],
    stringify: Callable[[Any], str],
) -> tuple[ResolvedItem, ...]:
    states: dict[str, tuple[bool, list[str]]] = {}
    for profile_selector in selectors:
        selector = profile_selector.selector
        matches = [candidate for candidate in candidates if selector.matches(candidate)]
        selector_text = str(selector)
        if not matches and not profile_selector.optional:
            raise ContractError(f"Required selector '{selector_text}' matched no catalog entries.")
        for match in matches:
            key = stringify(match)
            if key not in states:
                states[key] = (profile_selector.optional, [selector_text])
                continue
            current_optional, sources = states[key]
            states[key] = (current_optional and profile_selector.optional, [*sources, selector_text])
    return tuple(
        ResolvedItem(id=key, optional=optional, selectors=tuple(sources))
        for key, (optional, sources) in sorted(states.items())
    )


def _resolve_feature_selectors(
    selectors: Sequence[ProfileSelector],
    catalog: Mapping[str, FeatureDefinition],
) -> tuple[ResolvedItem, ...]:
    selected = _resolve_selectors(
        selectors,
        sorted((definition.id for definition in catalog.values()), key=str),
        lambda item: str(item),
    )
    states: dict[str, tuple[bool, list[str]]] = {
        item.id: (item.optional, list(item.selectors)) for item in selected
    }
    queue = list(states)
    while queue:
        parent_id = queue.pop(0)
        parent_optional, _ = states[parent_id]
        for dependency in catalog[parent_id].dependencies:
            dependency_id = str(dependency)
            if dependency_id not in catalog:
                raise ContractError(
                    f"Feature '{parent_id}' depends on unknown feature '{dependency_id}'."
                )
            source = f"dependency:{parent_id}"
            if dependency_id not in states:
                states[dependency_id] = (parent_optional, [source])
                queue.append(dependency_id)
                continue
            optional, sources = states[dependency_id]
            new_optional = optional and parent_optional
            if source not in sources:
                sources.append(source)
            if new_optional != optional:
                states[dependency_id] = (new_optional, sources)
                queue.append(dependency_id)
    return tuple(
        ResolvedItem(id=key, optional=optional, selectors=tuple(sources))
        for key, (optional, sources) in sorted(states.items())
    )


def _expand_contract_dependencies(
    features: Sequence[ResolvedItem],
    capabilities: Sequence[ResolvedItem],
    feature_catalog: Mapping[str, FeatureDefinition],
    capability_catalog: Mapping[str, CapabilityDefinition | None],
) -> tuple[tuple[ResolvedItem, ...], tuple[ResolvedItem, ...]]:
    feature_states: dict[str, tuple[bool, list[str]]] = {
        item.id: (item.optional, list(item.selectors)) for item in features
    }
    capability_states: dict[str, tuple[bool, list[str]]] = {
        item.id: (item.optional, list(item.selectors)) for item in capabilities
    }

    changed = True
    while changed:
        changed = False
        for feature_id, (optional, _) in list(feature_states.items()):
            definition = feature_catalog[feature_id]
            for dependency in definition.dependencies:
                dependency_id = str(dependency)
                if dependency_id not in feature_catalog:
                    raise ContractError(
                        f"Feature '{feature_id}' depends on unknown feature '{dependency_id}'."
                    )
                changed = _merge_resolved_state(
                    feature_states,
                    dependency_id,
                    optional,
                    f"feature:{feature_id}",
                ) or changed
            for dependency in definition.capabilities:
                dependency_id = str(dependency)
                if dependency_id not in capability_catalog:
                    raise ContractError(
                        f"Feature '{feature_id}' requires unknown capability '{dependency_id}'."
                    )
                changed = _merge_resolved_state(
                    capability_states,
                    dependency_id,
                    optional,
                    f"feature:{feature_id}",
                ) or changed

        for capability_id, (optional, _) in list(capability_states.items()):
            definition = capability_catalog[capability_id]
            if definition is None:
                continue
            for dependency in definition.dependencies:
                dependency_id = str(dependency)
                if dependency_id not in capability_catalog:
                    raise ContractError(
                        f"Capability '{capability_id}' depends on unknown capability '{dependency_id}'."
                    )
                changed = _merge_resolved_state(
                    capability_states,
                    dependency_id,
                    optional,
                    f"capability:{capability_id}",
                ) or changed
            for dependency in definition.features:
                dependency_id = str(dependency)
                if dependency_id not in feature_catalog:
                    raise ContractError(
                        f"Capability '{capability_id}' requires unknown feature '{dependency_id}'."
                    )
                changed = _merge_resolved_state(
                    feature_states,
                    dependency_id,
                    optional,
                    f"capability:{capability_id}",
                ) or changed

    resolved_features = tuple(
        ResolvedItem(id=key, optional=optional, selectors=tuple(sources))
        for key, (optional, sources) in sorted(feature_states.items())
    )
    resolved_capabilities = tuple(
        ResolvedItem(id=key, optional=optional, selectors=tuple(sources))
        for key, (optional, sources) in sorted(capability_states.items())
    )
    return resolved_features, resolved_capabilities


def _resolve_capability_selectors(
    selectors: Sequence[ProfileSelector],
    features: Sequence[ResolvedItem],
    feature_catalog: Mapping[str, FeatureDefinition],
    capability_catalog: Mapping[str, CapabilityDefinition | None],
) -> tuple[ResolvedItem, ...]:
    selected = _resolve_selectors(
        selectors,
        sorted((CapabilityId.parse(key) for key in capability_catalog), key=str),
        lambda item: str(item),
    )
    states: dict[str, tuple[bool, list[str]]] = {
        item.id: (item.optional, list(item.selectors)) for item in selected
    }

    for feature in features:
        for capability in feature_catalog[feature.id].capabilities:
            capability_id = str(capability)
            if capability_id not in capability_catalog:
                raise ContractError(
                    f"Feature '{feature.id}' requires unknown capability '{capability_id}'."
                )
            _merge_resolved_state(
                states,
                capability_id,
                feature.optional,
                f"feature:{feature.id}",
            )

    queue = list(states)
    visited: set[tuple[str, bool]] = set()
    while queue:
        parent_id = queue.pop(0)
        parent_optional, _ = states[parent_id]
        marker = (parent_id, parent_optional)
        if marker in visited:
            continue
        visited.add(marker)
        definition = capability_catalog[parent_id]
        if definition is None:
            continue
        for dependency in definition.dependencies:
            dependency_id = str(dependency)
            if dependency_id not in capability_catalog:
                raise ContractError(
                    f"Capability '{parent_id}' depends on unknown capability '{dependency_id}'."
                )
            changed = _merge_resolved_state(
                states,
                dependency_id,
                parent_optional,
                f"dependency:{parent_id}",
            )
            if changed:
                queue.append(dependency_id)

    return tuple(
        ResolvedItem(id=key, optional=optional, selectors=tuple(sources))
        for key, (optional, sources) in sorted(states.items())
    )


def _merge_resolved_state(
    states: dict[str, tuple[bool, list[str]]],
    item_id: str,
    optional: bool,
    source: str,
) -> bool:
    if item_id not in states:
        states[item_id] = (optional, [source])
        return True
    current_optional, sources = states[item_id]
    new_optional = current_optional and optional
    if source not in sources:
        sources.append(source)
    changed = new_optional != current_optional
    states[item_id] = (new_optional, sources)
    return changed


def _capability_catalog(
    capabilities: Mapping[str, CapabilityDefinition] | Iterable[CapabilityDefinition | str],
) -> dict[str, CapabilityDefinition | None]:
    if isinstance(capabilities, Mapping):
        catalog: dict[str, CapabilityDefinition | None] = {}
        for key, definition in capabilities.items():
            parsed_key = str(CapabilityId.parse(key))
            if str(definition.id) != parsed_key:
                raise ContractError(
                    f"Capability catalog key '{key}' does not match definition id '{definition.id}'."
                )
            catalog[parsed_key] = definition
        return catalog

    catalog = {}
    for item in capabilities:
        if isinstance(item, CapabilityDefinition):
            catalog[str(item.id)] = item
        else:
            capability_id = str(CapabilityId.parse(item))
            catalog[capability_id] = None
    return catalog


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ContractError(f"Contract field '{field_name}' must be a list of strings.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"Contract field '{field_name}' must contain non-empty strings.")
    return tuple(item.strip() for item in value)


def _expand_paths(paths: Iterable[str | Path], pattern: str) -> list[Path]:
    """Expand contract inputs into the concrete files they name.

    A path that does not exist contributes nothing, exactly like a directory
    that exists and is empty. The two cases are not meaningfully different to a
    caller, and a tier cannot control which one it presents: a tier publishing
    no contracts of one kind leaves that directory empty, git cannot track an
    empty directory, so the same tier offers a missing path in a fresh checkout
    and an empty one wherever the catalog has been generated. Rejecting the
    missing case would make loading depend on that accident.
    """
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            expanded.extend(sorted(path.glob(pattern)))
        elif path.is_file():
            expanded.append(path)
    return expanded


__all__ = [
    "CapabilityDefinition",
    "CapabilityId",
    "CapabilitySelector",
    "ContractError",
    "FeatureDefinition",
    "FeatureId",
    "FeatureSelector",
    "ProfileDefinition",
    "ProfileSelector",
    "ProfileTarget",
    "ResolvedItem",
    "ResolvedProfile",
    "load_feature_definitions",
    "load_capability_definitions",
    "load_profile_definitions",
    "resolve_profile",
    "resolve_profiles",
    "validate_asset_against_profiles",
    "validate_feature_catalog",
]
