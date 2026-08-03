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
from simready_benchmark_kit_suite.fet005_grasp.transform_utils import (
    compute_gripper_orientation_from_grasp_points,
    set_pose_from_transform,
)


class GraspRobot:
    """Encapsulates the gantry + parallel-jaw gripper articulation."""

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
    ):
        # type: (...) -> GraspRobot
        """Create a GraspRobot configured for the given asset.

        Uses only USD/PhysX APIs -- no World or Robot wrapper needed.
        The V2 framework handles physics init via ctx.scene.add_physics().
        """
        self = cls(stage)

        pad_props = self._compute_pad_properties(target_asset_path)

        grip_info = compute_gripper_orientation_from_grasp_points(grasp_point_1, grasp_point_2)

        # Ensure pad_scale is small enough to fit between the grasp points.
        # If pads are wider than the gap, the gripper can't close at all.
        grasp_dist = grip_info["grasp_distance"]
        if grasp_dist > 1e-6:
            max_pad = grasp_dist * 0.3  # pads take at most 30% of grasp gap
            if pad_props["scale"] > max_pad:
                pad_props["scale"] = max_pad

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
        }
        return self

    async def _create_pads_and_fingers(self, grip_info, pad_props, pad_mass, target_asset_path):
        # type: (Dict[str, Any], Dict[str, Any], float, str) -> None
        """Create gripper pads, finger joints, mimic joint, and drive."""
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
        if self._check_pad_overlap(grip_info, pad_props["scale"], target_asset_path):
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

        # Mimic joint: right follows left with -1.0 gearing
        right_prim = stage.GetPrimAtPath(right_joint_path)
        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(right_prim, "rotX")
        mimic.GetReferenceJointRel().AddTarget(left_joint_path)
        mimic.GetGearingAttr().Set(-1.0)
        mimic.GetOffsetAttr().Set(0.0)

        # Configure finger drive
        max_grip_force = pad_props["max_force"]
        stiffness = max(200.0, min(max_grip_force / 0.005, 5000.0))
        damping = max(100.0, min(2.0 * math.sqrt(pad_mass * stiffness), 1000.0))
        max_vel = max(0.01, min(pad_props["max_velocity"], 0.5))
        await self._configure_drive(
            left_joint_path,
            target_position=0.0,
            stiffness=stiffness,
            damping=damping,
            max_force=max_grip_force,
            max_velocity=max_vel,
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
                scale=[pad_props["scale"]] * 3,
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
        return (
            self.get_joint_target(self.JOINT_X),
            self.get_joint_target(self.JOINT_Y),
            self.get_joint_target(self.JOINT_Z),
        )

    def get_gripper_joint_position(self):
        # type: () -> float
        """Return the current finger joint position (left joint).

        Reads from PhysxSchema.JointStateAPI which is applied during
        drive configuration.
        """
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

    def _set_finger_target(self, position):
        # type: (float) -> None
        """Set the left finger joint drive target position."""
        prim = self._stage.GetPrimAtPath(self.LEFT_JOINT)
        if prim and prim.IsValid():
            attr = prim.GetAttribute("drive:linear:physics:targetPosition")
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

    def _compute_pad_properties(self, target_asset_path):
        # type: (str) -> Dict[str, Any]
        """Compute pad scale, mass, friction, force from target object."""
        asset_prim = self._stage.GetPrimAtPath(target_asset_path)
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default"])
        world_bound = bbox_cache.ComputeWorldBound(asset_prim)
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

        total_mass = sum(
            UsdPhysics.MassAPI(p).GetMassAttr().Get() for p in Usd.PrimRange(asset_prim) if p.HasAPI(UsdPhysics.MassAPI)
        )
        if total_mass == 0.0:
            total_mass = 8000.0 * volume

        required_force = total_mass * 9.81 * 5.0
        try:
            max_velocity = min(0.5, 0.1 * float(dimension))
        except Exception:
            max_velocity = 0.1

        return {
            "scale": pad_scale,
            "mass": total_mass,
            "static_friction": 5.0,
            "dynamic_friction": 5.0,
            "max_force": required_force,
            "max_velocity": max_velocity,
        }

    def _check_pad_overlap(self, grip_info, pad_scale, target_asset_path):
        # type: (Dict[str, Any], float, str) -> bool
        """Return True if either pad cube overlaps the target object."""
        extent = carb.Float3(pad_scale / 2, pad_scale / 2, pad_scale / 2)
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
