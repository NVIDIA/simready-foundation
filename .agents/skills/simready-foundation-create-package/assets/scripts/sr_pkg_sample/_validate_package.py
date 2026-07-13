"""Local ``validate_package`` — package-manifest validation without the branch wheel.

Provides package-manifest validation using only ``omni.asset_validator``
public APIs.

Most of the code here is destined for the future ``simready.package`` (or
``simready.publish``) library, which might share engine-setup helpers with
``simready.validate``.  Each section is annotated:

* **[sv-copy]** — straight copy of a private helper from
  ``simready.validate.api``. These should be shared in some
  way with simready.validate?
* **[new — simready.package]** — new code that belongs in
  ``simready.package``, not in ``simready.validate``.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path

from omni.asset_validator import (
    Capability,
    CapabilityRegistry,
    Issue,
    IssueSeverity,
    ProfileRegistry,
    RequirementsRegistry,
    ValidationEngine,
)

__all__ = [
    "PackageValidationConfig",
    "PackageValidationResult",
    "_build_validation_engine",
    "validate_package",
]

logger = logging.getLogger("sr_pkg_sample")


# -- [sv-copy] helpers from simready.validate.api (master) -----------------
#
# Almost-straight copies of ``_copy_capability_with_dependencies`` and
# ``_build_features_validation_summary`` from
# simready-explorer/source/libraries/validate/src/validate/api.py.
# When simready.package is created, factor these into a shared internal
# module (e.g. simready._engine_helpers) so both simready.validate and
# simready.package import them from one place.

def _copy_capability_with_dependencies(  # [sv-copy]
    capability: Capability,
    *,
    log: bool = False,
) -> tuple[Capability, set[Capability]]:
    capability_copy = copy.copy(capability)
    dependency_set: set[Capability] = set()

    if capability_copy.custom_data:
        queue = list(capability_copy.custom_data.get("dependencies", []))
        seen: set[str] = set()

        while queue:
            entry = queue.pop(0)
            try:
                dep_id = list(entry.keys())[0]
                dep_version = list(entry.values())[0].get("version", "")
            except Exception as exc:
                logger.error("Bad dependency entry %s: %s", entry, exc)
                continue

            key = f"{dep_id}_{dep_version}"
            if key in seen:
                continue
            seen.add(key)

            dep = CapabilityRegistry().find(dep_id, dep_version)
            if dep:
                if log:
                    logger.info("  Feature dependency: %s (%s)", dep.id, dep.version)
                dependency_set.add(dep)
                capability_copy.requirements.extend(dep.requirements)
                if dep.custom_data:
                    queue.extend(dep.custom_data.get("dependencies", []))
            elif log:
                logger.error("  Feature dependency not found: %s", key)

    capability_copy.requirements = list(set(capability_copy.requirements))
    return capability_copy, dependency_set


def _build_features_summary(  # [sv-copy] but patched to include issues by code
    issues: list[Issue],
    profile_id: str,
    profile_version: str,
) -> dict[str, dict]:
    issues_missing_requirement: set = set()
    failed_requirements: set[str] = set()
    issues_by_code: dict[str, list[str]] = {}

    for issue in issues:
        if issue.requirement is None:
            if issue.rule is not None:
                issues_missing_requirement.add(issue.rule)
        else:
            failed_requirements.add(issue.requirement.code)
            issues_by_code.setdefault(issue.requirement.code, []).append(
                issue
            )

    profile = ProfileRegistry().find_profile(profile_id, profile_version)
    if profile is None:
        return {}

    features: list[Capability] = []
    for capability in profile.capabilities:
        feat_copy, deps = _copy_capability_with_dependencies(capability)
        features.append(feat_copy)
        for dep in deps:
            if all(not (dep.id == f.id and dep.version == f.version) for f in features):
                features.append(dep)

    for feature in features:
        for req in feature.requirements:
            if RequirementsRegistry().get_validator(req) in issues_missing_requirement:
                failed_requirements.add(req.code)

    summary: dict[str, dict] = {}
    for feature in features:
        failing = [r.code for r in feature.requirements if r.code in failed_requirements]
        entry: dict = {
            "version": feature.version,
            "dependencies": str(feature.custom_data.get("dependencies", [])),
            "passed": not failing,
        }
        if failing:
            entry["failing requirements"] = str(failing)
            entry["issues"] = {
                code: issues_by_code[code]
                for code in failing
                if code in issues_by_code
            }
        summary[feature.id] = entry

    return summary


# -- [new — simready.package] public API ------------------------------------
#
# validate_package() is the package-level counterpart of
# simready.validate.validate_asset().  The engine-setup block (find
# profile → copy capabilities → enable on engine) is shared with
# validate_asset; the difference is that validate_package passes a
# string path to engine.validate() instead of a Usd.Stage, relying on
# the SimReadyPackageFormat handler registered by simready_foundations.

@dataclass
class PackageValidationConfig:
    """Mirrors ``simready.validate.AssetValidationConfig`` for packages.

    ``write_metadata`` is accepted for signature parity but ignored —
    there is no USD stage to stamp.
    """

    asset_path: str
    profile_id: str | None = None
    profile_version: str | None = None
    write_metadata: bool = False


@dataclass
class PackageValidationResult:
    """Minimal result type matching the ``features_summary`` interface
    expected by :func:`~sr_pkg_sample._conformance_writer.build_asset_results`.

    Analogous to ``simready.validate.AssetValidationResult`` but for
    package-level (non-USD) validation.  Future ``simready.package``
    should define its own first-class result type here.
    """

    asset_path: str
    profile_id: str
    profile_version: str
    features_summary: dict[str, dict]


def _build_validation_engine(
    profile_id: str,
    profile_version: str,
) -> ValidationEngine | None:
    """Construct a ``ValidationEngine`` configured for a given profile.

    Looks up *profile_id* / *profile_version* in ``ProfileRegistry``,
    instantiates a fresh engine with ``init_rules=False`` (so only the
    profile's capabilities and any extra rules added by the caller are
    enabled), and enables every capability in the profile after
    expanding capability dependencies.

    Returns ``None`` (and logs an error) when the profile cannot be
    resolved. Callers that need to bolt additional rules onto the
    engine — tests, future ``simready.package`` integrations — can use
    ``engine.enable_rule(rule_class)`` on the returned object before
    calling ``engine.validate(...)``.
    """
    profile = ProfileRegistry().find_profile(profile_id, profile_version)
    if not profile:
        logger.error(
            "Profile '%s' version '%s' not found.", profile_id, profile_version,
        )
        return None

    engine = ValidationEngine(init_rules=False, variants=False)
    for capability in sorted(profile.capabilities, key=lambda c: c.id):
        cap_copy, _ = _copy_capability_with_dependencies(capability, log=True)
        engine.enable_capability(cap_copy)
    return engine


def validate_package(
    validation_config: PackageValidationConfig,
) -> PackageValidationResult | None:
    """Validate a SimReady package manifest against a profile.

    Signature mirrors ``simready.validate.validate_asset(config)``.
    The ``SimReadyPackageFormat`` handler registered by the packaging
    capability in ``simready_foundations`` makes the engine accept the
    JSON manifest as a non-USD asset.
    """
    asset_path = validation_config.asset_path
    profile_id = validation_config.profile_id
    profile_version = validation_config.profile_version

    path = Path(asset_path)
    if not path.is_file():
        logger.error("File does not exist: %s", path)
        return None

    if not profile_id or not profile_version:
        logger.error("profile_id and profile_version are required for package validation.")
        return None

    engine = _build_validation_engine(profile_id, profile_version)
    if engine is None:
        return None

    results = engine.validate(asset_path)

    failure_issues: list[Issue] = []
    for issue in results.issues().filter_by(
        lambda i: i.severity in (IssueSeverity.ERROR, IssueSeverity.FAILURE),
    ):
        failure_issues.append(issue)

    features_summary = _build_features_summary(
        failure_issues, profile_id, profile_version,
    )

    return PackageValidationResult(
        asset_path=asset_path,
        profile_id=profile_id,
        profile_version=profile_version,
        features_summary=features_summary,
    )
