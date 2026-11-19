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

"""Generate the Foundations 2 CAP/FET catalogs from published tier content.

Published split-ID manifests and exact-pin profiles remain compatibility input.
The generated ``foundations2`` trees are the canonical dotted-ID projection:

* exact benchmark-mapped contracts are FETs;
* a STANDARD contract remains a source FET when its family has tested FETs;
* every other static-only contract becomes a CAP-prefixed capability; and
* profile entries move to the matching feature or capability selector list.

The version token is a lossless single-segment encoding of the published
semantic version (``0.4.0`` becomes ``0-4-0``).
"""

from __future__ import annotations

import argparse
import ast
import json
import keyword
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 tier support
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[3]
TIERS_ROOT = REPO_ROOT / "nv_core" / "tiers"

FAMILY_NAMES = {
    "000": "Core",
    "001": "MinimalPlaceableVisual",
    "002": "PosableBodies",
    "003": "RigidBody",
    "004": "Multibody",
    "005": "Grasp",
    "006": "Materials",
    "007": "NonVisualMaterials",
    "010": "DisplayColor",
    "011": "SemanticLabels",
    # Named for its SPL.* Gaussian-splat requirements rather than its broader
    # "Sensor Visual 3DGS" display name.
    "012": "GaussianSplat",
    "021": "RobotCore",
    "022": "DrivenJoints",
    "023": "RobotMaterials",
    "024": "BaseArticulation",
    "025": "RosBridge",
    "026": "Mates",
    "027": "Connections",
    "028": "Gripper",
    "029": "ConnectionJoint",
    "030": "PackagingCore",
    "031": "SelfContainedPackage",
    "032": "PackagingIntrospection",
    "033": "SimReadyPackage",
    # Sensors tier. 035 and 036 are named for the requirements they carry (RP.*
    # render products, LI.* LiDAR) rather than their broader display names; the
    # runtime already occupies the middle dotted segment.
    "034": "ImuSensor",
    "035": "RenderProducts",
    "036": "Lidar",
    "037": "JointSensor",
    "039": "ObjectAffordances",
    "040": "CocoLabels",
    "041": "CityscapesLabels",
    "042": "Ade20kLabels",
    "043": "PascalVocLabels",
    "044": "SunRgbdLabels",
    "045": "ImageNet1kLabels",
    "046": "WikidataLabels",
    "100": "IsaacComposition",
    "101": "RobotComposition",
    # AIF tier.
    "200": "AifMetadata",
    "201": "ConnectionPoints",
    "202": "ThermalCooling",
    "203": "Electrical",
    "1000": "TemplateSmoke",
}

FEATURE_REF_RE = re.compile(r'\{"id":\s*"(FET_[0-9A-Z_]+)",\s*"version":\s*"([^"]+)"\}')
TEST_NAME_RE = re.compile(r'^\s*name="([^"]+)"', re.MULTILINE)
# The AIF tier publishes pre-underscore IDs such as `FET200_AIF`.
FAMILY_RE = re.compile(r"^FET_?(\d+)_")


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _matches_version(version: str, constraint: str) -> bool:
    if constraint.startswith(">="):
        return _version_tuple(version) >= _version_tuple(constraint[2:])
    if constraint.startswith("=="):
        return _version_tuple(version) == _version_tuple(constraint[2:])
    return version == constraint


def _version_token(version: str) -> str:
    return version.replace(".", "-").replace("+", "-plus-")


def _family(legacy_id: str) -> str:
    match = FAMILY_RE.match(legacy_id)
    if not match:
        raise ValueError(f"Unsupported legacy feature id: {legacy_id}")
    return match.group(1)


def _runtime(legacy_id: str, manifest: dict[str, Any]) -> str:
    if manifest.get("runtime"):
        runtime = str(manifest["runtime"])
        if legacy_id.endswith("_ROBOT_PHYSX"):
            return "RobotPhysX"
        if legacy_id.endswith("_ROBOT_NEWTON"):
            return "RobotNewton"
        if legacy_id.endswith("_ROBOT_MUJOCO"):
            return "RobotMuJoCo"
        return runtime.replace(" ", "")
    _family(legacy_id)
    suffix = FAMILY_RE.sub("", legacy_id, count=1)
    return {
        "STANDARD": "OpenUSD",
        # AIF names the tier's domain, not a runtime; its rules are runtime-neutral.
        "AIF": "OpenUSD",
        "ISAAC": "Isaac",
        "RTX": "RTX",
        "MDL": "MDL",
        "MUJOCO": "MuJoCo",
        "PHYSX": "PhysX",
        "TEMPLATE": "Template",
    }.get(suffix, suffix.title().replace("_", ""))


def _legacy_page(manifest: dict[str, Any]) -> str:
    """The stem of the Foundations 1 page documenting a manifest.

    Usually the legacy ID, but not always: the AIF tier's `FET200_AIF` is
    documented by `FET_200-aif_metadata.md`. The manifest's `path` names the
    page either way.
    """
    path = manifest.get("path")
    return PurePosixPath(path).stem if path else manifest["id"]


def _new_id(prefix: str, manifest: dict[str, Any]) -> str:
    family = _family(manifest["id"])
    # A generated placeholder would become a permanent contract ID and a
    # permanent filename, and nothing downstream would flag it. Naming a new
    # family is a deliberate choice, so demand it here instead.
    if family not in FAMILY_NAMES:
        raise KeyError(
            f"Feature family '{family}' has no FAMILY_NAMES entry, needed to project "
            f"{manifest['id']}@{manifest['version']}. Add one to "
            "nv_core/tiers/_tooling/migrate_foundations2_catalog.py, using the manifest's "
            f"display_name ({manifest.get('display_name', 'unset')!r}) in PascalCase."
        )
    name = FAMILY_NAMES[family]
    runtime = _runtime(manifest['id'], manifest)
    runtime_segment = "" if runtime.casefold() == "openusd" else f"{runtime}."
    return f"{prefix}{family}_{name}.{runtime_segment}{_version_token(manifest['version'])}"


