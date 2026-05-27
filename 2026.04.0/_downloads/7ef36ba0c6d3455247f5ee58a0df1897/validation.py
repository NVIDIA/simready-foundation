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
import omni.asset_validator
import omni.capabilities as cap
from pxr import Usd, UsdGeom, UsdPhysics


def get_external_prepended_items(prim: Usd.Prim) -> list:
    external_prepended_items = []
    if prim.HasAuthoredReferences():
        if prim.GetMetadata("references") is not None and prim.GetMetadata("references").prependedItems is not None:
            external_prepended_items.extend(prim.GetMetadata("references").prependedItems)
    if prim.HasAuthoredPayloads():
        if prim.GetMetadata("payloads") is not None and prim.GetMetadata("payloads").prependedItems is not None:
            external_prepended_items.extend(prim.GetMetadata("payloads").prependedItems)
    return external_prepended_items


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(
    cap.UnitsRequirements.UN_001, cap.UnitsRequirements.UN_002, override=True
)
class StageMetadataChecker(omni.asset_validator.BaseRuleChecker):
    """
    All stages should declare their 'upAxis' and 'metersPerUnit'. Stages that can be consumed as referencable assets
    should furthermore have a valid 'defaultPrim' declared, and stages meant for consumer-level packaging should
    always have upAxis set to 'Y'
    """

    def __init__(self, verbose, consumerLevelChecks, assetLevelChecks):
        super().__init__(verbose, consumerLevelChecks, assetLevelChecks)

    def CheckStage(self, usdStage):
        from pxr import UsdGeom

        if not usdStage.HasAuthoredMetadata(UsdGeom.Tokens.upAxis):
            self._AddFailedCheck(
                message="Stage does not specify an upAxis.",
                requirement=cap.UnitsRequirements.UN_001,
            )
        elif self._consumerLevelChecks:
            up_axis = UsdGeom.GetStageUpAxis(usdStage)
            if up_axis != UsdGeom.Tokens.y:
                self._AddFailedCheck(
                    f"Stage specifies upAxis '{up_axis}'. upAxis should be '{UsdGeom.Tokens.y}'.",
                    requirement=cap.UnitsRequirements.UN_001,
                )

        if not usdStage.HasAuthoredMetadata(UsdGeom.Tokens.metersPerUnit):
            self._AddFailedCheck(
                message="Stage does not specify its linear scale " "in metersPerUnit.",
                requirement=cap.UnitsRequirements.UN_002,
            )

        if self._assetLevelChecks:
            default_prim = usdStage.GetDefaultPrim()
            if not default_prim:
                self._AddFailedCheck("Stage has missing or invalid defaultPrim.")


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(cap.UnitsRequirements.UN_003, override=True)
class KilogramsPerUnitChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that stage has kilogramsPerUnit specified if physics objects are present"""

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Check if there are any physics objects in the stage
        has_physics = False
        for prim in stage.Traverse():
            if (
                prim.HasAPI(UsdPhysics.RigidBodyAPI)
                or prim.HasAPI(UsdPhysics.CollisionAPI)
                or prim.HasAPI(UsdPhysics.MassAPI)
            ):
                has_physics = True
                break

        if not has_physics:
            # No physics objects, so kilogramsPerUnit is not required
            return

        # Get the stage kilogramsPerUnit
        kilograms_per_unit = UsdPhysics.GetStageKilogramsPerUnit(stage)

        if kilograms_per_unit is None:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_003,
                message="Stage has physics objects but no kilogramsPerUnit specified.",
                at=stage,
            )


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(cap.UnitsRequirements.UN_004, override=True)
class UnitsCorrectiveTransformChecker(omni.asset_validator.BaseRuleChecker):

    def CheckStage(self, stage: Usd.Stage) -> None:
        # get the world mpu
        world_mpu = UsdGeom.GetStageMetersPerUnit(stage)
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        # check all reference and payloads -> if different mpu, check if scale transform is applied
        for prim in Usd.PrimRange(default_prim):
            external_prepended_items = get_external_prepended_items(prim)

            prim_layer = prim.GetPrimStack()[0].layer
            for item in external_prepended_items:
                # compute asset path -> open stage -> get mpu
                asset_path = item.assetPath
                resolved_asset_path = prim_layer.ComputeAbsolutePath(asset_path)
                asset_mpu = None
                if not asset_path:
                    continue
                try:
                    asset_stage = Usd.Stage.Open(resolved_asset_path)
                    asset_mpu = UsdGeom.GetStageMetersPerUnit(asset_stage)
                except Exception as e:
                    pass

                if asset_mpu is not None and asset_mpu != world_mpu:
                    # calculate the transform scale
                    transform_scale = asset_mpu / world_mpu
                    # check if the transform is applied
                    prim_scale_attr = prim.GetAttribute("xformOp:scale")
                    if not prim_scale_attr.IsValid():
                        self._AddFailedCheck(
                            requirement=cap.UnitsRequirements.UN_004,
                            message=f"Reference Prim '{prim.GetPath()}' has different mpu but no scale transform for correction.",
                            at=prim,
                        )
                    else:
                        scale_value = prim_scale_attr.Get()
                        if not all(x == transform_scale for x in scale_value):
                            self._AddFailedCheck(
                                requirement=cap.UnitsRequirements.UN_004,
                                message=f"Reference Prim '{prim.GetPath()}' has different mpu but scale transform is not uniform.",
                                at=prim,
                            )

                        scale_x = prim.GetAttribute("xformOp:scaleX")
                        scale_y = prim.GetAttribute("xformOp:scaleY")
                        scale_z = prim.GetAttribute("xformOp:scaleZ")

                        # right now, checking if scaling == transform_scale
                        # Do we want to allow scaling of the same order of magnitude, as a future feature?
                        if any(scale.IsValid() for scale in [scale_x, scale_y, scale_z]):
                            if not all(scale.IsValid() for scale in [scale_x, scale_y, scale_z]) or not all(
                                scale.Get() == transform_scale for scale in [scale_x, scale_y, scale_z]
                            ):
                                self._AddFailedCheck(
                                    requirement=cap.UnitsRequirements.UN_004,
                                    message=f"Reference Prim '{prim.GetPath()}' has different mpu but scale transform is not uniform.",
                                    at=prim,
                                )


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(cap.UnitsRequirements.UN_005, override=True)
class TimeCodesPerSecondChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that stage has timeCodesPerSecond specified if timesamples are present"""

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Check if there are any time-varying attributes in the stage
        has_timesamples = False
        for prim in stage.Traverse():
            for attr in prim.GetAttributes():
                if attr.GetNumTimeSamples() > 0:
                    has_timesamples = True
                    break
            if has_timesamples:
                break

        if not has_timesamples:
            # No time-varying data, so timeCodesPerSecond is not required
            return

        # Get the stage timeCodesPerSecond
        time_codes_per_second = stage.GetTimeCodesPerSecond()

        if time_codes_per_second is None or time_codes_per_second == 0:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_005,
                message="Stage has time-varying data but no timeCodesPerSecond specified.",
                at=stage,
            )


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(cap.UnitsRequirements.UN_006, override=True)
class UpAxisZChecker(omni.asset_validator.BaseRuleChecker):
    """
    Validates that stage upAxis is 'Z'.

    This validator checks that the stage has an upAxis specified and that it is set to 'Z'.
    This is a requirement for certain simulation environments that expect Z-up coordinate systems.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Get the stage upAxis
        up_axis = UsdGeom.GetStageUpAxis(stage)

        if not up_axis:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_006, message="Stage has no upAxis specified.", at=stage
            )
        elif up_axis != UsdGeom.Tokens.z:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_006, message=f"Stage has upAxis of '{up_axis}', not 'Z'.", at=stage
            )


@omni.asset_validator.register_rule("Units")
@omni.asset_validator.register_requirements(cap.UnitsRequirements.UN_007, override=True)
class MetersPerUnit1Checker(omni.asset_validator.BaseRuleChecker):
    """
    Validates that stage metersPerUnit is exactly 1.0.

    This validator checks that:
    - The stage has metersPerUnit specified
    - The metersPerUnit value is exactly 1.0

    This ensures the stage uses real-world scale (1 unit = 1 meter).
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        # Get the stage metersPerUnit
        meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)

        if meters_per_unit is None:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_007, message="Stage has no metersPerUnit specified.", at=stage
            )
        elif meters_per_unit != 1.0:
            self._AddFailedCheck(
                requirement=cap.UnitsRequirements.UN_007,
                message=f"Stage has metersPerUnit of {meters_per_unit}, not 1.0.",
                at=stage,
            )
