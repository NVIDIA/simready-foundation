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
"""Scene management for grasp-and-lift tests.

Creates the test scene, loads the asset, builds the gripper, and runs
the per-frame simulation loop with phase checking and frame capture.
Raycasting symmetrization ensures pads contact the surface evenly.
"""

import math
from contextlib import contextmanager
from numbers import Integral, Real
from typing import Any

import carb
import numpy as np
import omni.kit.app
import omni.usd
from isaacsim.core.utils.stage import update_stage_async
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_body import resolve_grasp_body
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_checks import grasp_point_source
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_geometry import (
    post_failure_stop_frame,
)
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_phases import GraspPhaseManager
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_robot import GraspRobot
from simready.foundation.tier_core.runtime_tests.fet005_grasp.grasp_utils import AssetPoseTracker
from simready.foundation.tier_core.runtime_tests.fet005_grasp.newton_articulation import (
    NewtonTensorDriveUnavailable,
)


def _required_grasp_matrix(rows, path):
    """Preserve scale in an invertible finite affine point transform."""
    from simready.evaluate_engine_kit.fabric_utils import validated_world_matrix

    try:
        checked = validated_world_matrix(rows)
        matrix = Gf.Matrix4d(1.0)
        for index, row in enumerate(checked):
            matrix.SetRow(index, Gf.Vec4d(*row))
        determinant = matrix.GetDeterminant()
        if not math.isfinite(determinant) or determinant == 0.0:
            raise ValueError("World transform is singular")
        return matrix
    except Exception as exc:
        raise RuntimeError("Required grasp transform is invalid: " + str(path)) from exc


def _record_required_fixture_failure(ctx, reason, primary):
    """Latch unsafe native/topology health without replacing the first cause."""
    try:
        session = getattr(ctx, "_engine_session", None)
        callback = getattr(session, "record_required_cleanup_failure", None)
        if callable(callback):
            callback(reason)
    except BaseException as secondary:
        try:
            primary.add_note("Fixture health recording also failed (%s)." % type(secondary).__name__)
        except BaseException:
            pass


