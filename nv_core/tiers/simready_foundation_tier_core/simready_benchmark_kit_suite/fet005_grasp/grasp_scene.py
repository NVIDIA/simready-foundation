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

import carb
import numpy as np
import omni.kit.app
import omni.usd
from isaacsim.core.utils.stage import update_stage_async
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, Usd, UsdGeom
from simready_benchmark_kit_suite.fet005_grasp.grasp_geometry import (
    post_failure_stop_frame,
)
from simready_benchmark_kit_suite.fet005_grasp.grasp_phases import GraspPhaseManager
from simready_benchmark_kit_suite.fet005_grasp.grasp_robot import GraspRobot
from simready_benchmark_kit_suite.fet005_grasp.grasp_utils import AssetPoseTracker
from simready_benchmark_kit_suite.fet005_grasp.newton_articulation import (
    NewtonTensorDriveUnavailable,
    tensor_drive_skip_result,
)


class GraspScene:
    """Manages a single grasp-and-lift test scene for one identifier."""

    def __init__(self, ctx, identifier_path, asset_mount_path):
        # type: (Any, str, str) -> None
        self._ctx = ctx
        self._identifier_path = identifier_path
        self._asset_mount_path = asset_mount_path
        self._robot = None  # type: Optional[GraspRobot]
        self._scene_properties = {}  # type: Dict[str, Any]
        # Tracking state: local grasp points + parent body for per-frame follow
        self._local_gp1 = None  # type: Optional[Any]
        self._local_gp2 = None  # type: Optional[Any]
        self._parent_body_path = None  # type: Optional[str]
        self._gantry_base_world = None  # type: Optional[np.ndarray]

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
        # type: () -> Dict[str, Any]
        return self._scene_properties

    @property
    def grasp_identifier_path(self):
        # type: () -> str
        return self._identifier_path

    # ------------------------------------------------------------------
    # Grasp point extraction
    # ------------------------------------------------------------------

    def compute_local_grasp_points(self):
        # type: () -> Optional[List[Any]]
        """Extract grasp points from grasp_identifier BasisCurves children."""
        stage = self.stage
        id_prim = stage.GetPrimAtPath(self._identifier_path)
        if not id_prim or not id_prim.IsValid():
            return None
        parent = id_prim.GetParent()
        if not parent:
            return None

        gp1_world = None  # type: Optional[Gf.Vec3d]
        gp2_world = None  # type: Optional[Gf.Vec3d]
        xform_cache = UsdGeom.XformCache()

        for child in id_prim.GetChildren():
            pts_attr = child.GetAttribute("points")
            if pts_attr is None:
                continue
            pts = pts_attr.Get()
            if not pts or (hasattr(pts, "__len__") and len(pts) < 2):
                continue
            child_xf = xform_cache.GetLocalToWorldTransform(child).RemoveScaleShear()
            world_pts = [child_xf.Transform(Gf.Vec3d(p)) for p in pts]
            gp1_world = world_pts[0]
            gp2_world = world_pts[1]
            break

        if gp1_world is None or gp2_world is None:
            return None

        body_xf = xform_cache.GetLocalToWorldTransform(parent).RemoveScaleShear()
        inv = body_xf.GetInverse()
        return [inv.Transform(gp1_world), inv.Transform(gp2_world)]

    def compute_world_grasp_points(self, local_gp1, local_gp2):
        # type: (Any, Any) -> List[Gf.Vec3d]
        """Convert local grasp points to world space."""
        id_prim = self.stage.GetPrimAtPath(self._identifier_path)
        body_xf = None
        if id_prim and id_prim.IsValid():
            body_xf = self._body_world_matrix(str(id_prim.GetParent().GetPath()))
        if body_xf is None:
            raise RuntimeError("Cannot resolve the live grasp-body transform")
        return [
            body_xf.Transform(Gf.Vec3d(local_gp1)),
            body_xf.Transform(Gf.Vec3d(local_gp2)),
        ]

    def _body_world_matrix(self, body_path):
        # type: (str) -> Optional[Gf.Matrix4d]
        """Return the active engine's live rigid-body world transform."""
        prim = self.stage.GetPrimAtPath(body_path)
        if not prim or not prim.IsValid():
            return None
        from simready_benchmark_engine_kit.physics_utils import active_physics_engine

        if active_physics_engine() != "physx":
            from simready_benchmark_engine_kit.fabric_utils import live_world_matrix

            rows = live_world_matrix(self.stage, body_path)
            if rows is not None:
                matrix = Gf.Matrix4d(1.0)
                for index in range(4):
                    matrix.SetRow(index, Gf.Vec4d(*rows[index]))
                return matrix.RemoveScaleShear()
        return UsdGeom.XformCache().GetLocalToWorldTransform(prim).RemoveScaleShear()

    # ------------------------------------------------------------------
    # Raycasting symmetrization
    # ------------------------------------------------------------------

    def symmetrize_grasp_points(self, gp1, gp2):
        # type: (np.ndarray, np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]
        """Symmetrize grasp points via PhysX raycasting.

        Returns (adj_gp1, adj_gp2, pad_to_surface_distance).
        """
        axis = gp2 - gp1
        dist = float(np.linalg.norm(axis))
        axis_n = axis / max(1e-9, dist)
        midpoint = (gp1 + gp2) / 2.0

        id_prim = self.stage.GetPrimAtPath(self._identifier_path)
        target_body = str(id_prim.GetParent().GetPath())

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
        local_pts = self.compute_local_grasp_points()
        if local_pts is None or len(local_pts) < 2:
            raise RuntimeError("Failed to extract grasp points from " + self._identifier_path)
        self._local_gp1 = local_pts[0]
        self._local_gp2 = local_pts[1]
        id_prim = self.stage.GetPrimAtPath(self._identifier_path)
        self._parent_body_path = str(id_prim.GetParent().GetPath())

    async def build_robot(self):
        # type: () -> None
        """Build the gripper from initial (pre-stability) grasp points.

        Stores local grasp points and parent body path for per-frame
        tracking during the simulation.
        """
        if self._local_gp1 is None:
            self.init_tracking()

        world_pts = self.compute_world_grasp_points(self._local_gp1, self._local_gp2)
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
        """Enable or disable collision on the pad cube prims.

        Disabled during stability to prevent pads from pushing the object.
        Re-enabled before grasping so pads can make contact.
        """
        from pxr import UsdPhysics

        stage = self.stage
        for cube_path in [
            GraspRobot.LEFT_PAD + "/Cube",
            GraspRobot.RIGHT_PAD + "/Cube",
        ]:
            prim = stage.GetPrimAtPath(cube_path)
            if not prim or not prim.IsValid():
                continue
            col_api = UsdPhysics.CollisionAPI.Get(stage, cube_path)
            if col_api:
                col_api.GetCollisionEnabledAttr().Set(enabled)

    def disable_gripper_pad_collisions(self):
        # type: () -> None
        """Remove generated pad contact after the jaws finish opening.

        The pads are temporary test-fixture geometry. Disabling only their
        collision prevents residual solver contact from retaining a released
        object while leaving the Dropping phase's free-fall assertion intact.
        """
        self._set_pad_collision_enabled(False)

    def get_current_world_grasp_points(self):
        # type: () -> Optional[Tuple[np.ndarray, np.ndarray]]
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
        # type: () -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]
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
        physics.stop()

        # Delete old gripper
        stage = self.stage
        old_robot_prim = stage.GetPrimAtPath(GraspRobot.ROBOT_PATH)
        if old_robot_prim and old_robot_prim.IsValid():
            stage.RemovePrim(GraspRobot.ROBOT_PATH)
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
        physics.play()
        await self._ctx.settle(count=1)

        from simready_benchmark_engine_kit.physics_utils import active_physics_engine

        if active_physics_engine() == "newton":
            ready = await self._robot.init_newton_tensor_drive(self._ctx)
            self._ctx.log("[rebuild] Newton tensor finger control %s" % ("ready" if ready else "UNAVAILABLE"))
            if not ready:
                raise NewtonTensorDriveUnavailable("Newton tensor finger control could not be initialized")
        return True

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    async def run_simulation(self, cfg, identifier_name, physics=None):
        # type: (Dict[str, Any], str, Any) -> Dict[str, Any]
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
        frames = []  # type: List[str]

        result = None  # type: Optional[Dict[str, Any]]
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
            tracker.record_frame(asset_prim, time)

            # Record gripper joint position if robot exists
            if self._robot is not None:
                try:
                    tracker.record_joint_position(self._robot.get_gripper_joint_position())
                except Exception:
                    pass

            # Per-frame grasp line tracking: move gantry to follow
            # the object until Lifting starts
            if phases.tracking_active:
                self.track_grasp_line()

                # Diagnostic logging (once per second)
                if frame % log_interval == 0:
                    pts = self.get_current_world_grasp_points()
                    if pts is not None and self._robot is not None:
                        gp1, gp2 = pts
                        mid = 0.5 * (gp1 + gp2)
                        jx, jy, jz = self._robot.get_joint_targets()
                        gx_prim = self.stage.GetPrimAtPath(GraspRobot.GANTRY_X)
                        gx_pos = (0.0, 0.0, 0.0)
                        if gx_prim and gx_prim.IsValid():
                            gx_xf = UsdGeom.Xformable(gx_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                            gx_t = gx_xf.ExtractTranslation()
                            gx_pos = (float(gx_t[0]), float(gx_t[1]), float(gx_t[2]))
                        ctx.log(
                            "[track] t=%.1fs phase=%s "
                            "grasp_mid=(%.3f,%.3f,%.3f) "
                            "joint_tgt=(%.3f,%.3f,%.3f) "
                            "gantry_x_actual=(%.3f,%.3f,%.3f) "
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
                try:
                    await self.rebuild_gripper_at_settled_position(
                        physics,
                        floor_level=floor_level,
                        pad_ground_clearance=pad_ground_clearance,
                    )
                    pad_props = self._scene_properties.get("gripper_pad_properties", {})
                    ctx.log(
                        "[fixture-load] source=%s authored_mass_count=%d "
                        "mass=%.6fkg max_force=%.6fN"
                        % (
                            pad_props.get("mass_source", "unknown"),
                            int(pad_props.get("authored_mass_count", 0)),
                            float(pad_props.get("mass", 0.0)),
                            float(pad_props.get("max_force", 0.0)),
                        )
                    )
                    ctx.add_metric(
                        "grasp_%s_fixture_mass_kg" % identifier_name,
                        float(pad_props.get("mass", 0.0)),
                    )
                    ctx.add_metric(
                        "grasp_%s_fixture_max_force_n" % identifier_name,
                        float(pad_props.get("max_force", 0.0)),
                    )
                    ctx.add_metric(
                        "grasp_%s_fixture_mass_source" % identifier_name,
                        str(pad_props.get("mass_source", "unknown")),
                    )
                except NewtonTensorDriveUnavailable as exc:
                    ctx.log("[rebuild] NEWTON CONTROL UNAVAILABLE: %s" % exc)
                    return tensor_drive_skip_result(exc)
                except Exception as exc:
                    ctx.log("[rebuild] FAILED: %s" % exc)

            # Diagnostic logging every second (all phases, not just tracking)
            if frame % log_interval == 0 and self._robot is not None:
                finger_pos = self._robot.get_gripper_joint_position()
                finger_tgt = self._robot.get_gripper_joint_target()
                # Read left pad world position
                lp = self.stage.GetPrimAtPath(GraspRobot.LEFT_PAD)
                lp_pos = (0.0, 0.0, 0.0)
                if lp and lp.IsValid():
                    lp_xf = UsdGeom.Xformable(lp).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    lp_t = lp_xf.ExtractTranslation()
                    lp_pos = (float(lp_t[0]), float(lp_t[1]), float(lp_t[2]))
                obj_z = 0.0
                if tracker.center_history:
                    obj_z = tracker.center_history[-1][2]
                ctx.log(
                    "[diag] t=%.1fs phase=%s "
                    "finger_pos=%.4f finger_tgt=%.4f "
                    "left_pad=(%.3f,%.3f,%.3f) obj_z=%.4f"
                    % (time, phases.current_phase_name, finger_pos, finger_tgt, lp_pos[0], lp_pos[1], lp_pos[2], obj_z)
                )

            # Capture-rate state trace. This uses live tensor joint coordinates
            # under Newton and is intentionally read-only: it lets the retained
            # PNG sequence be matched to the exact close/rebound/lift commands.
            if frame % capture_interval == 0 and self._robot is not None:
                left_pos, right_pos = self._robot.get_finger_joint_positions()
                finger_target = self._robot.get_gripper_joint_target()
                _, _, gantry_z_target = self._robot.get_joint_targets()
                grasp_dist = float(self._scene_properties.get("gripper_position_info", {}).get("grasp_distance", 0.0))
                pad_thickness = float(self._scene_properties.get("gripper_pad_properties", {}).get("scale", 0.0))
                estimated_inner_gap = grasp_dist + left_pos + right_pos - pad_thickness
                obj_xyz = tracker.center_history[-1] if tracker.center_history else (0.0, 0.0, 0.0)
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
            if phase_result is not None:
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
                for key in metric_keys:
                    if key in phase_result:
                        ctx.add_metric(prefix + key, phase_result[key])

                result = phase_result
                if phase_result.get("failed", False):
                    failure_frame = frame
                    failure_stop_frame = post_failure_stop_frame(
                        frame,
                        fps,
                        failure_observation_seconds,
                    )
                    ctx.log(
                        "[failure-observation] preserving verdict and recording "
                        "%.3fs through frame %d" % (failure_observation_seconds, failure_stop_frame)
                    )
                elif phase_result.get("phase_name") == "GraspAndLift":
                    simulation_complete = True

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
                path = await ctx.capture_frame(label=label, stabilize_frames=1)
                if path:
                    frames.append(path)

            await ctx.physics_advance()

            if failure_stop_frame is not None and frame >= failure_stop_frame:
                observation_end_frame = frame
                ctx.log("[failure-observation] complete at frame %d" % frame)
                break
            if simulation_complete:
                break

        # Encode video
        if frames:
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
            ctx.add_metric(
                "grasp_%s_post_failure_observation_seconds" % identifier_name,
                observed_seconds,
            )
        return result
