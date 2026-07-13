"""Post-build validation: does this package conform to the SimReady standard?

Drives :func:`simready.validate.validate_package` over a finished
package-definition file (``com.nvidia.simready.packaging.json``) and
returns a :class:`PostValidationResult` with the per-feature
pass/fail detail.

This is the third (and last) phase of the SimReady packaging workflow,
running after the package has been written to its repo by the create
step.

When ``write_evidence=True``, the results are also persisted as
``.metadata/com.nvidia.simready.conformance.{profile}@{ver}.json``
evidence files next to the package definition.  Evidence files are
**not** covered by ``package_hash`` (they are post-creation artefacts).

``simready.validate.initialize`` must already have run before
:func:`post_validate` is called — see the README for the one-time
setup snippet.
"""

from __future__ import annotations

from pathlib import Path

import omni.asset_validator as _av
import simready.validate as sv

from ._conformance_writer import (
    build_asset_results,
    write_conformance_metadata,
)
from ._validate_package import PackageValidationConfig, validate_package
from .errors import UsageError, ValidationFailed
from .results import PostValidationResult

PROFILE_ID = "Package"
PROFILE_VERSION = "1.0.0"


def _check_asset_validator_version() -> None:
    """Raise :class:`UsageError` if omniverse-asset-validator is too old."""
    if not hasattr(_av, "register_format"):
        installed = getattr(_av, "__version__", "unknown")
        raise UsageError(
            f"omniverse-asset-validator does not support package "
            f"validation (installed version: {installed}). This script "
            f"requires the AssetFormat API (register_format / "
            f"FormatDependency / BaseRuleChecker.CheckFormatDependency), "
            f"available in omniverse-asset-validator >= 1.18.0. Re-run "
            f"setup_venv.sh (optionally with --asset-validator-wheel pointing "
            f"at a locally-built wheel) to get a compatible version."
        )


def _validate_one_profile(
    package_def: Path,
    profile_id: str,
) -> tuple[list[str], list[tuple[str, sv.AssetValidationResult | None]]]:
    """Run validation for a single profile.

    Returns ``(failed_feature_ids, [(rel_path, result), ...])``.
    """
    result = validate_package(PackageValidationConfig(
        asset_path=str(package_def),
        profile_id=profile_id,
        profile_version=PROFILE_VERSION,
    ))

    if result is None:
        raise RuntimeError(
            f"simready.validate returned no result for {package_def}"
        )

    features = result.features_summary
    if not features:
        raise RuntimeError(
            f"no features evaluated for profile "
            f"{profile_id!r} v{PROFILE_VERSION}"
        )

    failed_features: list[str] = []
    for fid in sorted(features):
        if not bool(features[fid].get("passed")):
            failed_features.append(fid)

    rel = package_def.name
    return failed_features, [(rel, result)]


async def post_validate(
    package_def: Path,
    *,
    profiles: list[str] | None = None,
    write_evidence: bool = False,
) -> PostValidationResult:
    """Validate ``package_def`` against one or more package-level profiles.

    Returns a :class:`PostValidationResult` whose ``.results`` dict
    maps each profile ID to ``[(rel_path, AssetValidationResult)]``
    pairs.  Inspect ``result.passed`` or ``result.failed_features``
    for the overall outcome; drill into
    ``AssetValidationResult.features_summary`` for per-feature detail.

    Parameters
    ----------
    package_def:
        Path to a ``com.nvidia.simready.packaging.json`` written by the
        create step (or any other SimReady-conformant packager).
    profiles:
        Profile IDs to validate against.  Defaults to ``["Package"]``
        (which includes FET030 core and FET032 introspection/BOM).
        Use ``["Package-NoBOM"]`` for packages without a BOM.
    write_evidence:
        When ``True``, write a conformance JSON into ``.metadata/``
        next to the package definition for each validated profile.
        These evidence files are **not** registered in the package
        definition's ``metadata`` array and are not covered by
        ``package_hash`` — they are post-creation artefacts per the
        "Evidence" tier of PKG.CONF.001.

    Returns
    -------
    PostValidationResult

    Raises
    ------
    UsageError
        ``package_def`` does not exist, or the installed
        ``omniverse-asset-validator`` is too old to validate packages
        (the AssetFormat API requires >= 1.18.0).
    ValidationFailed
        At least one feature of at least one profile failed.
        ``ValidationFailed.failures`` lists the failing feature IDs
        and ``ValidationFailed.result`` carries the full
        :class:`PostValidationResult`.
    RuntimeError
        ``simready.validate`` returned no result, or evaluated no
        features — both indicate a misconfigured engine rather than a
        legitimate validation outcome.
    """
    package_def = Path(package_def)
    if not package_def.is_file():
        raise UsageError(f"package definition not found: {package_def}")

    _check_asset_validator_version()

    profile_list = profiles or [PROFILE_ID]
    all_failed: list[str] = []
    all_results: dict[str, list[tuple[str, sv.AssetValidationResult | None]]] = {}
    evidence_paths: list[Path] = []

    for profile_id in profile_list:
        failed, results_with_rel = _validate_one_profile(package_def, profile_id)
        all_failed.extend(failed)
        all_results[profile_id] = results_with_rel

        if write_evidence:
            pkg_dir = package_def.parent
            asset_results = build_asset_results(results_with_rel)
            path = write_conformance_metadata(
                pkg_dir,
                profile_id,
                PROFILE_VERSION,
                asset_results,
            )
            evidence_paths.append(path)

    result = PostValidationResult(
        package_def=package_def,
        profile_version=PROFILE_VERSION,
        results=all_results,
        evidence_paths=evidence_paths,
        failed_features=sorted(all_failed),
    )

    if all_failed:
        profiles_str = ", ".join(profile_list)
        summary = (
            f"{package_def} did not pass every feature of "
            f"[{profiles_str}] v{PROFILE_VERSION}."
        )
        raise ValidationFailed(summary, failures=sorted(all_failed), result=result)

    return result