_PROVIDER_DESCRIPTORS = ("benchmark-provider.json", "evaluate-provider.json")
_PROVIDER_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _runtime_import_package(suite: Path, declared: dict) -> str:
    """Normalize regular-package inference and validate exact physical ownership."""
    root = suite.resolve()
    if "import_package" not in declared:
        if not (root / "__init__.py").is_file():
            raise ValueError("import_package is required for namespace package ownership")
        name, parent = root.name, root.parent
        while (parent / "__init__.py").is_file():
            name = parent.name + "." + name
            parent = parent.parent
    else:
        name = declared["import_package"]
    if not isinstance(name, str) or not all(
        part.isidentifier() and not keyword.iskeyword(part) for part in name.split(".")
    ):
        raise ValueError("import_package must be a dotted Python identifier")
    import_root = root
    for part in reversed(name.split(".")):
        if os.path.normcase(import_root.name) != os.path.normcase(part):
            raise ValueError("import_package does not match the selected package")
        import_root = import_root.parent
    if import_root.joinpath(*name.split(".")).resolve() != root:
        raise ValueError("import_package escapes the selected package")
    return name


def _runtime_provider_metadata(suite: Path) -> dict | None:
    """Read static provider identities with the canonical descriptor first."""
    declarations = []
    for filename in _PROVIDER_DESCRIPTORS:
        path = suite / filename
        if not path.exists() and not path.is_symlink():
            continue
        try:
            if not path.resolve().is_relative_to(suite.resolve()):
                raise ValueError("descriptor escapes selected package")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) - {"provider", "aliases", "import_package"}:
                raise ValueError("expected provider and optional aliases/import_package")
            aliases = data.setdefault("aliases", [])
            if not isinstance(aliases, list):
                raise ValueError("aliases must be an array")
            identities = [data.get("provider"), *aliases]
            if any(
                not isinstance(identity, str)
                or not identity
                or len(identity) > 128
                or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", identity)
                or identity.endswith(".")
                or identity.split(".", 1)[0].upper() in _PROVIDER_RESERVED_NAMES
                for identity in identities
            ):
                raise ValueError("provider and aliases must be portable qualified identities of at most 128 characters")
            if len(set(identities)) != len(identities):
                raise ValueError("duplicate provider identities")
            data["import_package"] = _runtime_import_package(suite, data)
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid runtime suite ownership at {path}: {exc}") from exc
        declarations.append(data)
    if any(data != declarations[0] for data in declarations[1:]):
        raise ValueError(f"Conflicting runtime suite ownership descriptors at {suite}")
    return declarations[0] if declarations else None