class GraspScene:
    """Manages a single grasp-and-lift test scene for one identifier."""

    def __init__(self, ctx, identifier_path, asset_mount_path):
        # type: (Any, str, str) -> None
        self._ctx = ctx
        self._identifier_path = identifier_path
        self._asset_mount_path = asset_mount_path
        self._robot = None  # type: Optional[GraspRobot]
        self._scene_properties = {}  # type: dict[str, Any]
        # Tracking state: local grasp points + parent body for per-frame follow
        self._local_gp1 = None  # type: Optional[Any]
        self._local_gp2 = None  # type: Optional[Any]
        self._parent_body_path = None  # type: Optional[str]
        self._gantry_base_world = None  # type: Optional[np.ndarray]
        self._diagnostic_failures = set()

    @contextmanager
    def _optional_diagnostics(self, name):
        """Bound optional reporting failures without hiding required operations."""
        try:
            yield
        except Exception as error:
            if name not in self._diagnostic_failures and len(self._diagnostic_failures) < 8:
                self._diagnostic_failures.add(name)
                try:
                    self._ctx.warn("Optional FET005 %s unavailable (%s)." % (name, type(error).__name__))
                except Exception:
                    pass

    def _report_fixture_load(self, identifier_name):
        with self._optional_diagnostics("fixture load report"):
            ctx = self._ctx
            pad_props = self._scene_properties["gripper_pad_properties"]
            ctx.log(
                "[fixture-load] source=%s authored_mass_count=%d mass=%.6fkg max_force=%.6fN"
                % (
                    pad_props["mass_source"],
                    pad_props["authored_mass_count"],
                    pad_props["mass"],
                    pad_props["max_force"],
                )
            )
            ctx.add_metric("grasp_%s_fixture_mass_kg" % identifier_name, pad_props["mass"])
            ctx.add_metric("grasp_%s_fixture_max_force_n" % identifier_name, pad_props["max_force"])
            ctx.add_metric("grasp_%s_fixture_mass_source" % identifier_name, pad_props["mass_source"])

    # Attributes accessed by phase checks
    @property
    def robot(self):
        # type: () -> Optional[GraspRobot]
        return self._robot

    @property
    def stage(self):
        # type: () -> Usd.Stage
        return omni.usd.get_context().get_stage()

    @property
    def scene_properties(self):
        # type: () -> dict[str, Any]
        return self._scene_properties

    @property
    def grasp_identifier_path(self):
        # type: () -> str
        return self._identifier_path

    def empty_grasp_failure_message(self) -> str:
        """Append scoped collider authoring context, not a native-contact diagnosis."""
        message = "Grasping failed: pads touched (no object)"
        try:
            from pxr import UsdPhysics
            from simready.evaluate_engine_kit.physics_utils import (
                active_physics_engine,
            )

            if active_physics_engine() != "newton":
                return message
            body_path = self._parent_body_path
            if not body_path:
                return message
            body = self.stage.GetPrimAtPath(body_path)
            if not body or not body.IsValid() or not body.HasAPI(UsdPhysics.RigidBodyAPI):
                return message
            if UsdPhysics.RigidBodyAPI(body).GetRigidBodyEnabledAttr().Get() is not True:
                return message
            for prim in Usd.PrimRange(
                body,
                Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate),
            ):
                if prim.GetTypeName() != "Mesh":
                    continue
                schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
                authored_schemas = prim.GetMetadata("apiSchemas")
                if authored_schemas is not None:
                    schemas.update(str(schema) for schema in authored_schemas.GetAppliedItems())
                if "PhysicsCollisionAPI" not in schemas:
                    continue
                if UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is not True:
                    continue
                owner = prim
                while owner and owner.IsValid() and not owner.HasAPI(UsdPhysics.RigidBodyAPI):
                    owner = owner.GetParent()
                if owner != body:
                    continue
                approximation = prim.GetAttribute("physics:approximation")
                approximation_value = approximation.Get() if approximation and approximation.IsValid() else None
                if str(approximation_value or "").lower() != "none":
                    continue
                if "NewtonSDFCollisionAPI" in schemas:
                    continue
                return (
                    message + "; selected grasp body %s has enabled exact mesh collider %s "
                    "(physics:approximation=none, no NewtonSDFCollisionAPI). "
                    "This is authored collider context only; native dynamic contacts were not measured. "
                    "Inspect the selected runtime's cooking and generated-pad setup before "
                    "concluding that the asset needs a collider change." % (body.GetPath(), prim.GetPath())
                )
        except Exception as exc:
            try:
                carb.log_warn("[grasp-scene] Could not inspect Newton collider diagnostics: %s" % exc)
            except Exception:
                pass
        return message

    # ------------------------------------------------------------------
    # Grasp point extraction
    # ------------------------------------------------------------------

    def _extract_world_grasp_points(self) -> list[Gf.Vec3d] | None:
        """Extract the authored grasp segment in world space."""
        from simready.evaluate_engine_kit.fabric_utils import validated_bounds

        stage = self.stage
        id_prim = stage.GetPrimAtPath(self._identifier_path)
        if not id_prim or not id_prim.IsValid():
            return None
        gp1_world = None  # type: Optional[Gf.Vec3d]
        gp2_world = None  # type: Optional[Gf.Vec3d]
        xform_cache = UsdGeom.XformCache()

        source = grasp_point_source(id_prim)
        if source is not None:
            child, pts = source
            child_xf = _required_grasp_matrix(xform_cache.GetLocalToWorldTransform(child), child.GetPath())
            try:
                world_pts = []
                for point in pts[:2]:
                    checked, _ = validated_bounds(point, point)
                    transformed = child_xf.Transform(Gf.Vec3d(*checked))
                    validated_bounds(transformed, transformed)
                    world_pts.append(transformed)
                length = (world_pts[1] - world_pts[0]).GetLength()
                if not math.isfinite(length) or length <= 0.0:
                    raise ValueError("Grasp segment must have finite nonzero length")
            except Exception as exc:
                raise RuntimeError("Authored grasp segment is invalid: " + str(child.GetPath())) from exc
            gp1_world = world_pts[0]
            gp2_world = world_pts[1]

        if gp1_world is None or gp2_world is None:
            return None
        return [gp1_world, gp2_world]

    def compute_local_grasp_points(self, body_path: str | None = None) -> list[Any] | None:
        """Extract grasp points in the resolved grasp body's local space."""
        world_points = self._extract_world_grasp_points()
        if world_points is None:
            return None
        if body_path is None:
            id_prim = self.stage.GetPrimAtPath(self._identifier_path)
            if not id_prim or not id_prim.IsValid():
                return None
            body_path = str(id_prim.GetParent().GetPath())
        body = self.stage.GetPrimAtPath(body_path)
        if not body or not body.IsValid():
            return None
        body_xf = _required_grasp_matrix(UsdGeom.XformCache().GetLocalToWorldTransform(body), body.GetPath())
        inv = body_xf.GetInverse()
        return [inv.Transform(world_points[0]), inv.Transform(world_points[1])]

    def compute_world_grasp_points(self, local_gp1, local_gp2, authored=False):
        # type: (Any, Any, bool) -> list[Gf.Vec3d]
        """Convert local grasp points to world space."""
        body_xf = self._body_world_matrix(self._parent_body_path, authored=authored) if self._parent_body_path else None
        if body_xf is None:
            raise RuntimeError("Cannot resolve the live grasp-body transform")
        return [
            body_xf.Transform(Gf.Vec3d(local_gp1)),
            body_xf.Transform(Gf.Vec3d(local_gp2)),
        ]

    def _body_world_matrix(self, body_path, authored=False):
        # type: (str, bool) -> Gf.Matrix4d
        """Return a required live transform, or explicitly authored setup pose."""
        prim = self.stage.GetPrimAtPath(body_path)
        if not prim or not prim.IsValid():
            raise RuntimeError("Required grasp body is unavailable: " + body_path)
        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        if not authored and active_physics_engine() != "physx":
            from simready.evaluate_engine_kit.fabric_utils import live_world_matrix

            rows = live_world_matrix(self.stage, body_path)
            if rows is not None:
                return _required_grasp_matrix(rows, body_path)
            raise RuntimeError("Required live grasp-body transform is unavailable: " + body_path)
        return _required_grasp_matrix(UsdGeom.XformCache().GetLocalToWorldTransform(prim), body_path)

    # ------------------------------------------------------------------
    # Raycasting symmetrization
    # ------------------------------------------------------------------

    def symmetrize_grasp_points(self, gp1, gp2):
        # type: (np.ndarray, np.ndarray) -> tuple[np.ndarray, np.ndarray, float]
        """Symmetrize grasp points via PhysX raycasting.

        Returns (adj_gp1, adj_gp2, pad_to_surface_distance).
        """
        axis = gp2 - gp1
        dist = float(np.linalg.norm(axis))
        axis_n = axis / max(1e-9, dist)
        midpoint = (gp1 + gp2) / 2.0

        target_body = self._parent_body_path or self._asset_mount_path

        hit1 = get_physx_scene_query_interface().raycast_closest(
            carb.Float3(*gp1),
            carb.Float3(*axis_n),
            dist,
        )
        hit2 = get_physx_scene_query_interface().raycast_closest(
            carb.Float3(*gp2),
            carb.Float3(*(-axis_n)),
            dist,
        )

        if (
            hit1["hit"]
            and hit2["hit"]
            and target_body in hit1.get("rigidBody", "")
            and target_body in hit2.get("rigidBody", "")
        ):
            s1 = np.array([hit1["position"][i] for i in range(3)])
            s2 = np.array([hit2["position"][i] for i in range(3)])
            off1 = float(np.linalg.norm(gp1 - s1))
            off2 = float(np.linalg.norm(gp2 - s2))
            avg_off = (off1 + off2) / 2.0
            d1 = (gp1 - s1) / max(1e-9, off1) if off1 > 1e-9 else -axis_n
            d2 = (gp2 - s2) / max(1e-9, off2) if off2 > 1e-9 else axis_n
            return s1 + d1 * avg_off, s2 + d2 * avg_off, avg_off

        # Fallback: use original symmetric points
        return (
            midpoint - axis_n * (dist / 2.0),
            midpoint + axis_n * (dist / 2.0),
            dist / 2.0,
        )

    # ------------------------------------------------------------------
    # Robot lifecycle
    # ------------------------------------------------------------------

    def init_tracking(self):
        # type: () -> None
        """Initialize tracking state (local grasp points + parent body).

        Call this before physics starts. The gripper will be built later
        (after stability) via rebuild_gripper_at_settled_position().
        """
        world_pts = self._extract_world_grasp_points()
        if world_pts is None or len(world_pts) < 2:
            raise RuntimeError("Failed to extract grasp points from " + self._identifier_path)
        self._parent_body_path = resolve_grasp_body(
            self.stage,
            self._identifier_path,
            self._asset_mount_path,
            world_pts[0],
            world_pts[1],
        )
        local_pts = self.compute_local_grasp_points(self._parent_body_path)
        if local_pts is None or len(local_pts) < 2:
            raise RuntimeError("Failed to extract grasp points from " + self._identifier_path)
        self._local_gp1 = local_pts[0]
        self._local_gp2 = local_pts[1]
        self._ctx.log("[tracker] resolved_grasp_body=%s" % self._parent_body_path)

    async def build_robot(self):
        # type: () -> None
        """Build the gripper from initial (pre-stability) grasp points.

        Stores local grasp points and parent body path for per-frame
        tracking during the simulation.
        """
        if self._local_gp1 is None:
            self.init_tracking()

        world_pts = self.compute_world_grasp_points(self._local_gp1, self._local_gp2, authored=True)
        gp1 = np.array(world_pts[0])
        gp2 = np.array(world_pts[1])

        # Build gripper at the ACTUAL grasp positions (like V1).
        # Pad collision is disabled during stability to prevent the
        # pads from pushing the object. Enabled when grasping starts.
        pad_dist = float(np.linalg.norm(gp2 - gp1)) / 2.0

        await update_stage_async()

        self._robot = await GraspRobot.build_for_asset(
            stage=self.stage,
            grasp_point_1=list(gp1),
            grasp_point_2=list(gp2),
            target_asset_path=self._asset_mount_path,
            pad_to_surface_distance=float(pad_dist),
            grasp_body_path=self._parent_body_path,
        )

        self._scene_properties = {
            **self._robot.scene_properties,
            "target_asset_path": self._asset_mount_path,
            "tracked_body_path": self._parent_body_path or self._asset_mount_path,
        }

        # Cache the gantry base world position (fixed, never moves).
        # Joint targets are offsets from this position.
        base_prim = self.stage.GetPrimAtPath(GraspRobot.GANTRY_BASE)
        base_xf = UsdGeom.Xformable(base_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        base_pos = base_xf.ExtractTranslation()
        self._gantry_base_world = np.array([float(base_pos[0]), float(base_pos[1]), float(base_pos[2])])

        # --- DEBUG: log build positions ---
        mid_actual = 0.5 * (gp1 + gp2)
        self._ctx.log(
            "[build] grasp_world_mid=(%.3f,%.3f,%.3f) "
            "gantry_base=(%.3f,%.3f,%.3f) "
            "gp1=(%.3f,%.3f,%.3f) gp2=(%.3f,%.3f,%.3f)"
            % (
                mid_actual[0],
                mid_actual[1],
                mid_actual[2],
                self._gantry_base_world[0],
                self._gantry_base_world[1],
                self._gantry_base_world[2],
                gp1[0],
                gp1[1],
                gp1[2],
                gp2[0],
                gp2[1],
                gp2[2],
            )
        )

    def _set_pad_collision_enabled(self, enabled):
        # type: (bool) -> None
        """Author and verify collision state on both generated pad cube prims.

        Disabled during stability to prevent pads from pushing the object.
        Re-enabled before grasping so pads can make contact.
        USD readback does not establish that the native runtime applied a change.
        """
        from pxr import UsdPhysics

        if type(enabled) is not bool:
            raise RuntimeError("Generated pad collision state must be a boolean")
        stage = self.stage
        attributes = []
        for cube_path in [
            GraspRobot.LEFT_PAD,
            GraspRobot.RIGHT_PAD,
        ]:
            prim = stage.GetPrimAtPath(cube_path)
            if not prim or not prim.IsValid():
                raise RuntimeError("Required generated gripper pad is missing: " + cube_path)
            col_api = UsdPhysics.CollisionAPI.Get(stage, cube_path)
            if not col_api:
                raise RuntimeError("Required generated gripper pad has no CollisionAPI: " + cube_path)
            attribute = col_api.GetCollisionEnabledAttr()
            if not attribute or not attribute.IsValid():
                raise RuntimeError("Required generated pad collision attribute is unavailable: " + cube_path)
            attributes.append((cube_path, attribute))
        for cube_path, attribute in attributes:
            try:
                written = attribute.Set(enabled)
                observed = attribute.Get()
            except Exception as exc:
                raise RuntimeError("Generated pad collision state could not be authored: " + cube_path) from exc
            if written is not True or type(observed) is not bool or observed is not enabled:
                raise RuntimeError("Generated pad collision state was not authored and verified: " + cube_path)
        self._scene_properties["pad_collision_authoring"] = {
            "enabled": enabled,
            "pad_paths": [path for path, _attribute in attributes],
            "source": "USD authored write/readback",
            "native_application_verified": False,
        }

    def disable_gripper_pad_collisions(self):
        # type: () -> None
        """Request collision-disabled generated pads after the jaws finish opening.

        The pads are temporary test-fixture geometry. Disabling only their
        collision is intended to prevent residual solver contact from retaining
        a released object. Required USD writes/readback are checked, but are not
        native solver acknowledgment; the free-fall assertion remains intact.
        """
        self._set_pad_collision_enabled(False)

    def verify_gripper_collision_disabled(self):
        # type: () -> None
        """Require release flags after the next existing physics tick."""
        self.verify_gripper_collision_state(False)

    def verify_gripper_collision_state(self, enabled):
        # type: (bool) -> None
        """Require the expected compiled Newton pad flags without changing state.

        This is read-only model acknowledgment, not a contact-force measurement.
        PhysX retains the verified USD authoring path. No model flags are written
        and no physics update is added while checking the Newton model.
        """
        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        if type(enabled) is not bool:
            raise RuntimeError("Required compiled gripper collision state must be a boolean")
        pad_paths = [GraspRobot.LEFT_PAD, GraspRobot.RIGHT_PAD]
        receipt = self._scene_properties.get("pad_collision_authoring")
        if (
            not isinstance(receipt, dict)
            or receipt.get("enabled") is not enabled
            or receipt.get("pad_paths") != pad_paths
        ):
            raise RuntimeError("Required generated gripper collision-state authoring is unavailable")
        if active_physics_engine() != "newton":
            return
        receipt["compiled_shape_flags_acknowledged"] = False
        receipt["native_application_verified"] = False
        receipt["contact_not_measured"] = True
        reason = "readback_unavailable"
        observed_pads = {}
        try:
            import newton
            from isaacsim.physics.newton import acquire_stage

            native_stage = acquire_stage()
            reason = "model_unavailable"
            if native_stage is None or native_stage.initialized is not True or native_stage.model is None:
                raise ValueError("The compiled Newton model is unavailable")
            model = native_stage.model
            reason = "shape_metadata_unavailable_or_invalid"
            labels = model.shape_label
            shape_count = model.shape_count
            if (
                not isinstance(shape_count, Integral)
                or isinstance(shape_count, bool)
                or shape_count <= 0
                or not isinstance(labels, (list, tuple))
                or len(labels) != shape_count
                or not all(isinstance(label, str) and label for label in labels)
            ):
                raise ValueError("Compiled Newton shape labels/count are invalid")
            reason = "shape_flags_unavailable_or_invalid"
            flags = np.asarray(model.shape_flags.numpy())
            if flags.ndim != 1 or len(flags) != shape_count or flags.dtype.kind not in ("i", "u") or np.any(flags < 0):
                raise ValueError("Compiled Newton shape flags must be a complete one-dimensional integer array")
            reason = "collision_flag_unavailable_or_invalid"
            collision_flag = newton.ShapeFlags.COLLIDE_SHAPES
            if not isinstance(collision_flag, Integral) or isinstance(collision_flag, bool) or collision_flag <= 0:
                raise ValueError("Newton's shape-collision flag is unavailable or invalid")
            for pad_path in pad_paths:
                reason = "pad_mapping_not_unique"
                if labels.count(pad_path) != 1:
                    raise ValueError("Required generated pad has no unique compiled Newton shape: " + pad_path)
                observed = bool(int(flags[labels.index(pad_path)]) & int(collision_flag))
                observed_pads["left" if pad_path == GraspRobot.LEFT_PAD else "right"] = observed
                reason = "compiled_state_mismatch"
                if observed is not enabled:
                    raise ValueError(
                        "Generated pad collision state differs from the required compiled state: " + pad_path
                    )
        except Exception as exc:
            # This bounded context survives EngineKit's outer-exception result
            # formatting. Never echo arbitrary native exception strings, or
            # invent an observed state for a pad whose readback did not succeed.
            raise RuntimeError(
                "Generated gripper collision state could not be acknowledged by the compiled Newton model "
                "(expected_enabled=%s; reason=%s; observed=%s)" % (enabled, reason, observed_pads)
            ) from exc
        receipt["compiled_shape_flags_acknowledged"] = True

    def get_current_world_grasp_points(self):
        # type: () -> Optional[tuple[np.ndarray, np.ndarray]]
        """Get the current world-space grasp points from the body's
        live physics transform.

        Returns (gp1_world, gp2_world) as numpy arrays, or None if
        the parent body or local points are not available.
        """
        if self._local_gp1 is None or self._local_gp2 is None or self._parent_body_path is None:
            return None
        body_xf = self._body_world_matrix(self._parent_body_path)
        if body_xf is None:
            return None
        gp1 = np.array(body_xf.Transform(Gf.Vec3d(self._local_gp1)))
        gp2 = np.array(body_xf.Transform(Gf.Vec3d(self._local_gp2)))
        return (gp1, gp2)

    def get_grasp_and_gripper_midpoints(self):
        # type: () -> Optional[tuple[tuple[float, float, float], tuple[float, float, float]]]
        """Return live authored-grasp and jaw midpoints in world space."""
        grasp_points = self.get_current_world_grasp_points()
        if grasp_points is None:
            return None
        left = self._body_world_matrix(GraspRobot.LEFT_PAD)
        right = self._body_world_matrix(GraspRobot.RIGHT_PAD)
        if left is None or right is None:
            return None
        grasp_mid = 0.5 * (grasp_points[0] + grasp_points[1])
        left_pos = left.ExtractTranslation()
        right_pos = right.ExtractTranslation()
        gripper_mid = 0.5 * (np.array(left_pos) + np.array(right_pos))
        return (
            tuple(float(value) for value in grasp_mid),
            tuple(float(value) for value in gripper_mid),
        )

    def track_grasp_line(self):
        # type: () -> bool
        """Update gantry joint targets to follow the current grasp line.

        Called every physics frame while tracking is active (before
        Lifting phase). Computes the absolute joint targets directly
        from the desired world position minus the fixed gantry base
        position. No delta accumulation -- avoids oscillation.

        Also updates scene_properties so phase checks (e.g. GraspingPhase
        close target) use the latest geometry.

        Returns True if tracking succeeded, False if grasp points are
        unavailable.
        """
        pts = self.get_current_world_grasp_points()
        if pts is None or self._robot is None or self._gantry_base_world is None:
            return False
        gp1, gp2 = pts
        midpoint = 0.5 * (gp1 + gp2)
        midpoint[2] += float(self._scene_properties.get("pad_ground_offset_z", 0.0))

        # Update scene properties with live grasp geometry
        self._scene_properties["grasp_point_1"] = list(gp1)
        self._scene_properties["grasp_point_2"] = list(gp2)
        grasp_dist = float(np.linalg.norm(gp2 - gp1))
        self._scene_properties["gripper_position_info"]["grasp_distance"] = grasp_dist

        # Set joint targets directly: target = desired_world - base_world.
        # The gantry base is fixed to world (root FixedJoint), so joint
        # offsets map 1:1 to world offsets. No reading current position,
        # no delta accumulation, no oscillation.
        target = midpoint - self._gantry_base_world
        self._robot.update_joint_target_positions(float(target[0]), float(target[1]), float(target[2]))
        return True

    async def rebuild_gripper_at_settled_position(
        self,
        physics,
        floor_level=0.0,
        pad_ground_clearance=0.002,
    ):
        # type: (Any, float, float) -> bool
        """Delete old gripper and rebuild at the settled grasp position.

        Called after stability. Stops physics, removes the old gripper
        prims, builds a new one at the current grasp world positions,
        restarts physics. This ensures the gripper orientation matches
        the settled object pose exactly.

        Returns True if rebuild succeeded.
        """
        pts = self.get_current_world_grasp_points()
        if pts is None:
            return False
        gp1, gp2 = pts

        # Stop physics so we can modify the stage
        try:
            if physics.stop() is False:
                raise RuntimeError("Required physics stop was rejected before rebuilding the generated gripper")
        except BaseException as error:
            _record_required_fixture_failure(self._ctx, "Required FET005 rebuild physics stop failed.", error)
            raise

        # Delete old gripper
        stage = self.stage
        old_robot_prim = stage.GetPrimAtPath(GraspRobot.ROBOT_PATH)
        if old_robot_prim and old_robot_prim.IsValid():
            try:
                if self._robot is None or not hasattr(self._robot, "_edit_target"):
                    raise RuntimeError("Cannot establish ownership of the existing generated gripper")
                self._robot.teardown()
                with Usd.EditContext(stage, self._robot._edit_target):
                    removed = stage.RemovePrim(GraspRobot.ROBOT_PATH)
                if removed is not True or stage.GetPrimAtPath(GraspRobot.ROBOT_PATH):
                    raise RuntimeError("Required owned gripper removal was not completed and verified")
            except BaseException as error:
                _record_required_fixture_failure(self._ctx, "Required FET005 old gripper removal failed.", error)
                raise
            self._robot = None
        await update_stage_async()

        # Build new gripper at settled position
        pad_dist = float(np.linalg.norm(gp2 - gp1)) / 2.0
        self._robot = await GraspRobot.build_for_asset(
            stage=stage,
            grasp_point_1=list(gp1),
            grasp_point_2=list(gp2),
            target_asset_path=self._asset_mount_path,
            pad_to_surface_distance=float(pad_dist),
            grasp_body_path=self._parent_body_path,
            floor_level=floor_level,
            pad_ground_clearance=pad_ground_clearance,
        )
        self._scene_properties = {
            **self._robot.scene_properties,
            "target_asset_path": self._asset_mount_path,
            "tracked_body_path": self._parent_body_path or self._asset_mount_path,
        }

        # Update gantry base cache
        base_prim = stage.GetPrimAtPath(GraspRobot.GANTRY_BASE)
        base_xf = UsdGeom.Xformable(base_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        base_pos = base_xf.ExtractTranslation()
        self._gantry_base_world = np.array([float(base_pos[0]), float(base_pos[1]), float(base_pos[2])])

        self._ctx.log(
            "[rebuild] gp1=(%.3f,%.3f,%.3f) gp2=(%.3f,%.3f,%.3f) "
            "gantry_base=(%.3f,%.3f,%.3f) pad_ground_offset_z=%.4f"
            % (
                gp1[0],
                gp1[1],
                gp1[2],
                gp2[0],
                gp2[1],
                gp2[2],
                self._gantry_base_world[0],
                self._gantry_base_world[1],
                self._gantry_base_world[2],
                float(self._scene_properties.get("pad_ground_offset_z", 0.0)),
            )
        )

        # Restart physics with the new gripper
        self._set_pad_collision_enabled(True)
        if physics.play() is False:
            raise RuntimeError("Required physics start was rejected after rebuilding the generated gripper")
        await self._ctx.settle(count=1)

        from simready.evaluate_engine_kit.physics_utils import active_physics_engine

        if active_physics_engine() == "newton":
            ready = await self._robot.init_newton_tensor_drive(self._ctx)
            self._ctx.log("[rebuild] Newton tensor finger control %s" % ("ready" if ready else "UNAVAILABLE"))
            if not ready:
                raise NewtonTensorDriveUnavailable("Newton tensor finger control could not be initialized")
            self.verify_gripper_collision_state(True)
        return True

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    async def run_simulation(self, cfg, identifier_name, physics=None):
        # type: (dict[str, Any], str, Any) -> dict[str, Any]
        """Run the 9-phase simulation loop. Returns the final result dict."""
        ctx = self._ctx
        fps = int(cfg["physics_fps"])
        capture_fps = int(cfg.get("capture_fps", 20))
        sim_seconds = float(cfg.get("simulation_seconds", 17.0))
        total_frames = int(sim_seconds * fps)
        failure_observation_seconds = float(cfg.get("post_failure_observation_seconds", 1.0))
        failure_observation_frames = post_failure_stop_frame(
            0,
            fps,
            failure_observation_seconds,
        )
        capture_interval = max(1, fps // capture_fps)

        tracker = AssetPoseTracker(fps)
        phases = GraspPhaseManager(cfg)
        floor_level = float(cfg.get("floor_level", 0.0))
        pad_ground_clearance = float(cfg.get("pad_ground_clearance", 0.002))
        log_interval = fps  # log diagnostics once per second
        snapped = False  # True after gripper is snapped to position

        # Runtime verdicts concern the rigid body selected by the authored
        # grasp identifier.  Tracking the whole asset produces false motion
        # for multibody props (for example, a joystick whose lever settles
        # while its grasped base remains still).
        tracked_path = self._parent_body_path or self._asset_mount_path
        asset_prim = self.stage.GetPrimAtPath(tracked_path)
        if not asset_prim or not asset_prim.IsValid():
            raise RuntimeError("Tracked grasp body is missing: " + tracked_path)
        ctx.log("[tracker] rigid_body=%s" % tracked_path)
        label = "grasp_and_lift_%s" % identifier_name
        frames = []  # type: list[str]

        result = None  # type: Optional[dict[str, Any]]
        failure_frame = None  # type: Optional[int]
        failure_stop_frame = None  # type: Optional[int]
        observation_end_frame = None  # type: Optional[int]
        simulation_complete = False

        # Reserve an observation tail for a failure on the final normal-budget
        # frame. Successful or unfinished phase execution cannot consume it.
        max_frames = total_frames + failure_observation_frames + 1
        for frame in range(max_frames):
            if failure_stop_frame is None and frame >= total_frames:
                break
            await ctx.physics_step()

            time = frame / float(fps)
            finger_positions = None
            try:
                tracker.record_frame(asset_prim, time)
                # These observations drive the phase criteria until a measured
                # failure is terminal. A diagnostic tail cannot replace it.
                if self._robot is not None:
                    finger_positions = self._robot.get_finger_joint_positions()
                    tracker.record_finger_positions(finger_positions, current_time=time)
            except Exception as error:
                if failure_stop_frame is None:
                    raise
                observation_end_frame = frame - 1
                result["failure_observation_limited"] = True
                result["failure_observation_limitation"] = (
                    "Post-failure observation unavailable (%s)." % type(error).__name__
                )
                with self._optional_diagnostics("failure observation warning"):
                    ctx.warn(result["failure_observation_limitation"])
                break

            # Per-frame grasp line tracking: move gantry to follow
            # the object until Lifting starts
            if phases.tracking_active:
                try:
                    self.track_grasp_line()
                except Exception as error:
                    if failure_stop_frame is None:
                        raise
                    observation_end_frame = frame - 1
                    result["failure_observation_limited"] = True
                    result["failure_observation_limitation"] = (
                        "Post-failure tracking unavailable (%s)." % type(error).__name__
                    )
                    with self._optional_diagnostics("failure tracking warning"):
                        ctx.warn(result["failure_observation_limitation"])
                    break

                # Diagnostic logging (once per second)
                if frame % log_interval == 0:
                    with self._optional_diagnostics("tracking log"):
                        pts = self.get_current_world_grasp_points()
                        if pts is not None and self._robot is not None:
                            gp1, gp2 = pts
                            mid = 0.5 * (gp1 + gp2)
                            jx, jy, jz = self._robot.get_joint_targets()
                            gx_pos = self._body_world_matrix(GraspRobot.GANTRY_X).ExtractTranslation()
                            ctx.log(
                                "[track] t=%.1fs phase=%s "
                                "grasp_mid=(%.3f,%.3f,%.3f) "
                                "joint_tgt=(%.3f,%.3f,%.3f) "
                                "gantry_x_live=(%.3f,%.3f,%.3f) "
                                "delta_z=%.3f"
                                % (
                                    time,
                                    phases.current_phase_name,
                                    mid[0],
                                    mid[1],
                                    mid[2],
                                    jx,
                                    jy,
                                    jz,
                                    gx_pos[0],
                                    gx_pos[1],
                                    gx_pos[2],
                                    mid[2] - gx_pos[2],
                                )
                            )

            # After stability: rebuild gripper at the settled position.
            # Must happen BEFORE the phase check so GripperPositioning
            # sees the correctly positioned gripper.
            if not snapped and phases.stability_complete and physics is not None:
                snapped = True
                ctx.step("Rebuilding gripper at settled position")
                rebuilt = await self.rebuild_gripper_at_settled_position(
                    physics,
                    floor_level=floor_level,
                    pad_ground_clearance=pad_ground_clearance,
                )
                if rebuilt is not True:
                    raise RuntimeError("Required generated gripper could not be rebuilt at the settled grasp pose")
                self._report_fixture_load(identifier_name)

            # Diagnostic logging every second (all phases, not just tracking)
            if frame % log_interval == 0 and self._robot is not None:
                with self._optional_diagnostics("gripper log"):
                    finger_pos = finger_positions[0]
                    finger_tgt = self._robot.get_gripper_joint_target()
                    lp_pos = self._body_world_matrix(GraspRobot.LEFT_PAD).ExtractTranslation()
                    obj_z = tracker.center_history[-1][2]
                    ctx.log(
                        "[diag] t=%.1fs phase=%s "
                        "finger_pos=%.4f finger_tgt=%.4f "
                        "left_pad_live=(%.3f,%.3f,%.3f) obj_z=%.4f"
                        % (
                            time,
                            phases.current_phase_name,
                            finger_pos,
                            finger_tgt,
                            lp_pos[0],
                            lp_pos[1],
                            lp_pos[2],
                            obj_z,
                        )
                    )

            # Capture-rate state trace. This uses live tensor joint coordinates
            # under Newton and is intentionally read-only: it lets the retained
            # PNG sequence be matched to the exact close/rebound/lift commands.
            if frame % capture_interval == 0 and self._robot is not None:
                with self._optional_diagnostics("capture state log"):
                    left_pos, right_pos = finger_positions
                    finger_target = self._robot.get_gripper_joint_target()
                    _, _, gantry_z_target = self._robot.get_joint_targets()
                    grasp_dist = self._scene_properties["gripper_position_info"]["grasp_distance"]
                    pad_thickness = self._scene_properties["gripper_pad_properties"]["scale"]
                    if not all(
                        isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
                        for value in (grasp_dist, pad_thickness)
                    ):
                        raise ValueError("Optional gap diagnostic geometry is unavailable or invalid")
                    estimated_inner_gap = grasp_dist + left_pos + right_pos - pad_thickness
                    obj_xyz = tracker.center_history[-1]
                    ctx.log(
                        "[frame-diag] frame=%d t=%.4f phase=%s "
                        "left=%.6f right=%.6f target=%.6f inner_gap=%.6f "
                        "gantry_z_target=%.6f obj=(%.6f,%.6f,%.6f) pose_source=%s"
                        % (
                            frame,
                            time,
                            phases.current_phase_name,
                            left_pos,
                            right_pos,
                            finger_target,
                            estimated_inner_gap,
                            gantry_z_target,
                            obj_xyz[0],
                            obj_xyz[1],
                            obj_xyz[2],
                            tracker.pose_source,
                        )
                    )

            # Stop evaluating phases after the first terminal result. A
            # failure verdict is final, but physics and capture continue
            # briefly to show the resulting drop or instability.
            phase_result = None
            if failure_stop_frame is None and not simulation_complete:
                phase_result = phases.check_frame(frame, time, self, tracker)
                # Completed intermediate phases still return None to the loop.
                # Drain their diagnostic evidence independently of the terminal verdict.
                with self._optional_diagnostics("completed phase evidence"):
                    drain = getattr(phases, "drain_completed_results", None)
                    if callable(drain):
                        for completed_phase in drain():
                            phase_name = str(completed_phase.get("phase_name", "unknown"))
                            ctx.add_metric(f"grasp_{identifier_name}_phase_{phase_name}", completed_phase)
                            for key, value in completed_phase.items():
                                if key not in ("phase_name", "frame", "time", "message", "failed"):
                                    ctx.add_metric(f"grasp_{identifier_name}_{key}", value)
            if phase_result is not None:
                result = phase_result
                with self._optional_diagnostics("phase progress"):
                    ctx.step(
                        "[%s] %s"
                        % (
                            phase_result.get("phase_name", "?"),
                            phase_result.get("message", ""),
                        )
                    )
                # Forward per-phase metrics
                metric_keys = [
                    "stability_frame",
                    "gripper_positioned_frame",
                    "gripper_closed_frame",
                    "lift_height",
                    "lift_success_frame",
                    "hold_duration",
                    "drop_distance",
                    "drop_detection_frame",
                    "drop_observation_seconds",
                    "object_release_frame",
                    # GraspingPhase diagnostics: how far the object
                    # drifted during close, and how closely the gripper
                    # reached its commanded close target.  No behavior
                    # change, purely informational.
                    "grasp_obj_xy_drift_m",
                    "grasp_close_gap_m",
                    "grasp_close_joint_position",
                ]
                prefix = "grasp_%s_" % identifier_name
                with self._optional_diagnostics("phase metrics"):
                    for key in metric_keys:
                        if key in phase_result:
                            ctx.add_metric(prefix + key, phase_result[key])

                if phase_result.get("failed", False):
                    failure_frame = frame
                    failure_stop_frame = post_failure_stop_frame(
                        frame,
                        fps,
                        failure_observation_seconds,
                    )
                    with self._optional_diagnostics("failure observation log"):
                        ctx.log(
                            "[failure-observation] preserving verdict and recording "
                            "%.3fs through frame %d" % (failure_observation_seconds, failure_stop_frame)
                        )
                elif phase_result.get("phase_name") == "GraspAndLift":
                    simulation_complete = True

            media_operation = "camera follow"
            try:
                # Camera follow (tracks asset; gripper is nearby so visible too)
                ctx.scene.update_camera_follow(update_history=(frame % capture_interval == 0))

                # Capture frames only after stability (no need to record settling).
                # stabilize_frames=1: with synchronous rendering
                # (/app/asyncRendering=false) one render tick is a complete,
                # converged-enough frame, so grasp motion footage needs only one
                # pre-render tick. This halves the per-capture render cost vs the
                # old value of 2 (each tick is ~0.2s and grasp_and_lift takes
                # ~180 captures). If the video looks noisy, raise back to 2.
                if phases.capture_active and frame % capture_interval == 0:
                    media_operation = "frame capture"
                    path = await ctx.capture_frame(label=label, stabilize_frames=1)
                    if path:
                        frames.append(path)
            except Exception as error:
                if failure_stop_frame is None:
                    raise
                # The measured failure is already terminal. End the optional
                # tail, retain its original result, and disclose missing media
                # without echoing unbounded native messages or host paths.
                observation_end_frame = frame
                result["failure_media_limited"] = True
                result["failure_media_limitation"] = "Post-failure %s unavailable (%s)." % (
                    media_operation,
                    type(error).__name__[:64],
                )
                with self._optional_diagnostics("failure media warning"):
                    ctx.warn(result["failure_media_limitation"])
                break

            await ctx.physics_advance()

            if failure_stop_frame is not None and frame >= failure_stop_frame:
                observation_end_frame = frame
                with self._optional_diagnostics("failure observation completion log"):
                    ctx.log("[failure-observation] complete at frame %d" % frame)
                break
            if simulation_complete:
                break

        # Encode video
        if frames:
            with self._optional_diagnostics("video encoding"):
                ctx.encode_video(
                    frames,
                    fps=capture_fps,
                    delete_frames=False,
                    label=label,
                    role="summary",
                )

        if result is None:
            result = {
                "phase_name": "Timeout",
                "frame": total_frames,
                "time": sim_seconds,
                "message": "Simulation timeout after %.1fs" % sim_seconds,
                "failed": True,
            }
        elif failure_frame is not None:
            if observation_end_frame is None:
                observation_end_frame = failure_frame
            observed_seconds = (observation_end_frame - failure_frame) / float(fps)
            result["post_failure_observation_seconds"] = observed_seconds
            result["failure_observation_end_frame"] = observation_end_frame
            with self._optional_diagnostics("failure observation metric"):
                ctx.add_metric(
                    "grasp_%s_post_failure_observation_seconds" % identifier_name,
                    observed_seconds,
                )
        return result
