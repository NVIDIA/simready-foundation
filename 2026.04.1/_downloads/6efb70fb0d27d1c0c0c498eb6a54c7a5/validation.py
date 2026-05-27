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
Validation rules for Packaging Introspection capability (PKG.BOM).

The BOM is a metadata file identified by the name
``com.nvidia.simready.packaging.bom.json``. These validators verify BOM
structure, content-file completeness, path format, and uniqueness.
"""

import omni.asset_validator
import omni.capabilities as cap

from ..packaging_core.validation import (
    BOM_ABSENT,
    BOM_BROKEN,
    BOM_FILENAME,
    METADATA_DIR,
    _load_bom,
    _parse_package_json,
)


@omni.asset_validator.register_rule("BomStructure")
@omni.asset_validator.register_requirements(cap.PackagingIntrospectionRequirements.PKG_BOM_001)
class BomStructureChecker(omni.asset_validator.BaseRuleChecker):
    """Checker for BOM presence and structural integrity (PKG.BOM.001).

    Verifies that a BOM file exists at
    ``.metadata/com.nvidia.simready.packaging.bom.json`` and that it is
    structurally loadable (valid UTF-8 JSON object with an ``items``
    array). Content-hash verification against the BOM is handled by the
    core ``HashObjectFormatChecker``; per-item structural checks beyond
    shape are deferred to future PKG.BOM.* rules.
    """

    REQUIREMENT = cap.PackagingIntrospectionRequirements.PKG_BOM_001

    def CheckFormatDependency(self, dependency):
        if dependency.path != dependency.root_asset_path:
            return

        data = _parse_package_json(dependency.path)
        if data is None:
            return

        uri_resolver = dependency.uri_resolver
        pkg_dir = uri_resolver.parent_uri(dependency.path)
        status, _, detail = _load_bom(pkg_dir, uri_resolver)
        if status == BOM_ABSENT:
            self._AddFailedCheck(
                message=f"BOM file '{BOM_FILENAME}' not found in '{METADATA_DIR}/'",
                requirement=self.REQUIREMENT,
            )
        elif status == BOM_BROKEN:
            self._AddFailedCheck(
                message=(
                    f"BOM file '{BOM_FILENAME}' is present but unusable: {detail}"
                ),
                requirement=self.REQUIREMENT,
            )
