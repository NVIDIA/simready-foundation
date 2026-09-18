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
"""Programmatic parallel-jaw gripper for grasp-and-lift tests.

Builds a gantry-based gripper articulation from USD primitives.
Pad size, mass, friction, and drive forces are computed from the
target asset's bounding box and mass.

Ported from V1 FET005_grasp/grasp_robot.py.
"""
import math

import carb
import numpy as np
from isaacsim.core.api.materials.physics_material import PhysicsMaterial
from isaacsim.core.api.objects.cuboid import FixedCuboid
from isaacsim.core.utils.stage import update_stage_async
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics
from simready_benchmark_kit_suite.fet005_grasp.grasp_geometry import (
    pad_ground_clearance_offset,
    resolve_test_fixture_mass,
)
from simready_benchmark_kit_suite.fet005_grasp.newton_articulation import (
    author_newton_pd_actuator,
    compute_newton_pd_parameters,
)
from simready_benchmark_kit_suite.fet005_grasp.transform_utils import (
    compute_gripper_orientation_from_grasp_points,
    projected_aabb_extent,
    set_pose_from_transform,
)


class GraspRobot:
    """Encapsulates the gantry + parallel-jaw gripper articulation."""

    TENSOR_PASSIVE_JOINTS = ()
    PAD_FACE_BBOX_MULTIPLIER = 0.35

    # Prim path constants
    ROBOT_PATH = "/World/grasp_robot"
    GANTRY_BASE = ROBOT_PATH + "/gantry_base"
    GANTRY_Z = ROBOT_PATH + "/gantry_z"
    GANTRY_Y = ROBOT_PATH + "/gantry_y"
    GANTRY_X = ROBOT_PATH + "/gantry_x"
    JOINT_Z = GANTRY_BASE + "/joint_z"
    JOINT_X = GANTRY_Z + "/joint_x"
    JOINT_Y = GANTRY_Y + "/joint_y"
    LEFT_PAD = ROBOT_PATH + "/left_pad"
    RIGHT_PAD = ROBOT_PATH + "/right_pad"

    # Path to the left finger joint (used for reading joint state)
    LEFT_JOINT = GANTRY_X + "/left_joint"

    def __init__(self, stage):
        # type: (Usd.Stage) -> None
        self._stage = stage
        self._scene_properties = {}  # type: Dict[str, Any]
        self._tensor_art = None  # type: Optional[Any]
        self._dof_index = {}  # type: Dict[str, int]
        self._targets = None  # type: Optional[Any]

    async def init_newton_tensor_drive(self, ctx):
        # type: (Any) -> bool
        """Initialize Newton control using gains compiled from authored USD.

        The generated drives are authored before Newton compiles the
        articulation. Do not rewrite controller gains after initialization:
        some Isaac builds expose device-backed gain buffers that cannot safely
        accept host-side arrays.
        """
        try:
            from simready_benchmark_kit_suite.articulation_phases.robot_handle import (
                RobotHandle,
            )
            from simready_benchmark_kit_suite.articulation_phases.robot_type import (
                RobotType,
            )

            art = RobotHandle(
                self._stage,
                self.ROBOT_PATH,
                self._stage.GetPrimAtPath(self.ROBOT_PATH),
                RobotType.GRIPPER,
            )
            await art.initialize_newton(ctx)
            names = list(art.dof_names)
            required = {"joint_x", "joint_y", "joint_z", "left_joint", "right_joint"}
            if not required.issubset(names):
                missing = ", ".join(sorted(required.difference(names)))
                raise RuntimeError("Newton gripper articulation is missing DOFs: " + missing)

            self._tensor_art = art
            self._dof_index = {name: index for index, name in enumerate(names)}
            # The generated gripper is authored and rebuilt with every drive
            # target at zero. Avoid converting the GPU-backed live position
            # tensor to NumPy during initialization.
            self._targets = np.zeros(len(names), dtype=np.float64)
            carb.log_info(
                "[grasp-robot] Newton tensor control ready; both finger joints "
                "use native actuators with gains authored before compilation"
            )
            return True
        except Exception as exc:
            self._tensor_art = None
            self._dof_index = {}
            self._targets = None
            carb.log_error("[grasp-robot] Newton tensor control unavailable: %s" % exc)
            return False

    def teardown(self):
        # type: () -> None
        """Release the runtime controller bridge, if one was initialized."""
        if self._tensor_art is not None:
            try:
                self._tensor_art.teardown()
            except Exception:
                pass
        self._tensor_art = None
        self._dof_index = {}
        self._targets = None

    def _apply_tensor_targets(self):
        # type: () -> None
        """Apply targets to every actively controlled generated joint."""
        from isaacsim.core.utils.types import ArticulationAction  # type: ignore

        passive_indices = {self._dof_index[name] for name in self.TENSOR_PASSIVE_JOINTS}
        indices = [index for index in range(len(self._targets)) if index not in passive_indices]
        positions = [float(self._targets[index]) for index in indices]
        self._tensor_art.apply_action(
            ArticulationAction(
                joint_positions=np.array(positions, dtype=np.float64),
                joint_indices=indices,
            )
        )

    def _set_tensor_targets(self, values):
        # type: (Dict[str, float]) -> None
        if self._tensor_art is None or self._targets is None:
            return
        for name, value in values.items():
            if name in self.TENSOR_PASSIVE_JOINTS:
                raise ValueError("cannot command passive mimic joint " + name)
            index = self._dof_index.get(name)
            if index is not None:
                self._targets[index] = float(value)
        self._apply_tensor_targets()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    async def build_for_asset(
        cls,
        stage,  # type: Usd.Stage
        grasp_point_1,  # type: List[float]
        grasp_point_2,  # type: List[float]
        target_asset_path,  # type: str
        pad_to_surface_distance,  # type: float
        grasp_body_path=None,  # type: Optional[str]
        floor_level=0.0,  # type: float
        pad_ground_clearance=0.002,  # type: float
    ):
        # type: (...) -> GraspRobot
        """Create a GraspRobot configured for the given asset.

        Uses only USD/PhysX APIs -- no World or Robot wrapper needed.
        The V2 framework handles physics init via ctx.scene.add_physics().
        """
        self = cls(stage)

        pad_props = self._compute_pad_properties(
            target_asset_path,
            geometry_path=grasp_body_path,
        )

        grip_info = compute_gripper_orientation_from_grasp_points(grasp_point_1, grasp_point_2)

        # Ensure pad_scale is small enough to fit between the grasp points.
        # If pads are wider than the gap, the gripper can't close at all.
        grasp_dist = grip_info["grasp_distance"]
        if grasp_dist > 1e-6:
            max_pad = grasp_dist * 0.3  # pads take at most 30% of grasp gap
            if pad_props["scale"] > max_pad:
                pad_props["scale"] = max_pad
        pad_props["dimensions"] = (
            pad_props["scale"],
            self.PAD_FACE_BBOX_MULTIPLIER
            * projected_aabb_extent(pad_props["asset_bbox_size_m"], grip_info["gripper_face_y"]),
            self.PAD_FACE_BBOX_MULTIPLIER
            * projected_aabb_extent(pad_props["asset_bbox_size_m"], grip_info["gripper_face_z"]),
        )
        ground_offset_z = pad_ground_clearance_offset(
            grip_info["left_joint_world_pos"],
            grip_info["right_joint_world_pos"],
            pad_props["dimensions"],
            (
                grip_info["grasp_direction"],
                grip_info["gripper_face_y"],
                grip_info["gripper_face_z"],
            ),
            floor_level=floor_level,
            clearance=pad_ground_clearance,
        )
        if ground_offset_z > 0.0:
            for key in (
                "gripper_base_position",
                "left_joint_world_pos",
                "right_joint_world_pos",
            ):
                grip_info[key][2] += ground_offset_z
        grip_info["ground_clearance_offset_z"] = ground_offset_z
        object_grip_extent = projected_aabb_extent(
            pad_props["asset_bbox_size_m"],
            grip_info["grasp_direction"],
        )
        expected_contact_travel = max(
            0.0,
            (grasp_dist - pad_props["scale"] - object_grip_extent) / 2.0,
        )

        pad_mass = min(0.1, pad_props["mass"] * 0.01)

        await self._create_gantry(grip_info)
        await self._create_pads_and_fingers(grip_info, pad_props, pad_mass, target_asset_path)

        # Set solver iterations on the articulation root
        px_art = PhysxSchema.PhysxArticulationAPI.Get(stage, self.ROBOT_PATH)
        if px_art:
            px_art.CreateSolverPositionIterationCountAttr(64)
            px_art.CreateSolverVelocityIterationCountAttr(4)
        await update_stage_async()

        self._scene_properties = {
            "gantry_x_path": cls.GANTRY_X,
            "target_asset_path": target_asset_path,
            "grasp_point_1": grasp_point_1,
            "grasp_point_2": grasp_point_2,
            "gripper_position_info": grip_info,
            "gripper_pad_properties": pad_props,
            "pad_to_surface_distance": pad_to_surface_distance,
            "expected_contact_travel": expected_contact_travel,
            "pad_ground_offset_z": ground_offset_z,
        }
        return self

    async def _create_pads_and_fingers(self, grip_info, pad_props, pad_mass, target_asset_path):
        # type: (Dict[str, Any], Dict[str, Any], float, str) -> None
        """Create gripper pads, finger joints, runtime controls, and collision."""
        stage = self._stage

        # Create pad Xforms and apply physics
        for pad_path, world_pos in [
            (self.LEFT_PAD, grip_info["left_joint_world_pos"]),
            (self.RIGHT_PAD, grip_info["right_joint_world_pos"]),
        ]:
            prim = stage.DefinePrim(pad_path, "Xform")
            set_pose_from_transform(prim, world_pos, grip_info["gripper_orientation"])
            UsdPhysics.RigidBodyAPI.Apply(prim)
            mass_api = UsdPhysics.MassAPI.Apply(prim)
            mass_api.CreateMassAttr(pad_mass)

        # Overlap check (pads vs. object mesh)
        if self._check_pad_overlap(grip_info, pad_props["dimensions"], target_asset_path):
            raise RuntimeError("Gripper pads overlap with object mesh at " + target_asset_path)

        # Finger joints
        grasp_distance = grip_info["grasp_distance"]
        if grasp_distance <= 1e-8:
            max_joint_travel = 0.0
        else:
            max_joint_travel = max(0.0, (grasp_distance / 2.0) - (pad_props["scale"] / 2.0))
        joint_limits = [-max_joint_travel, 0.0]

        # Compute local anchor positions in gantry_x frame
        gantry_x_prim = stage.GetPrimAtPath(self.GANTRY_X)
        gantry_x_xf = UsdGeom.Xformable(gantry_x_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        gantry_x_inv = gantry_x_xf.GetInverse()
        left_anchor = gantry_x_inv.Transform(Gf.Vec3d(*grip_info["left_joint_world_pos"]))
        right_anchor = gantry_x_inv.Transform(Gf.Vec3d(*grip_info["right_joint_world_pos"]))

        left_joint_path = self.GANTRY_X + "/left_joint"
        await self._create_prismatic_joint(
            left_joint_path,
            UsdPhysics.Tokens.x,
            self.GANTRY_X,
            self.LEFT_PAD,
            local_pos0=list(left_anchor),
            local_rot0=Gf.Quatf(0, 0, 0, 1),
            limits=joint_limits,
        )
        right_joint_path = self.GANTRY_X + "/right_joint"
        await self._create_prismatic_joint(
            right_joint_path,
            UsdPhysics.Tokens.x,
            self.GANTRY_X,
            self.RIGHT_PAD,
            local_pos0=list(right_anchor),
            limits=joint_limits,
        )

        # The generated joints have mirrored local axes, so both internal joint
        # coordinates use the same sign. Drive both jaws explicitly: PhysX does
        # not enforce PhysxMimicJointAPI on prismatic DOFs, and a passive
        # follower can spring open when the gantry starts moving laterally.
        from simready_benchmark_engine_kit.physics_utils import active_physics_engine

        if active_physics_engine() == "newton":
            params = compute_newton_pd_parameters(
                pad_props["max_force"],
                pad_mass,
                pad_props["static_friction"],
                pad_props["max_velocity"],
            )
            carb.log_info(
                "[grasp-robot] Newton per-jaw controller: "
                "object_mass=%.6fkg effort=%.6fN kp=%.3f kd=%.3f velocity_limit=%.6fm/s"
                % (
                    pad_props["mass"],
                    params["max_effort"],
                    params["stiffness"],
                    params["damping"],
                    params["max_velocity"],
                )
            )
            for joint_path, name in (
                (left_joint_path, "left_finger_actuator"),
                (right_joint_path, "right_finger_actuator"),
            ):
                author_newton_pd_actuator(
                    stage,
                    self.ROBOT_PATH + "/actuators/" + name,
                    joint_path,
                    params["stiffness"],
                    params["damping"],
                    params["max_effort"],
                    params["max_velocity"],
                )
        else:
            # Keep the established PhysX force and gain scale on each jaw.
            # ``max_force`` already represents a safety-factored fixture load;
            # reducing it again by friction and splitting it between the jaws
            # makes heavy or eccentric props slip as soon as the gantry moves.
            # Explicit bilateral drives replace the unsupported prismatic
            # mimic coupling without weakening the original squeeze.
            max_effort = pad_props["max_force"]
            stiffness = max(200.0, min(max_effort / 0.005, 5000.0))
            damping = max(100.0, min(2.0 * math.sqrt(pad_mass * stiffness), 1000.0))
            max_velocity = max(0.01, min(pad_props["max_velocity"], 0.5))
            carb.log_info(
                "[grasp-robot] PhysX balanced per-jaw controller: "
                "object_mass=%.6fkg effort=%.6fN kp=%.3f kd=%.3f velocity_limit=%.6fm/s"
                % (
                    pad_props["mass"],
                    max_effort,
                    stiffness,
                    damping,
                    max_velocity,
                )
            )
            for joint_path in (left_joint_path, right_joint_path):
                await self._configure_drive(
                    joint_path,
                    target_position=0.0,
                    stiffness=stiffness,
                    damping=damping,
                    max_force=max_effort,
                    max_velocity=max_velocity,
                )

        self._create_pad_cubes(pad_props)
        await update_stage_async()

    def _create_pad_cubes(self, pad_props):
        # type: (Dict[str, Any]) -> None
        """Create the visual/collision pad cubes with physics material."""
        material_path = "/World/GripperMaterial"
        gripper_material = PhysicsMaterial(
            material_path,
            static_friction=pad_props["static_friction"],
            dynamic_friction=pad_props["dynamic_friction"],
            restitution=0.0,
        )
        for cube_path in [self.LEFT_PAD + "/Cube", self.RIGHT_PAD + "/Cube"]:
            cube = FixedCuboid(
                prim_path=cube_path,
                scale=list(pad_props["dimensions"]),
                color=np.array([255, 0, 0]) if "left" in cube_path else np.array([0, 255, 0]),
                physics_material=gripper_material,
            )
            cube.set_collision_approximation("convexHull")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def scene_properties(self):
        # type: () -> Dict[str, Any]
        return dict(self._scene_properties)

    def open(self):
        # type: () -> None
        """Fully open the gripper (target position = 0)."""
        self._set_finger_target(0.0)

    def close(self, close_position):
        # type: (float) -> None
        """Set the gripper close position via drive target."""
        self._set_finger_target(close_position)

    def lift(self, target_z, base_x=None, base_y=None):
        # type: (float, Optional[float], Optional[float]) -> None
        """Lift the gripper to target_z."""
        if base_x is None or base_y is None:
            cx, cy, _ = self.get_joint_targets()
            if base_x is None:
                base_x = cx
            if base_y is None:
                base_y = cy
        self.update_joint_target_positions(float(base_x), float(base_y), float(target_z))

    def update_joint_target_positions(self, x, y, z):
        # type: (float, float, float) -> None
        """Set all 3 gantry joint target positions."""
        if self._tensor_art is not None:
            self._set_tensor_targets({"joint_x": x, "joint_y": y, "joint_z": z})
            return
        for path, val in [
            (self.JOINT_X, x),
            (self.JOINT_Y, y),
            (self.JOINT_Z, z),
        ]:
            prim = self._stage.GetPrimAtPath(path)
            if prim and prim.IsValid():
                attr = prim.GetAttribute("drive:linear:physics:targetPosition")
                if attr:
                    attr.Set(float(val))

    def get_joint_target(self, joint_path):
        # type: (str) -> float
        """Get current target position for a prismatic joint."""
        prim = self._stage.GetPrimAtPath(joint_path)
        if not prim:
            return 0.0
        attr = prim.GetAttribute("drive:linear:physics:targetPosition")
        val = attr.Get() if attr else None
        try:
            return float(val)
        except Exception:
            return 0.0

    def get_joint_targets(self):
        # type: () -> Tuple[float, float, float]
        """Return current (x, y, z) gantry joint targets."""
        if self._targets is not None:
            try:
                return tuple(float(self._targets[self._dof_index[name]]) for name in ("joint_x", "joint_y", "joint_z"))
            except (IndexError, KeyError, TypeError, ValueError):
                pass
        return (
            self.get_joint_target(self.JOINT_X),
            self.get_joint_target(self.JOINT_Y),
            self.get_joint_target(self.JOINT_Z),
        )

    def get_gripper_joint_position(self):
        # type: () -> float
        """Return the current finger joint position (left joint).

        Newton state is read from the live articulation tensor view. PhysX
        reads PhysxSchema.JointStateAPI from USD.
        """
        if self._tensor_art is not None:
            index = self._dof_index.get("left_joint")
            if index is None:
                return 0.0
            try:
                return float(self._tensor_art.get_joint_positions()[index])
            except Exception:
                return 0.0
        prim = self._stage.GetPrimAtPath(self.LEFT_JOINT)
        if not prim or not prim.IsValid():
            return 0.0
        attr = prim.GetAttribute("state:linear:physics:position")
        if not attr or not attr.HasValue():
            # Fallback: read drive target position
            attr = prim.GetAttribute("drive:linear:physics:targetPosition")
        val = attr.Get() if attr else None
        try:
            return float(val)
        except Exception:
            return 0.0

    def get_finger_joint_positions(self):
        # type: () -> Tuple[float, float]
        """Return live leader and follower positions for transition diagnostics."""
        if self._tensor_art is not None:
            try:
                positions = self._tensor_art.get_joint_positions()
                return (
                    float(positions[self._dof_index["left_joint"]]),
                    float(positions[self._dof_index["right_joint"]]),
                )
            except Exception:
                return (0.0, 0.0)

        def usd_position(path):
            prim = self._stage.GetPrimAtPath(path)
            attr = prim.GetAttribute("state:linear:physics:position") if prim else None
            value = attr.Get() if attr and attr.HasValue() else None
            try:
                return float(value)
            except Exception:
                return 0.0

        return (
            usd_position(self.LEFT_JOINT),
            usd_position(self.GANTRY_X + "/right_joint"),
        )

    def get_gripper_joint_target(self):
        # type: () -> float
        """Return the active left-finger target for the selected engine."""
        if self._targets is not None:
            try:
                return float(self._targets[self._dof_index["left_joint"]])
            except (IndexError, KeyError, TypeError, ValueError):
                return 0.0
        return self.get_joint_target(self.LEFT_JOINT)

    def _set_finger_target(self, position):
        # type: (float) -> None
        """Set the runtime's finger-joint target position."""
        if self._tensor_art is not None:
            self._set_tensor_targets({"left_joint": position, "right_joint": position})
            return
        prim = self._stage.GetPrimAtPath(self.LEFT_JOINT)
        right_prim = self._stage.GetPrimAtPath(self.GANTRY_X + "/right_joint")
        for joint_prim in (prim, right_prim):
            if joint_prim and joint_prim.IsValid():
                attr = joint_prim.GetAttribute("drive:linear:physics:targetPosition")
                if attr:
                    attr.Set(float(position))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_gantry(self, grip_info):
        # type: (Dict[str, Any]) -> None
        midpoint = grip_info["gripper_base_position"]
        orientation = grip_info["gripper_orientation"]

        # Articulation root
        robot_prim = self._stage.DefinePrim(self.ROBOT_PATH, "Xform")
        UsdPhysics.ArticulationRootAPI.Apply(robot_prim)
        PhysxSchema.PhysxArticulationAPI.Apply(robot_prim)

        # Base (fixed to world via root joint).
        # All gantry nodes get explicit mass so PhysX has valid inertia.
        # Without mass, PhysX logs "invalid inertia tensor" and drives
        # can't move the bodies properly.
        gantry_mass = 1.0  # kg -- lightweight for fast drive response
        base_prim = self._stage.DefinePrim(self.GANTRY_BASE, "Xform")
        UsdPhysics.RigidBodyAPI.Apply(base_prim)
        UsdPhysics.MassAPI.Apply(base_prim).CreateMassAttr(gantry_mass)
        set_pose_from_transform(base_prim, midpoint, [1.0, 0.0, 0.0, 0.0])

        root_joint = UsdPhysics.FixedJoint.Define(self._stage, self.ROBOT_PATH + "/root_joint")
        root_joint.CreateBody1Rel().SetTargets([self.GANTRY_BASE])

        # Gantry nodes (Z, Y, X) -- all get explicit mass
        for path, rot in [
            (self.GANTRY_Z, [1.0, 0.0, 0.0, 0.0]),
            (self.GANTRY_Y, [1.0, 0.0, 0.0, 0.0]),
            (self.GANTRY_X, orientation),
        ]:
            prim = self._stage.DefinePrim(path, "Xform")
            UsdPhysics.RigidBodyAPI.Apply(prim)
            UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(gantry_mass)
            set_pose_from_transform(prim, midpoint, rot)

        # Prismatic joints: base->Z->Y->X
        await self._create_prismatic_joint(
            self.JOINT_Z,
            UsdPhysics.Tokens.z,
            self.GANTRY_BASE,
            self.GANTRY_Z,
            limits=[-10.0, 10.0],
        )
        await self._create_prismatic_joint(
            self.JOINT_X,
            UsdPhysics.Tokens.x,
            self.GANTRY_Z,
            self.GANTRY_Y,
            limits=[-10.0, 10.0],
        )
        await self._create_prismatic_joint(
            self.JOINT_Y,
            UsdPhysics.Tokens.y,
            self.GANTRY_Y,
            self.GANTRY_X,
            limits=[-10.0, 10.0],
        )

        # Configure gantry drives. With mass=1kg, use high stiffness
        # and near-critical damping (2*sqrt(m*k)) for fast convergence.
        # stiffness=50000, critical_damping=2*sqrt(1*50000)=447
        gantry_stiffness = 50000.0
        gantry_damping = 2.0 * math.sqrt(gantry_mass * gantry_stiffness)
        for path in [self.JOINT_X, self.JOINT_Y, self.JOINT_Z]:
            await self._configure_drive(
                path,
                target_position=0.0,
                stiffness=gantry_stiffness,
                damping=gantry_damping,
                max_force=10000.0,
                max_velocity=20.0,
            )
        await update_stage_async()

    async def _create_prismatic_joint(
        self,
        joint_path,
        axis_token,
        body0,
        body1,
        local_pos0=None,
        local_rot0=None,
        limits=None,
    ):
        # type: (...) -> str
        joint = UsdPhysics.PrismaticJoint.Define(self._stage, joint_path)
        joint.CreateAxisAttr().Set(axis_token)
        joint.CreateBody0Rel().SetTargets([body0])
        joint.CreateBody1Rel().SetTargets([body1])
        if local_pos0 is not None:
            joint.CreateLocalPos0Attr().Set(Gf.Vec3f(*[float(c) for c in local_pos0]))
        if local_rot0 is not None:
            joint.CreateLocalRot0Attr().Set(local_rot0)
        if limits is not None:
            joint.CreateLowerLimitAttr().Set(float(limits[0]))
            joint.CreateUpperLimitAttr().Set(float(limits[1]))
        joint.CreateBreakForceAttr().Set(1000000.0)
        joint.CreateBreakTorqueAttr().Set(1000000.0)
        return joint_path

    async def _configure_drive(
        self,
        joint_path,
        target_position,
        stiffness,
        damping,
        max_force,
        max_velocity,
    ):
        # type: (...) -> None
        prim = self._stage.GetPrimAtPath(joint_path)
        drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
        PhysxSchema.JointStateAPI.Apply(prim, "linear")
        drive.CreateTargetPositionAttr().Set(target_position)
        drive.CreateStiffnessAttr().Set(stiffness)
        drive.CreateDampingAttr().Set(damping)
        drive.CreateMaxForceAttr().Set(max_force)
        px = PhysxSchema.PhysxJointAPI.Get(self._stage, joint_path)
        px.CreateMaxJointVelocityAttr().Set(max_velocity)

    def _compute_pad_properties(self, target_asset_path, geometry_path=None):
        # type: (str, Optional[str]) -> Dict[str, Any]
        """Compute pad scale, mass, friction, force from target object."""
        asset_prim = self._stage.GetPrimAtPath(target_asset_path)
        geometry_prim = self._stage.GetPrimAtPath(geometry_path) if geometry_path else asset_prim
        if not geometry_prim or not geometry_prim.IsValid():
            raise ValueError("grasp body is missing: " + str(geometry_path))
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
        # Size the pads and closing aperture from the body selected by the
        # grasp identifier, not from unrelated bodies in the same assembly.
        # A hammer head, for example, is much wider than its grasped handle.
        world_bound = bbox_cache.ComputeWorldBound(geometry_prim)
        aligned = world_bound.ComputeAlignedBox()
        size = aligned.GetSize()
        dimension = max(size[0], size[1], size[2])
        volume = size[0] * size[1] * size[2]

        min_dim = min(size[0], size[1], size[2])
        max_dim = max(size[0], size[1], size[2])
        aspect = max_dim / min_dim if min_dim > 0 else 1.0

        if aspect > 5.0:
            # Elongated assets (lamps, handles, shafts): smaller pads so
            # they fit around thin bodies without overlapping the object.
            pad_scale = min_dim * 0.3
        else:
            geometric_mean = (size[0] * size[1] * size[2]) ** (1.0 / 3.0)
            pad_scale = geometric_mean * 0.1

        # Minimum pad scale: 5mm.  The previous 2cm floor caused thin
        # graspable bodies (lamp shafts, handles) to be missed entirely
        # -- the closed pads met 8-15mm apart, never contacting the
        # object.  5mm is the lowest we can go before thin collision
        # meshes risk tunneling.
        pad_scale = max(0.005, pad_scale)

        # Runtime payloads commonly keep MassAPI on instance-proxy descendants.
        # A plain PrimRange stops at each instance root, misses those values,
        # and makes the fixture fall back to a bounding-box density estimate.
        # On a large but light prop that can inflate the commanded jaw force by
        # orders of magnitude and destabilize an otherwise valid simulation.
        mass_values = (
            UsdPhysics.MassAPI(prim).GetMassAttr().Get()
            for prim in Usd.PrimRange(
                asset_prim,
                Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate),
            )
            if prim.HasAPI(UsdPhysics.MassAPI)
        )
        total_mass, mass_source, authored_mass_count = resolve_test_fixture_mass(
            mass_values,
            volume,
        )

        required_force = total_mass * 9.81 * 5.0
        carb.log_info(
            "[grasp-robot] fixture load source=%s authored_mass_count=%d "
            "mass=%.6fkg max_force=%.6fN"
            % (mass_source, authored_mass_count, total_mass, required_force)
        )
        try:
            max_velocity = min(0.5, 0.1 * float(dimension))
        except Exception:
            max_velocity = 0.1

        return {
            "scale": pad_scale,
            "asset_bbox_size_m": tuple(float(value) for value in size),
            "mass": total_mass,
            "mass_source": mass_source,
            "authored_mass_count": authored_mass_count,
            "static_friction": 5.0,
            "dynamic_friction": 5.0,
            "max_force": required_force,
            "max_velocity": max_velocity,
        }

    def _check_pad_overlap(self, grip_info, pad_dimensions, target_asset_path):
        # type: (Dict[str, Any], Tuple[float, float, float], str) -> bool
        """Return True if either pad cube overlaps the target object."""
        extent = carb.Float3(*(float(value) / 2.0 for value in pad_dimensions))
        orientation = grip_info["gripper_orientation"]
        rotation = carb.Float4(*orientation)
        asset_hits = [0]

        def report_hit(hit):
            body = hit.get("rigidBody", "") if isinstance(hit, dict) else getattr(hit, "rigidBody", "")
            if target_asset_path in str(body):
                asset_hits[0] += 1
            return True

        for pos in [
            grip_info["left_joint_world_pos"],
            grip_info["right_joint_world_pos"],
        ]:
            origin = carb.Float3(*pos)
            get_physx_scene_query_interface().overlap_box(extent, origin, rotation, report_hit, False)
        return asset_hits[0] > 0
