# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
"""
Validation rules for Conformance Metadata capability (PKG.CONF).

These validators operate on the package directory (not a USD stage).
They verify conformance metadata file naming
(``{profile}@{profile_version}``), profile/version consistency between
filename and contents, and JSON schema conformance.
"""

import json
import re
from urllib.parse import unquote

import omni.asset_validator
import omni.capabilities as cap

from ..packaging_core.validation import (
    AGGREGATE_KEYS,
    BOM_OK,
    METADATA_DIR,
    _compare_digests_against_buffer,
    _content_hash_buffer_from_bom,
    _is_valid_hash_object,
    _load_bom,
    _parse_package_json,
    _read_asset_bytes,
    _uri_basename,
)

_CONF_PREFIX = "com.nvidia.simready.conformance"

_QUALIFIED_RE = re.compile(
    rf"^{re.escape(_CONF_PREFIX)}\.(?P<qualifier>.+@.+)\.json$"
)

FORMAT_VERSION_RE = re.compile(r"\d+\.\d+$")


def _parse_qualifier(qualifier):
    """Split a ``{profile}@{version}`` qualifier and percent-decode."""
    idx = qualifier.rfind("@")
    if idx <= 0:
        return None, None
    return unquote(qualifier[:idx]), unquote(qualifier[idx + 1:])