def _namespace_provider(tier_dir: Path, suite: Path) -> str:
    """Validate a source ownership declaration without importing its package."""
    try:
        metadata = _runtime_provider_metadata(suite)
        if metadata is None:
            raise ValueError("missing provider descriptor")
        name = metadata["import_package"]
        provider = metadata["provider"]
        if not isinstance(name, str) or not all(
            part.isidentifier() and not keyword.iskeyword(part) for part in name.split(".")
        ):
            raise ValueError("import_package must be a dotted Python identifier")
        if not isinstance(provider, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", provider):
            raise ValueError("provider must be a qualified identity")
        if tier_dir.joinpath(*name.split(".")).resolve() != suite.resolve():
            raise ValueError("import_package does not match the selected package")
        if not suite.resolve().is_relative_to(tier_dir.resolve()):
            raise ValueError("package escapes its tier")
        if not (suite / "__init__.py").is_file():
            raise ValueError("the owned package has no __init__.py")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Invalid runtime suite ownership at {suite}: {exc}") from exc
    return provider


def _runtime_suites() -> list[Path]:
    """Tier runtime suites, including namespace packages declared for the wheel.

    Static discovery preserves the historical flat-package input used by the
    Foundations 1 catalog transformer. Current source ownership comes from
    benchmark-provider.json and the descriptor's literal owned-package declaration.
    Neither descriptor nor runtime modules are executed.
    """
    suites: list[Path] = []
    for tier_dir in sorted(TIERS_ROOT.glob("simready_foundation_tier_*")):
        package_root = _tier_package_root(tier_dir)
        if package_root is None:
            continue
        pyproject = tomllib.loads((tier_dir / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = pyproject.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
        shipped = [tier_dir / name for name in wheel.get("packages", [])]
        advertised = []
        for node in ast.walk(ast.parse((package_root / "_tier.py").read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_owned_package_directory"
            ):
                if (
                    len(node.args) != 1
                    or not isinstance(node.args[0], ast.Constant)
                    or not isinstance(node.args[0].value, str)
                ):
                    raise ValueError(f"Cannot statically resolve runtime ownership in {package_root / '_tier.py'}")
                suite = tier_dir.joinpath(*node.args[0].value.split("."))
                if not any(suite.resolve().is_relative_to(path.resolve()) for path in shipped):
                    raise ValueError(f"Advertised runtime ownership at {suite} is not shipped by its tier")
                _namespace_provider(tier_dir, suite)
                advertised.append(suite)
        suites.extend(advertised)
        for name in wheel.get("packages", []):
            suite = tier_dir / name
            if not suite.resolve().is_relative_to(tier_dir.resolve()):
                raise ValueError(f"Runtime suite ownership at {suite} escapes its tier")
            if not suite.is_dir():
                raise FileNotFoundError(
                    f"{tier_dir.name} ships package '{name}' but {suite} does not exist; "
                    "cannot classify runtime-tested contracts."
                )
            declarations = sorted({path.parent for filename in _PROVIDER_DESCRIPTORS for path in suite.rglob(filename)})
            for declaration in declarations:
                if name == "simready":
                    _namespace_provider(tier_dir, declaration)
                else:
                    _runtime_provider_metadata(declaration)
                if declaration not in suites:
                    suites.append(declaration)
            if name != "simready" and not declarations:
                suites.append(suite)
    # An unreadable suite would silently yield no mappings, which demotes every
    # runtime-tested contract to a static CAP instead of failing.
    if not suites:
        raise FileNotFoundError(
            f"No tier under {TIERS_ROOT} ships a Benchmark test suite; cannot classify runtime-tested contracts."
        )
    return suites


def _discover_runtime_tests() -> dict[str, list[tuple[str, str]]]:
    mappings: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for suite in _runtime_suites():
        metadata = _runtime_provider_metadata(suite)
        provider = metadata["provider"] if metadata is not None else suite.name
        for path in sorted(suite.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            test_name = TEST_NAME_RE.search(text)
            if test_name is None:
                continue
            for match in FEATURE_REF_RE.finditer(text):
                item = (match.group(2), f"{provider}:{test_name.group(1)}")
                if item not in mappings[match.group(1)]:
                    mappings[match.group(1)].append(item)
    return mappings


def _manifest_dependencies(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    dependencies: list[tuple[str, str]] = []
    for entry in manifest.get("dependencies", []):
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ValueError(f"Invalid dependency in {manifest['id']}@{manifest['version']}: {entry}")
        legacy_id, body = next(iter(entry.items()))
        dependencies.append((legacy_id, str(body["version"])))
    return dependencies


def _adapter_reference(legacy_id: str) -> str:
    if legacy_id == "FET_011_RTX":
        legacy_id = "FET_011_STANDARD"
    stem = legacy_id.removeprefix("FET_").lower().replace("_", "-")
    return f"skill:simready-foundation-conform-fet-{stem}"


def _choose_source(
    manifest: dict[str, Any],
    sources: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    candidates = sources.get(_family(manifest["id"]), [])
    if not candidates:
        return None
    target = _version_tuple(manifest["version"])
    compatible = [item for item in candidates if _version_tuple(item["version"]) <= target]
    return max(compatible or candidates, key=lambda item: _version_tuple(item["version"]))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _profile_entry(entry: dict[str, Any]) -> tuple[str, str, bool]:
    optional = bool(entry.get("optional", False))
    keys = [key for key in entry if key != "optional"]
    if len(keys) != 1:
        raise ValueError(f"Invalid legacy profile entry: {entry}")
    legacy_id = keys[0]
    return legacy_id, str(entry[legacy_id]["version"]), optional


def _selector_line(selector: str, optional: bool) -> str:
    suffix = ", optional = true" if optional else ""
    return f'    {{selector = "{selector}"{suffix}}},'


def _write_profile_projection(
    source_path: Path,
    output_path: Path,
    id_map: dict[tuple[str, str], tuple[str, str]],
) -> None:
    with source_path.open("rb") as stream:
        document = tomllib.load(stream)
    lines = ["# Generated Foundations 2 projection. See ../catalog-map.json.", ""]
    for profile_name, versions in document.items():
        lines.append(f"[{profile_name}]")
        for version, body in versions.items():
            feature_entries: list[tuple[str, bool]] = []
            capability_entries: list[tuple[str, bool]] = []
            for entry in body.get("features", []):
                legacy_id, legacy_version, optional = _profile_entry(entry)
                try:
                    kind, new_id = id_map[(legacy_id, legacy_version)]
                except KeyError as exc:
                    raise ValueError(f"{source_path}: unknown {legacy_id}@{legacy_version}") from exc
                target = feature_entries if kind == "feature" else capability_entries
                if (new_id, optional) not in target:
                    target.append((new_id, optional))
            lines.append(f'"{version}" = {{features = [')
            lines.extend(_selector_line(selector, optional) for selector, optional in feature_entries)
            lines.append("], capabilities = [")
            lines.extend(_selector_line(selector, optional) for selector, optional in capability_entries)
            lines.append("]}")
        lines.append("")
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _clear_generated(directory: Path, pattern: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob(pattern):
        if path.is_file():
            path.unlink()


def _tier_package_root(tier_dir: Path) -> Path | None:
    """Return the tier's content package, or ``None`` when the tier has none.

    Package directory names are not uniform: the core and template tiers use a
    ``tier_`` prefix, while the sensors tier is plain ``sensors``. The ``_tier.py``
    descriptor is the marker instead of the directory name, which also keeps
    ``__pycache__`` and loose modules out of the result.
    """
    roots = sorted(path for path in (tier_dir / "simready" / "foundation").glob("*") if (path / "_tier.py").is_file())
    if not roots:
        return None
    if len(roots) > 1:
        raise ValueError(
            f"Tier {tier_dir.name} declares more than one package root: " + ", ".join(root.name for root in roots)
        )
    return roots[0]


def generate() -> dict[str, int]:
    for package_root in _package_roots():
        _assert_generatable(package_root)
    runtime_registry = _discover_runtime_tests()
    manifests: list[dict[str, Any]] = []
    manifest_tiers: dict[tuple[str, str], Path] = {}
    tier_roots: dict[Path, Path] = {}

    for tier_dir in sorted(TIERS_ROOT.glob("simready_foundation_tier_*")):
        package_root = _tier_package_root(tier_dir)
        if package_root is None:
            continue
        tier_roots[tier_dir] = package_root
        feature_dir = package_root / "features"
        for path in sorted(feature_dir.glob("FET_*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            key = (manifest["id"], str(manifest["version"]))
            if key in manifest_tiers:
                raise ValueError(f"Duplicate published feature {key}")
            manifests.append(manifest)
            manifest_tiers[key] = tier_dir

    tests_by_contract: dict[tuple[str, str], list[str]] = {}
    tested_families: set[str] = set()
    for manifest in manifests:
        tests = [
            test
            for constraint, test in runtime_registry.get(manifest["id"], [])
            if _matches_version(str(manifest["version"]), constraint)
        ]
        tests_by_contract[(manifest["id"], str(manifest["version"]))] = sorted(set(tests))
        if tests:
            tested_families.add(_family(manifest["id"]))

    sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest in manifests:
        if manifest["id"].endswith("_STANDARD") and _family(manifest["id"]) in tested_families:
            sources[_family(manifest["id"])].append(manifest)

    id_map: dict[tuple[str, str], tuple[str, str]] = {}
    for manifest in manifests:
        key = (manifest["id"], str(manifest["version"]))
        is_source = manifest in sources.get(_family(manifest["id"]), [])
        is_feature = bool(tests_by_contract[key]) or is_source
        id_map[key] = (
            "feature" if is_feature else "capability",
            _new_id("FET" if is_feature else "CAP", manifest),
        )

    counts = {"features": 0, "capabilities": 0, "profiles": 0}
    catalog_maps: dict[Path, list[dict[str, Any]]] = defaultdict(list)
    for tier_dir, package_root in tier_roots.items():
        output_root = package_root / "foundations2"
        _clear_generated(output_root / "features", "*.json")
        _clear_generated(output_root / "capabilities", "*.json")
        _clear_generated(output_root / "profiles", "*.toml")

    for manifest in manifests:
        key = (manifest["id"], str(manifest["version"]))
        tier_dir = manifest_tiers[key]
        package_root = tier_roots[tier_dir]
        kind, new_id = id_map[key]
        dependencies = _manifest_dependencies(manifest)
        cap_dependencies: list[str] = []
        feature_dependencies: list[str] = []
        for dependency in dependencies:
            dep_kind, dep_id = id_map[dependency]
            (feature_dependencies if dep_kind == "feature" else cap_dependencies).append(dep_id)

        common: dict[str, Any] = {
            "id": new_id,
            "display_name": manifest.get("display_name", manifest["id"]),
            "legacy_identity": {"id": manifest["id"], "version": manifest["version"]},
        }
        if kind == "feature":
            tests = tests_by_contract[key]
            is_source = manifest in sources.get(_family(manifest["id"]), [])
            data = dict(common)
            if is_source:
                data["source"] = True
            elif (source := _choose_source(manifest, sources)) is not None:
                data["source_feature"] = id_map[(source["id"], str(source["version"]))][1]
            if feature_dependencies:
                data["dependencies"] = sorted(set(feature_dependencies))
            if cap_dependencies:
                data["capabilities"] = sorted(set(cap_dependencies))
            requirements = list(manifest.get("requirements", []))
            if tests:
                data["additional_requirements"] = requirements
                data["adapters"] = [_adapter_reference(manifest["id"])]
                data["runtime_tests"] = tests
            else:
                data["requirements"] = requirements
            output = package_root / "foundations2" / "features" / f"{new_id}.json"
            counts["features"] += 1
        else:
            data = dict(common)
            data["requirements"] = list(manifest.get("requirements", []))
            if cap_dependencies:
                data["dependencies"] = sorted(set(cap_dependencies))
            if feature_dependencies:
                data["features"] = sorted(set(feature_dependencies))
            output = package_root / "foundations2" / "capabilities" / f"{new_id}.json"
            counts["capabilities"] += 1
        _write_json(output, data)
        catalog_maps[package_root].append(
            {
                "legacy_id": manifest["id"],
                "legacy_version": manifest["version"],
                "legacy_page": _legacy_page(manifest),
                "kind": kind,
                "id": new_id,
                "runtime_tests": tests_by_contract[key],
            }
        )

    for tier_dir, package_root in tier_roots.items():
        profile_dir = package_root / "profiles"
        output_profile_dir = package_root / "foundations2" / "profiles"
        for source_path in sorted(profile_dir.glob("*.toml")):
            output_path = output_profile_dir / source_path.name
            _write_profile_projection(source_path, output_path, id_map)
            counts["profiles"] += 1
        mapping = {
            "schema": "simready-foundations2-catalog-map-v1",
            "version_encoding": "published semantic version dots become hyphens",
            "contracts": sorted(
                catalog_maps[package_root],
                key=lambda item: (item["legacy_id"], item["legacy_version"]),
            ),
        }
        _write_json(package_root / "foundations2" / "catalog-map.json", mapping)
        (package_root / "foundations2" / "README.md").write_text(
            "# Foundations 2 contract projection\n\n"
            "Generated by `nv_core/tiers/_tooling/migrate_foundations2_catalog.py`. "
            "FET entries are runtime-tested contracts or their source FETs; "
            "CAP entries are standalone static contracts. Published sibling "
            "directories remain Foundations 1 compatibility input.\n",
            encoding="utf-8",
        )

    return counts


STAGING_DIRNAME = "foundations2"


def _package_roots() -> list[Path]:
    roots: list[Path] = []
    for tier_dir in sorted(TIERS_ROOT.glob("simready_foundation_tier_*")):
        package_root = _tier_package_root(tier_dir)
        if package_root is not None:
            roots.append(package_root)
    return roots


def _contract_stem(new_id: str) -> str:
    """``FET004_Multibody.PhysX.0-4-0`` -> ``FET004_Multibody.PhysX``.

    A contract's markdown is shared by every version of it, so the page is named
    after the identity minus the version segment.
    """
    return new_id.rsplit(".", 1)[0]


def _staged_catalog_map(package_root: Path) -> list[dict[str, Any]]:
    path = package_root / STAGING_DIRNAME / "catalog-map.json"
    if not path.is_file():
        raise FileNotFoundError(f"No generated catalog at {path}; generate before relocating.")
    return json.loads(path.read_text(encoding="utf-8"))["contracts"]


def _assert_generatable(package_root: Path) -> None:
    """Refuse to generate on a tree that has already been relocated.

    Generation projects from the Foundations 1 manifests that relocation deletes.
    On a relocated tree it would find none, write an empty catalog into a fresh
    staging directory, and report success. Relocation is the only step that puts
    ``catalog-map.json`` at the package root, so that file is the marker.
    """
    if (package_root / "catalog-map.json").is_file():
        raise ValueError(
            f"{package_root} is already relocated: its catalog-map.json sits at the package "
            "root and the Foundations 1 manifests generation reads are gone. Undo the "
            "relocation before generating."
        )


def _assert_relocatable(package_root: Path) -> None:
    """Refuse to relocate a tree that is already Foundations 2 shaped.

    :func:`generate` projects *from* the Foundations 1 manifests in
    ``features/``, so a second relocation would have nothing to read. Re-running
    means reverting to the Foundations 1 layout first, not relocating twice.
    """
    if (package_root / "capabilities").exists():
        raise ValueError(
            f"{package_root} already has a capabilities/ contract directory; "
            "revert the relocation before running it again."
        )
    if not (package_root / STAGING_DIRNAME).is_dir():
        raise FileNotFoundError(f"Nothing staged to relocate at {package_root / STAGING_DIRNAME}.")


def _relocation_plan(package_root: Path) -> dict[str, list]:
    """Compute the moves and deletions that flatten the staged catalog.

    Raises rather than dropping anything: an undocumented contract, two pages
    competing for one destination, or a page that would overwrite another are
    all authoring errors that must be fixed before the layout changes.
    """
    # Keyed by page rather than legacy ID: links name pages, and a page is not
    # always named after its contract's ID. Every version of a contract shares
    # its page, so a page may appear many times but must always land in one place.
    targets: dict[str, tuple[str, str]] = {}
    for contract in _staged_catalog_map(package_root):
        page = contract.get("legacy_page", contract["legacy_id"])
        section = "features" if contract["kind"] == "feature" else "capabilities"
        target = (section, _contract_stem(contract["id"]))
        if targets.setdefault(page, target) != target:
            raise ValueError(
                f"Page '{page}' documents both {targets[page][1]} and {target[1]}; "
                "one page cannot relocate to two contracts."
            )

    markdown: list[tuple[Path, Path]] = []
    for path in sorted((package_root / "features").glob("*.md")):
        if path.stem not in targets:
            raise ValueError(
                f"{path} documents '{path.stem}', which has no generated contract; " "relocation would drop the page."
            )
        section, stem = targets[path.stem]
        markdown.append((path, package_root / section / f"{stem}.md"))

    claimed: dict[Path, Path] = {}
    for source, destination in markdown:
        if destination in claimed:
            raise ValueError(f"{source} and {claimed[destination]} both relocate to {destination}.")
        claimed[destination] = source
        if destination.exists() and destination != source:
            raise ValueError(f"{source} would overwrite the existing {destination}.")

    staging = package_root / STAGING_DIRNAME
    contracts: list[tuple[Path, Path]] = []
    for section, pattern in (("features", "*.json"), ("capabilities", "*.json"), ("profiles", "*.toml")):
        contracts += [(path, package_root / section / path.name) for path in sorted((staging / section).glob(pattern))]
    # Provenance outlives the staging directory: it is the only file stating the
    # legacy-to-dotted mapping and the FET/CAP split together.
    contracts.append((staging / "catalog-map.json", package_root / "catalog-map.json"))

    # The Foundations 1 profile TOMLs share their names with the projections, so
    # they are replaced in place; only the feature manifests need removing.
    remove = sorted((package_root / "features").glob("FET_*.json"))
    return {"markdown": markdown, "contracts": contracts, "remove": remove, "targets": targets}


# A Foundations 1 page stem: `FET_003_PHYSX`, or the AIF tier's `FET_201-connection_points`.
_LEGACY_PAGE = r"FET_\d+[-_][A-Za-z0-9_]+"

_CONTRACT_LINK_RE = re.compile(rf"\((?:\./)?({_LEGACY_PAGE})\.md(#[^)]*)?\)")


def _rewrite_contract_links(text: str, containing_section: str, targets: dict[str, tuple[str, str]]) -> tuple[str, int]:
    """Repoint links between contract pages after the FET/CAP split.

    Contract pages link each other by bare filename because they used to share
    one directory. Both the filename and the relative prefix can change, since a
    page's target may have been renamed and moved to the other contract
    directory.

    Only link *targets* are rewritten. Link labels and surrounding prose still
    name Foundations 1 IDs and versions; that is an editorial pass, not a
    mechanical one.
    """
    rewrites = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        page, fragment = match.group(1), match.group(2) or ""
        target = targets.get(page)
        if target is None:
            return match.group(0)
        section, stem = target
        prefix = "" if section == containing_section else f"../{section}/"
        rewrites += 1
        return f"({prefix}{stem}.md{fragment})"

    return _CONTRACT_LINK_RE.sub(replace, text), rewrites


# Only the trailing `features/<legacy page>.md` is matched, so whatever path
# precedes it survives untouched. That one pattern covers the relative links in
# profile pages, guides and Benchmark docs as well as the repository-root paths
# the conform skills cite. A link may also omit `.md` where it ends, as the AIF
# profile page's do; those gain it, because a dotted contract stem without an
# extension reads as a file with a `.PhysX` or `.OpenUSD` suffix.
_OUTBOUND_LINK_RE = re.compile(rf"features/({_LEGACY_PAGE})(?:\.md|(?=[)#]))")

# A versioned manifest reference. Both the legacy ID and its version are needed,
# because each published version projects to its own contract file.
_OUTBOUND_MANIFEST_RE = re.compile(r"features/(FET_\d+_[A-Z0-9_]+)-(\d+(?:\.\d+)*)\.json")

_OUTBOUND_ROOTS = ("nv_core", "skills")
_OUTBOUND_SKIP_DIRS = frozenset({"__pycache__", "_build", "_compiler", "_repo", ".git"})
# Both migration guides name Foundations 1 paths deliberately, to describe the
# layout being replaced.
_OUTBOUND_SKIP_FILES = frozenset({"foundations2-layout-migration.md", "foundations2-catalog-migration.md"})


def _outbound_markdown_files(contract_dirs: set[Path]) -> list[Path]:
    """Markdown that links *into* the contract directories without moving itself.

    Profile pages, guides, Benchmark suite docs and conform skills stay where
    they are, so their links are repointed in place rather than rewritten in
    flight the way a moving contract page's are.

    The walk is scoped to the content roots deliberately. A repository-wide
    search would reach the git-ignored ``_git/`` checkout, which holds an
    unrelated Foundations 1 tree that must not be rewritten.
    """
    files: list[Path] = []
    for root in _OUTBOUND_ROOTS:
        for directory, subdirs, names in os.walk(REPO_ROOT / root):
            subdirs[:] = sorted(name for name in subdirs if name not in _OUTBOUND_SKIP_DIRS)
            current = Path(directory)
            if current in contract_dirs:
                continue
            for name in sorted(names):
                if name.endswith(".md") and name not in _OUTBOUND_SKIP_FILES:
                    files.append(current / name)
    return files


def _rewrite_outbound_contract_links(
    text: str,
    targets: dict[str, tuple[str, str]],
    manifest_targets: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> tuple[str, int]:
    """Repoint one non-moving file's references to relocated contracts.

    Both a contract's page and its versioned manifests are repointed. A
    reference the generator did not emit a contract for is left alone, which is
    what keeps pre-existing bad paths such as
    ``features/FET_022-driven_joints.md`` from being rewritten into something
    equally broken.
    """
    rewrites = 0

    def replace_page(match: re.Match[str]) -> str:
        nonlocal rewrites
        target = targets.get(match.group(1))
        if target is None:
            return match.group(0)
        section, stem = target
        rewrites += 1
        return f"{section}/{stem}.md"

    def replace_manifest(match: re.Match[str]) -> str:
        nonlocal rewrites
        target = (manifest_targets or {}).get((match.group(1), match.group(2)))
        if target is None:
            return match.group(0)
        section, new_id = target
        rewrites += 1
        return f"{section}/{new_id}.json"

    # Manifests first: the page pattern would otherwise not match them, but
    # keeping the order explicit makes the two rewrites independent.
    text = _OUTBOUND_MANIFEST_RE.sub(replace_manifest, text)
    return _OUTBOUND_LINK_RE.sub(replace_page, text), rewrites


def _catalog_contracts(package_root: Path) -> list[dict[str, Any]]:
    """A tier's catalog map, wherever it currently lives.

    The map is generated into the staging directory and moved to the package
    root by relocation, so reading both locations lets the outbound pass run
    either as part of relocation or standalone against a relocated tree.
    """
    for candidate in (
        package_root / "catalog-map.json",
        package_root / STAGING_DIRNAME / "catalog-map.json",
    ):
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))["contracts"]
    return []


def _outbound_targets() -> tuple[dict[str, tuple[str, str]], dict[tuple[str, str], tuple[str, str]]]:
    """Page and manifest destinations, merged across every tier.

    One merged map, because a guide or skill may reference contracts from any
    tier. Legacy IDs do not collide: `generate` refuses duplicates.
    """
    pages: dict[str, tuple[str, str]] = {}
    manifests: dict[tuple[str, str], tuple[str, str]] = {}
    for package_root in _package_roots():
        for contract in _catalog_contracts(package_root):
            if "legacy_id" not in contract:
                continue
            section = "features" if contract["kind"] == "feature" else "capabilities"
            page = contract.get("legacy_page", contract["legacy_id"])
            pages[page] = (section, _contract_stem(contract["id"]))
            manifests[(contract["legacy_id"], contract["legacy_version"])] = (
                section,
                contract["id"],
            )
    return pages, manifests


def relink_outbound_references(*, dry_run: bool = False) -> dict[str, int]:
    """Repoint contract references in files the relocation does not move."""
    pages, manifests = _outbound_targets()
    contract_dirs = {
        directory
        for package_root in _package_roots()
        for directory in (package_root / "features", package_root / "capabilities")
    }

    summary = {"outbound_links": 0, "outbound_files": 0}
    for path in _outbound_markdown_files(contract_dirs):
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        rewritten, count = _rewrite_outbound_contract_links(text, pages, manifests)
        if not count:
            continue
        summary["outbound_links"] += count
        summary["outbound_files"] += 1
        if dry_run:
            print(f"  relink {path.relative_to(REPO_ROOT)} ({count})")
            continue
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(rewritten)
    return summary


SHARED_DOCS_ROOT = REPO_ROOT / "nv_core" / "sr_specs" / "docs" / "shared"

_TOCTREE_ENTRY_RE = re.compile(r"^(?P<label>.*?)\s*<(?P<target>[^>]+)>$")
# A generated contract page, under either identifier scheme. Entries pointing at
# one are replaced; everything else in an existing toctree is preserved.
_CONTRACT_TARGET_RE = re.compile(r"^(?:FET|CAP)_?\d+")

_HUB_INTROS = {
    "features": (
        "This section lists the features from every SimReady Foundation\n"
        "[tier](../../guides/tiers.md) together. A feature is a runtime-tested contract.\n"
        "The **Runtime** column is the runtime a variant targets, which is independent\n"
        "of the tier that owns the contract.\n"
    ),
    "capabilities": (
        "This section lists the capabilities from every SimReady Foundation\n"
        "[tier](../../guides/tiers.md) together. A capability is a static contract: a\n"
        "requirement bundle with no runtime tests. The **Runtime** column is the\n"
        "runtime a variant targets, which is independent of the tier that owns the\n"
        "contract.\n"
    ),
}


def _hub_contract_rows(section: str) -> list[tuple[str, str, str, list[str]]]:
    """``(stem, display name, runtime, versions)`` for one contract section.

    Read from the contract manifests rather than transcribed, so publishing a
    contract version does not also mean hand-editing a hub. One page covers
    every version of its contract, hence the version list.
    """
    by_stem: dict[str, dict[str, Any]] = {}
    for package_root in _package_roots():
        for path in sorted((package_root / section).glob("*.json")):
            contract = json.loads(path.read_text(encoding="utf-8"))
            new_id = contract["id"]
            stem = _contract_stem(new_id)
            entry = by_stem.setdefault(stem, {"versions": [], "display_name": stem})
            entry["versions"].append(new_id.rsplit(".", 1)[1])
            entry["display_name"] = contract.get("display_name", stem)
    return [
        (stem, data["display_name"], stem.split(".")[1] if "." in stem else "OpenUSD", sorted(data["versions"]))
        for stem, data in sorted(by_stem.items())
    ]


def _hub_preserved_entries(path: Path) -> tuple[list[str], list[str]]:
    """Non-contract toctree entries of an existing hub, split around contracts.

    The features hub carries a dependency-graph entry ahead of the contracts and
    draft feature cards after them. Emitting only contract entries would drop
    both silently and orphan those pages, so they are read back out and kept in
    place rather than hard-coded here.
    """
    if not path.is_file():
        return [], []
    entries: list[tuple[str, bool]] = []
    inside = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("```{toctree}"):
            inside = True
            continue
        if inside and line.startswith("```"):
            break
        if not inside or not line or line.startswith(":"):
            continue
        match = _TOCTREE_ENTRY_RE.match(line)
        if match is None:
            continue
        target = match.group("target")
        is_contract = "/" not in target and _CONTRACT_TARGET_RE.match(target) is not None
        entries.append((line, is_contract))

    contract_positions = [index for index, (_, is_contract) in enumerate(entries) if is_contract]
    if not contract_positions:
        return [line for line, _ in entries], []
    first, last = contract_positions[0], contract_positions[-1]
    leading = [line for line, is_contract in entries[:first] if not is_contract]
    trailing = [line for line, is_contract in entries[last + 1 :] if not is_contract]
    return leading, trailing


def _contract_page(section: str, stem: str) -> Path:
    """The tier page that documents contract ``stem``."""
    pages = [package_root / section / f"{stem}.md" for package_root in _package_roots()]
    return next((page for page in pages if page.is_file()), pages[0])


def write_contract_hubs() -> dict[str, int]:
    """Regenerate the shared features and capabilities hub pages."""
    written: dict[str, int] = {}
    for section, intro in _HUB_INTROS.items():
        rows = _hub_contract_rows(section)
        path = SHARED_DOCS_ROOT / section / f"{section}.md"
        leading, trailing = _hub_preserved_entries(path)

        lines = [f"# {section.capitalize()}", "", intro.rstrip(), "", "## Status Dashboard", ""]
        lines += ["| Name | Runtime | Versions | Contract |", "|---|---|---|---|"]
        for stem, display_name, runtime, versions in rows:
            page = Path(os.path.relpath(_contract_page(section, stem), path.parent)).as_posix()
            lines.append(f"| [{display_name}]({page}) | {runtime} | " f"{', '.join(versions)} | `{stem}` |")
        lines += ["", "```{toctree}", ":maxdepth: 1", ":hidden:", ""]
        lines += leading
        lines += [f"{display_name} <{stem}>" for stem, display_name, _, _ in rows]
        lines += trailing
        lines += ["```", ""]

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines))
        written[section] = len(rows)
    return written


def relocate(*, dry_run: bool = False) -> dict[str, int]:
    """Flatten each tier's staged catalog into features/, capabilities/, profiles/."""
    summary = {
        "markdown": 0,
        "contracts": 0,
        "removed": 0,
        "links_rewritten": 0,
        "outbound_links": 0,
        "outbound_files": 0,
    }

    # Plan and validate every tier before mutating any of them, so a tier that
    # refuses does not leave earlier tiers half-relocated. The outbound pass
    # also needs one merged target map: a guide or skill may link contracts from
    # any tier, and legacy IDs are unique across tiers because `generate`
    # refuses duplicates.
    plans = []
    targets: dict[str, tuple[str, str]] = {}
    contract_dirs: set[Path] = set()
    for package_root in _package_roots():
        _assert_relocatable(package_root)
        plan = _relocation_plan(package_root)
        plans.append((package_root, plan))
        targets.update(plan["targets"])
        contract_dirs.update({package_root / "features", package_root / "capabilities"})

    for package_root, plan in plans:
        summary["markdown"] += len(plan["markdown"])
        summary["contracts"] += len(plan["contracts"])
        summary["removed"] += len(plan["remove"])

        for source, destination in plan["markdown"]:
            with source.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
            rewritten, count = _rewrite_contract_links(text, destination.parent.name, plan["targets"])
            summary["links_rewritten"] += count
            if dry_run:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8", newline="") as handle:
                handle.write(rewritten)
            source.unlink()

        if dry_run:
            for source, destination in plan["markdown"] + plan["contracts"]:
                print(f"  move   {source.relative_to(package_root)} -> {destination.relative_to(package_root)}")
            for path in plan["remove"]:
                print(f"  remove {path.relative_to(package_root)}")
            continue

        for path in plan["remove"]:
            path.unlink()
        for source, destination in plan["contracts"]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        shutil.rmtree(package_root / STAGING_DIRNAME)

    summary.update(relink_outbound_references(dry_run=dry_run))

    if dry_run:
        print("  hubs   features.md and capabilities.md would be regenerated")
    else:
        summary["hubs"] = sum(write_contract_hubs().values())
    return summary


def extend_static_catalogs(*, dry_run: bool = False) -> dict[str, int]:
    """Project static legacy additions on branches rebased onto a relocated tier.

    Native definitions and existing profile versions keep their contracts.
    Runtime families require explicit native authoring rather than guessing
    their test, source-feature, and adapter configuration. Validate the complete
    extension before writing any files.
    """
    roots = list(_package_roots())
    mappings = {}
    identities = {}
    targets = {}
    tested_families = set()
    for package_root in roots:
        map_path = package_root / "catalog-map.json"
        if not map_path.is_file():
            if not list((package_root / "features").glob("FET_*.json")):
                continue  # Native-only tiers have no legacy projection map.
            raise ValueError(f"{package_root}: relocate before extending the native catalog")
        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        mappings[package_root] = mapping
        for item in mapping["contracts"]:
            if "legacy_id" not in item:
                if item["kind"] == "feature":
                    tested_families.add(re.match(r"FET(\d+)", item["id"])[1])
                continue
            identities[(item["legacy_id"], item["legacy_version"])] = (item["kind"], item["id"])
            targets[item.get("legacy_page", item["legacy_id"])] = (
                "features" if item["kind"] == "feature" else "capabilities",
                _contract_stem(item["id"]),
            )
            if item["kind"] == "feature":
                tested_families.add(_family(item["legacy_id"]))
    runtime_tests = _discover_runtime_tests()
    additions = []
    for package_root in roots:
        for path in sorted((package_root / "features").glob("FET_*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            key = (manifest["id"], manifest["version"])
            if key in identities:
                raise ValueError(f"{path}: identity already exists in the native catalog")
            if _family(manifest["id"]) in tested_families or any(
                _matches_version(manifest["version"], constraint)
                for constraint, _ in runtime_tests.get(manifest["id"], [])
            ):
                raise ValueError(f"{path}: runtime family requires explicit native feature authoring")
            new_id = _new_id("CAP", manifest)
            identities[key] = ("capability", new_id)
            targets[_legacy_page(manifest)] = ("capabilities", _contract_stem(new_id))
            additions.append((package_root, path, manifest, new_id))
    writes = []
    removals = []
    pages = {}
    for package_root, path, manifest, new_id in additions:
        data = {
            "id": new_id,
            "display_name": manifest.get("display_name", manifest["id"]),
            "legacy_identity": {"id": manifest["id"], "version": manifest["version"]},
            "requirements": manifest.get("requirements", []),
        }
        for key in _manifest_dependencies(manifest):
            kind, dependency = identities[key]
            data.setdefault("features" if kind == "feature" else "dependencies", []).append(dependency)
        destination = package_root / "capabilities" / f"{new_id}.json"
        if destination.exists():
            raise ValueError(f"Refusing to overwrite native contract {destination}")
        writes.append((destination, json.dumps(data, indent=2) + "\n"))
        removals.append(path)
        source = path.parent / f"{_legacy_page(manifest)}.md"
        page = package_root / "capabilities" / f"{_contract_stem(new_id)}.md"
        if source.is_file():
            if page.exists():
                raise ValueError(f"Refusing to overwrite native page {page}")
            pages[source] = page
        mappings[package_root]["contracts"].append(
            {
                "legacy_id": manifest["id"],
                "legacy_version": manifest["version"],
                "legacy_page": _legacy_page(manifest),
                "kind": "capability",
                "id": new_id,
                "runtime_tests": [],
            }
        )
    for source, destination in pages.items():
        rewritten, _ = _rewrite_contract_links(source.read_text(encoding="utf-8"), "capabilities", targets)
        writes.append((destination, rewritten))
        removals.append(source)
    profiles = 0
    for package_root in roots:
        for path in sorted((package_root / "profiles").glob("*.toml")):
            original = path.read_text(encoding="utf-8")
            document = tomllib.loads(original)
            rewritten = original
            for versions in document.values():
                for version, body in versions.items():
                    entries = body.get("features", [])
                    if all("selector" in entry for entry in entries):
                        continue
                    features, capabilities = [], list(body.get("capabilities", []))
                    for entry in entries:
                        if "selector" in entry:
                            features.append(entry)
                            continue
                        legacy_id, legacy_version, optional = _profile_entry(entry)
                        kind, new_id = identities[(legacy_id, legacy_version)]
                        selector = {"selector": new_id}
                        if optional:
                            selector["optional"] = True
                        (features if kind == "feature" else capabilities).append(selector)
                    lines = [f'"{version}" = {{features = [']
                    lines.extend(_selector_line(item["selector"], item.get("optional", False)) for item in features)
                    lines.append("], capabilities = [")
                    lines.extend(_selector_line(item["selector"], item.get("optional", False)) for item in capabilities)
                    lines.append("]}\n")
                    pattern = r'^"' + re.escape(version) + r'"\s*=.*?(?=^"|^\[|\Z)'
                    rewritten, count = re.subn(pattern, lambda _: "\n".join(lines), rewritten, flags=re.M | re.S)
                    if count != 1:
                        raise ValueError(f"{path}: cannot unambiguously project profile version {version}")
            if rewritten != original:
                writes.append((path, rewritten))
                profiles += 1
    changed_roots = {item[0] for item in additions}
    for package_root in changed_roots:
        mapping = mappings[package_root]
        # Preserve existing entry order; additions are enumerated deterministically.
        writes.append((package_root / "catalog-map.json", json.dumps(mapping, indent=2) + "\n"))
    if not dry_run:
        for path, contents in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        for path in removals:
            path.unlink()
    return {"capabilities": len(additions), "profiles": profiles, "pages": len(pages)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project and optionally flatten the Foundations 2 catalog.")
    parser.add_argument(
        "--extend-static",
        action="store_true",
        help="Project static legacy additions and their profile pins into an already-relocated catalog.",
    )
    parser.add_argument(
        "--relocate",
        action="store_true",
        help=(
            "Destructive: replace the Foundations 1 features/ and profiles/ content with the "
            "staged Foundations 2 catalog and delete the staging directory. Requires a prior "
            "generate run; off by default so no routine task can destroy the published tree."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview --relocate, --extend-static, or --relink without writing files.",
    )
    parser.add_argument(
        "--write-hubs",
        action="store_true",
        help=(
            "Regenerate the shared features/ and capabilities/ hub pages from the relocated "
            "catalogs. Runs as part of --relocate; standalone for an already-relocated tree."
        ),
    )
    parser.add_argument(
        "--relink",
        action="store_true",
        help=(
            "Repoint contract references in files the relocation does not move (guides, "
            "profile pages, Benchmark docs, conform skills). Runs as part of --relocate; "
            "standalone for an already-relocated tree."
        ),
    )
    args = parser.parse_args()
    if args.extend_static:
        print(json.dumps(extend_static_catalogs(dry_run=args.dry_run), indent=2))
    elif args.relink:
        print(json.dumps(relink_outbound_references(dry_run=args.dry_run), indent=2))
    elif args.write_hubs:
        print(json.dumps(write_contract_hubs(), indent=2))
    elif args.relocate:
        print(json.dumps(relocate(dry_run=args.dry_run), indent=2))
    else:
        print(json.dumps(generate(), indent=2))
