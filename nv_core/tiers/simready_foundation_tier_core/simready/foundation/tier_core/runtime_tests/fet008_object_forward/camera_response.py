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

import math

from pxr import Gf, Sdf, Usd, UsdGeom
from simready.foundation.tier_core.asset_frame import (
    FORWARD_DIRECTION,
    facing_camera_transform,
    read_forward_direction,
)
from simready.evaluate import test
from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
    record_required_cleanup_failure,
)
from simready.foundation.tier_core.runtime_tests.fet006_materials._scene import asset_root


def pose_error(camera, target, expected_forward, distance):
    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(camera.GetPrim())
    expected_position = target + expected_forward * distance
    position_error = (matrix.ExtractTranslation() - expected_position).GetLength()
    view = matrix.TransformDir(Gf.Vec3d(0, 0, -1)).GetNormalized()
    view_error = (view + expected_forward).GetLength()
    return position_error, view_error


@test(
    features=[{"id": "FET008_ObjectForward.0-1-0", "version": "*"}],
    name="object_forward_camera_response",
    version="1.0.1",
    description="Change facing on two temporary references and measure composed camera response.",
    expected_video="Two cameras face otherwise identical asset references from different front sides.",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={"asset_load_timeout": 30, "camera_distance": 3.0, "pose_tolerance": 1e-5},
    max_duration=180,
)
async def test_object_forward_camera_response(ctx):
    validate_visual_config(ctx.config, positive=("camera_distance", "pose_tolerance"))
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    stage = ctx.scene.stage
    root_path = asset_root(ctx)
    root = stage.GetPrimAtPath(root_path) if root_path else None
    if not root:
        raise RuntimeError("The required runtime asset root is unavailable")
    try:
        read_forward_direction(root)
    except ValueError as error:
        ctx.fail(str(error))
        return
    distance = float(ctx.config["camera_distance"])
    tolerance = float(ctx.config["pose_tolerance"])
    if not math.isfinite(distance) or distance <= 0 or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Camera distance and pose tolerance must be finite and positive")
    scope = stage.GetPseudoRoot().GetPath().AppendChild("SimReadyForwardProbe")
    while stage.GetPrimAtPath(scope):
        scope = Sdf.Path(str(scope) + "_")
    primary = None
    try:
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            UsdGeom.Xform.Define(stage, scope)
            # Identity transforms make the expected world directions independent
            # of the consumer's local-to-world implementation.
            for name, direction in (
                ("X", Gf.Vec3f(1, 0, 0)),
                (
                    "Other",
                    Gf.Vec3f(0, 0, 1) if UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y else Gf.Vec3f(0, 1, 0),
                ),
            ):
                prim = UsdGeom.Xform.Define(stage, scope.AppendChild(name)).GetPrim()
                prim.GetReferences().AddReference(str(ctx.asset_path))
                prim.SetInstanceable(False)
                UsdGeom.Xformable(prim).ClearXformOpOrder()
                attr = prim.GetAttribute(FORWARD_DIRECTION)
                attr.Set(direction)
                camera = UsdGeom.Camera.Define(stage, scope.AppendChild("Camera" + name))
                camera.AddTransformOp().Set(facing_camera_transform(prim, distance))
                await ctx.settle(count=2)
                position_error, view_error = pose_error(camera, Gf.Vec3d(0), Gf.Vec3d(direction), distance)
                ctx.add_metric("object_forward_" + name + "_position_error", position_error)
                ctx.add_metric("object_forward_" + name + "_view_error", view_error)
                if not math.isfinite(position_error) or not math.isfinite(view_error):
                    raise RuntimeError("Required composed camera pose measurement is nonfinite")
                if position_error > tolerance or view_error > tolerance:
                    ctx.fail("Authored facing did not produce the expected composed camera pose")
                    return
                await ctx.capture_frame(
                    camera=str(camera.GetPath()), label="object_forward_camera_" + name, role="summary"
                )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            with Usd.EditContext(stage, stage.GetSessionLayer()):
                if stage.RemovePrim(scope) is not True or stage.GetPrimAtPath(scope):
                    raise RuntimeError("Required object-forward probe cleanup was not acknowledged")
        except BaseException as cleanup_error:
            record_required_cleanup_failure(ctx, "Required object-forward probe cleanup failed.", primary)
            if primary is None:
                raise
            note_secondary_error(
                primary,
                lambda cleanup_error=cleanup_error: f"Required object-forward cleanup also failed ({type(cleanup_error).__name__}).",
            )