@omni.asset_validator.register_rule("ConformanceMetadata")
@omni.asset_validator.register_requirements(cap.ConformanceMetadataRequirements.PKG_CONF_001)
class ConformanceMetadataChecker(omni.asset_validator.BaseRuleChecker):
    """Checker for conformance metadata (PKG.CONF.001).

    Validates naming (``{profile}@{version}``), profile/version
    consistency between filename and file contents, and JSON schema.
    """

    REQUIREMENT = cap.ConformanceMetadataRequirements.PKG_CONF_001

    def CheckFormatDependency(self, dependency):
        # Fires once per package on the root manifest. Without this gate
        # the rule would fire on every content dependency and double-report.
        if dependency.path != dependency.root_asset_path:
            return

        data = _parse_package_json(dependency.path)
        if data is None:
            return

        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        meta_dir = uri_resolver.join_uri(pkg_dir, METADATA_DIR)
        if not uri_resolver.is_uri_prefix(meta_dir):
            return

        conf_entries: list[tuple[str, str]] = []
        for child_uri in uri_resolver.list_uris(meta_dir):
            if uri_resolver.is_uri_prefix(child_uri):
                continue
            name = _uri_basename(child_uri)
            if name.startswith(_CONF_PREFIX) and name.endswith(".json"):
                conf_entries.append((name, child_uri))
        conf_entries.sort(key=lambda e: e[0])

        for filename, file_uri in conf_entries:
            match = _QUALIFIED_RE.fullmatch(filename)
            if match is None:
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}' does not match the expected naming pattern "
                            f"'{_CONF_PREFIX}.{{profile}}@{{version}}.json'",
                    requirement=self.REQUIREMENT,
                )
                self._validate_conformance_content(
                    file_uri, filename, None, None, dependency,
                )
                continue

            profile, version = _parse_qualifier(match.group("qualifier"))
            if profile is None or version is None:
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': unable to parse profile and version from qualifier",
                    requirement=self.REQUIREMENT,
                )
                self._validate_conformance_content(
                    file_uri, filename, None, None, dependency,
                )
                continue

            self._validate_conformance_content(
                file_uri, filename, profile, version, dependency,
            )

    # ------------------------------------------------------------------
    # Content validation
    # ------------------------------------------------------------------

    def _validate_conformance_content(
        self, file_uri, filename, expected_profile, expected_version, dependency,
    ):
        """Validate JSON schema and profile/version consistency."""
        raw = _read_asset_bytes(file_uri)
        if raw is None:
            self._AddFailedCheck(
                message=f"Conformance file '{filename}' could not be opened",
                requirement=self.REQUIREMENT,
            )
            return

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            self._AddFailedCheck(
                message=f"Conformance file '{filename}' could not be read as UTF-8",
                requirement=self.REQUIREMENT,
            )
            return

        try:
            content = json.loads(text)
        except json.JSONDecodeError as exc:
            self._AddFailedCheck(
                message=f"Conformance file '{filename}' is not valid JSON: {exc}",
                requirement=self.REQUIREMENT,
            )
            return

        if not isinstance(content, dict):
            self._AddFailedCheck(
                message=f"Conformance file '{filename}' must be a JSON object",
                requirement=self.REQUIREMENT,
            )
            return

        required = {"format_version": str, "profile": str, "profile_version": str, "timestamp": str, "assets": list}
        for field, expected_type in required.items():
            val = content.get(field)
            if val is None:
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}' is missing required field '{field}'",
                    requirement=self.REQUIREMENT,
                )
            elif not isinstance(val, expected_type):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': '{field}' must be {expected_type.__name__}, got {type(val).__name__}",
                    requirement=self.REQUIREMENT,
                )

        fv = content.get("format_version")
        if isinstance(fv, str) and not FORMAT_VERSION_RE.fullmatch(fv):
            self._AddFailedCheck(
                message=f"Conformance file '{filename}': 'format_version' must be in 'major.minor' format, got '{fv}'",
                requirement=self.REQUIREMENT,
            )

        assets = content.get("assets")
        if isinstance(assets, list):
            self._validate_assets_array(assets, filename)

        if expected_profile is not None:
            actual_profile = content.get("profile")
            if isinstance(actual_profile, str) and actual_profile != expected_profile:
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': 'profile' is '{actual_profile}' but filename encodes '{expected_profile}'",
                    requirement=self.REQUIREMENT,
                )

        if expected_version is not None:
            actual_version = content.get("profile_version")
            if isinstance(actual_version, str) and actual_version != expected_version:
                self._AddFailedCheck(
                    message=(
                        f"Conformance file '{filename}': 'profile_version' is "
                        f"'{actual_version}' but filename encodes '{expected_version}'"
                    ),
                    requirement=self.REQUIREMENT,
                )

        self._verify_content_hash(content, filename, dependency)

    # ------------------------------------------------------------------
    # Optional content_hash verification (PKG.HASH.001 multi-algo)
    # ------------------------------------------------------------------

    def _verify_content_hash(self, content, filename, dependency):
        """Re-derive the conformance file's optional ``content_hash``
        from the package's BOM and compare every advertised digest.

        Per the conformance-metadata requirement, ``content_hash`` is
        optional ("MAY"); when present, it MUST match the
        BOM-derived content hash defined by PKG.HASH.001. We verify
        SHA-256 + BLAKE2b unconditionally, and BLAKE3 when the optional
        ``blake3`` Python module is importable.

        Skipped silently when:

        * the field is absent or malformed (``_is_valid_hash_object``
          gates the work — same fail-open posture as
          ``HashObjectFormatChecker._verify_content_hash``);
        * no BOM is present — the requirement explicitly allows
          omitting ``content_hash`` here for BOM-less packages, so we
          have no canonical buffer to compare against.
        """
        content_hash = content.get("content_hash")
        if not isinstance(content_hash, dict) or not _is_valid_hash_object(content_hash):
            return

        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        try:
            status, bom, _ = _load_bom(pkg_dir, uri_resolver)
        except (OSError, RuntimeError, ValueError):
            return
        if status != BOM_OK:
            return

        buf = _content_hash_buffer_from_bom(bom)
        if buf is None:
            return

        def report(msg):
            self._AddFailedCheck(
                message=f"Conformance file '{filename}': {msg}",
                requirement=self.REQUIREMENT,
            )

        _compare_digests_against_buffer(
            content_hash, buf, "content_hash", AGGREGATE_KEYS, report,
        )

    def _validate_assets_array(self, assets, filename):
        """Validate the assets array and delegate feature validation per entry."""
        for i, entry in enumerate(assets):
            if not isinstance(entry, dict):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': assets[{i}] must be an object",
                    requirement=self.REQUIREMENT,
                )
                continue
            asset_path = entry.get("asset")
            if not isinstance(asset_path, str):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': assets[{i}].asset must be a string",
                    requirement=self.REQUIREMENT,
                )
            features = entry.get("features")
            if not isinstance(features, list):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': assets[{i}].features must be an array",
                    requirement=self.REQUIREMENT,
                )
            else:
                context = f"{filename}' assets[{i}]"
                self._validate_features_array(features, context)

    def _validate_features_array(self, features, filename):
        for i, item in enumerate(features):
            if not isinstance(item, dict):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': features[{i}] must be an object",
                    requirement=self.REQUIREMENT,
                )
                continue
            if len(item) != 1:
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': features[{i}] must have exactly one key (feature ID), found {len(item)}",
                    requirement=self.REQUIREMENT,
                )
                continue
            feature_id = next(iter(item))
            feature_obj = item[feature_id]
            if not isinstance(feature_obj, dict):
                self._AddFailedCheck(
                    message=f"Conformance file '{filename}': features[{i}].{feature_id} must be an object",
                    requirement=self.REQUIREMENT,
                )
                continue
            prefix = f"Conformance file '{filename}': features[{i}].{feature_id}"
            version = feature_obj.get("version")
            if not isinstance(version, str):
                self._AddFailedCheck(
                    message=f"{prefix}.version must be a string",
                    requirement=self.REQUIREMENT,
                )
            passed = feature_obj.get("passed")
            if not isinstance(passed, bool):
                self._AddFailedCheck(
                    message=f"{prefix}.passed must be a boolean",
                    requirement=self.REQUIREMENT,
                )
            failing_reqs = feature_obj.get("failing_requirements")
            if not isinstance(failing_reqs, list):
                self._AddFailedCheck(
                    message=f"{prefix}.failing_requirements must be an array",
                    requirement=self.REQUIREMENT,
                )
            elif not all(isinstance(r, str) for r in failing_reqs):
                self._AddFailedCheck(
                    message=f"{prefix}.failing_requirements must contain only strings",
                    requirement=self.REQUIREMENT,
                )
            deps = feature_obj.get("dependencies")
            if not isinstance(deps, list):
                self._AddFailedCheck(
                    message=f"{prefix}.dependencies must be an array",
                    requirement=self.REQUIREMENT,
                )
