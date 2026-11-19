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

__all__ = [
    "RenderProductChecker",
    "RenderVarChecker",
    "SemanticAovCompressionChecker",
    "CompressionTypeChecker",
    "GenericModelOutputCompressionChecker",
]

import logging

import simready.foundation.sensors.requirements as cap
from pxr import Sdf, Usd, UsdGeom, UsdRender
from usd_validation_nvidia import (
    BaseRuleChecker,
    Suggestion,
    register_requirements,
    register_rule,
)

logger = logging.getLogger(__name__)


@register_rule("RenderProducts")
@register_requirements(
    cap.RenderProductsRequirements.RP_001,
    cap.RenderProductsRequirements.RP_002,
)
class RenderProductChecker(BaseRuleChecker):
    """
    Validate that a RenderProduct prim has an orderedVars and a camera
    relationship targeting valid prims.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdRender.Product):
            return
        if prim.GetPath().pathString.startswith("/Render/OmniverseKit"):
            return

        stage = prim.GetStage()
        render_product = UsdRender.Product(prim)
        prim_path = prim.GetPath()

        camera_rel = render_product.GetCameraRel()
        camera_paths = camera_rel.GetTargets()
        if not camera_paths:
            self._AddFailedCheck(
                message="`camera` relationship must target a prim.",
                at=prim,
                requirement=cap.RenderProductsRequirements.RP_001,
            )
        else:
            for camera_path in camera_paths:
                target_prim = stage.GetPrimAtPath(camera_path)
                if not target_prim:
                    self._AddFailedCheck(
                        message=f"`camera` relationship targets an invalid prim - {camera_path}",
                        at=prim,
                        requirement=cap.RenderProductsRequirements.RP_001,
                    )
                elif not (
                    target_prim.IsA(UsdGeom.Camera) or target_prim.GetPrimTypeInfo().GetTypeName() == "OmniLidar"
                ):
                    self._AddFailedCheck(
                        message=(
                            f"`camera` relationship targets '{camera_path}', which is a "
                            f"{target_prim.GetPrimTypeInfo().GetTypeName()}, not a Camera or OmniLidar prim."
                        ),
                        at=prim,
                        requirement=cap.RenderProductsRequirements.RP_001,
                    )

        orderedVars_rel = render_product.GetOrderedVarsRel()
        var_paths = orderedVars_rel.GetTargets()
        if not var_paths:
            self._AddFailedCheck(
                message="`orderedVars` relationship must include at least one UsdRender.Var prim.",
                at=prim,
                requirement=cap.RenderProductsRequirements.RP_002,
            )
        for var_path in var_paths:
            var_prim = stage.GetPrimAtPath(var_path)
            if not var_prim or not var_prim.IsA(UsdRender.Var):
                self._AddFailedCheck(
                    message=f"`orderedVars` relationship targets an invalid UsdRender.Var prim - {var_path}",
                    at=prim,
                    requirement=cap.RenderProductsRequirements.RP_002,
                )
                continue
            if var_path.GetParentPath() != prim_path:
                self._AddWarning(
                    message=f"RenderVar '{var_path}' should be a child of '{prim_path}'.",
                    at=var_prim,
                )


@register_rule("RenderProducts")
@register_requirements(cap.RenderProductsRequirements.RP_003)
class RenderVarChecker(BaseRuleChecker):
    """
    Validate that a RenderVar prim has a non-empty sourceName attribute.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdRender.Var):
            return

        source_name_attr = UsdRender.Var(prim).GetSourceNameAttr()
        source_name = source_name_attr.Get() if source_name_attr else None
        if not source_name:
            self._AddFailedCheck(
                message="sourceName is empty.",
                at=prim,
                requirement=cap.RenderProductsRequirements.RP_003,
            )


@register_rule("RenderProducts")
@register_requirements(cap.RenderProductsRequirements.RP_004)
class SemanticAovCompressionChecker(BaseRuleChecker):
    """
    Validate that semantic AOV render vars use BLOSC compression.
    """

    @staticmethod
    def _fix_compression(stage: Usd.Stage, prim: Usd.Prim) -> None:
        """Set srtx:compression:type = 'blosc' on a semantic AOV RenderVar."""
        compression_attr = prim.GetAttribute("srtx:compression:type")
        if not compression_attr or not compression_attr.IsValid():
            compression_attr = prim.CreateAttribute("srtx:compression:type", Sdf.ValueTypeNames.String)
        compression_attr.Set("blosc")

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdRender.Var):
            return

        source_name_attr = prim.GetAttribute("sourceName")
        source_name = source_name_attr.Get() if source_name_attr and source_name_attr.IsValid() else None
        if not source_name or not source_name.lower().startswith("semantic"):
            return

        compression_attr = prim.GetAttribute("srtx:compression:type")
        compression = compression_attr.Get() if compression_attr and compression_attr.IsValid() else None
        if compression != "blosc":
            self._AddFailedCheck(
                message=f"Semantic AOV '{source_name}' must use BLOSC compression.",
                at=prim,
                requirement=cap.RenderProductsRequirements.RP_004,
                suggestion=Suggestion(
                    message="Set srtx:compression:type to 'blosc'.",
                    callable=self._fix_compression,
                ),
            )


_VALID_COMPRESSION_TYPES = frozenset({"hevc", "h264", "av1", "blosc"})


@register_rule("RenderProducts")
@register_requirements(cap.RenderProductsRequirements.RP_005)
class CompressionTypeChecker(BaseRuleChecker):
    """
    Validate that srtx:compression:type, when present on a RenderVar prim,
    is one of the four supported codec values: hevc, h264, av1, blosc.

    An unrecognised value is silently ignored by the RTX runtime, producing
    no compressed output without any error message.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdRender.Var):
            return

        compression_attr = prim.GetAttribute("srtx:compression:type")
        if not compression_attr or not compression_attr.IsValid():
            return
        value = compression_attr.Get()
        if value is None:
            return

        if value not in _VALID_COMPRESSION_TYPES:
            self._AddFailedCheck(
                message=(
                    f"srtx:compression:type '{value}' is not a supported codec. "
                    f"Allowed values: {', '.join(sorted(_VALID_COMPRESSION_TYPES))}."
                ),
                at=prim,
                requirement=cap.RenderProductsRequirements.RP_005,
            )


@register_rule("RenderProducts")
@register_requirements(cap.RenderProductsRequirements.RP_006)
class GenericModelOutputCompressionChecker(BaseRuleChecker):
    """
    Warn when a GenericModelOutput RenderVar does not use BLOSC compression.

    GenericModelOutput carries LiDAR point cloud data (per-point XYZ
    coordinates, intensity, timestamps). Video codecs (hevc, h264, av1) are
    lossy and corrupt numeric precision data. BLOSC is lossless and is the
    codec recommended by the RTX Sensor API for non-visual data.

    This is a warning rather than a failure because some pipelines may have
    legitimate reasons to omit or override compression.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdRender.Var):
            return

        source_name_attr = prim.GetAttribute("sourceName")
        source_name = source_name_attr.Get() if source_name_attr and source_name_attr.IsValid() else None
        if source_name != "GenericModelOutput":
            return

        compression_attr = prim.GetAttribute("srtx:compression:type")
        if not compression_attr or not compression_attr.IsValid():
            return
        value = compression_attr.Get()
        if value is None or value == "blosc":
            return

        self._AddWarning(
            message=(
                f"GenericModelOutput RenderVar uses '{value}' compression. "
                f"BLOSC is recommended for LiDAR point cloud data to preserve numeric precision."
            ),
            at=prim,
            requirement=cap.RenderProductsRequirements.RP_006,
        )
