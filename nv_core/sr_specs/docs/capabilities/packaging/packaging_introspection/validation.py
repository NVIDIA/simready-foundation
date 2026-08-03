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
"""
Validation rules for Packaging Introspection capability (PKG.BOM).

The BOM is a metadata file identified by the name
``com.nvidia.simready.packaging.bom.json``. These validators verify BOM
structure, content-file completeness, path format, and uniqueness.
"""

import omni.capabilities as cap
import usd_validation_nvidia

from ..packaging_core.validation import (
    BOM_ABSENT,
    BOM_BROKEN,
    BOM_FILENAME,
    METADATA_DIR,
    _load_bom,
    _parse_package_json,
)


@usd_validation_nvidia.register_rule("BomStructure")
@usd_validation_nvidia.register_requirements(cap.PackagingIntrospectionRequirements.PKG_BOM_001)
class BomStructureChecker(usd_validation_nvidia.BaseRuleChecker):
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
                message=(f"BOM file '{BOM_FILENAME}' is present but unusable: {detail}"),
                requirement=self.REQUIREMENT,
            )
