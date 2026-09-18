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

"""Engine-independent USD authoring helpers for Newton articulation drives."""


def _drive_dof_for_joint(joint):
    # type: (dict) -> object
    type_name = joint.get("type_name")
    if type_name == "PhysicsRevoluteJoint":
        return "angular"
    if type_name == "PhysicsPrismaticJoint":
        return "linear"
    return None


def activate_newton_position_drives(stage, drive_joints, cfg):
    # type: (object, list, dict) -> dict
    """Author temporary position-drive parameters before Newton compiles USD.

    Isaac Sim 6.0's Newton GPU articulation view cannot safely rewrite gains
    after play (the controller mixes CPU index buffers with CUDA gain buffers).
    Newton does consume gains authored on the USD joints before compilation, so
    stage them here and restore every joint after the run.
    """
    from pxr import UsdPhysics

    activated = {}
    kp_ang = float(cfg.get("newton_drive_stiffness_angular", 1.0e4))
    kp_lin = float(cfg.get("newton_drive_stiffness_linear", 1.0e5))
    kd = float(cfg.get("newton_drive_damping", 5.0e2))
    max_force = float(cfg.get("drive_max_force", 1.0e7))
    for joint in drive_joints:
        dof = _drive_dof_for_joint(joint)
        if dof is None:
            continue
        prim = stage.GetPrimAtPath(joint["prim_path"])
        if not prim or not prim.IsValid():
            continue
        api = UsdPhysics.DriveAPI(prim, dof)
        had_api = bool(api)
        if not had_api:
            api = UsdPhysics.DriveAPI.Apply(prim, dof)
        saved = {"_had_api": had_api, "_dof": dof}
        attrs = {
            "stiffness": api.GetStiffnessAttr(),
            "damping": api.GetDampingAttr(),
            "max_force": api.GetMaxForceAttr(),
            "target_position": api.GetTargetPositionAttr(),
            "target_velocity": api.GetTargetVelocityAttr(),
        }
        for name, attr in attrs.items():
            if attr and attr.HasAuthoredValueOpinion():
                saved[name] = attr.Get()
        api.CreateStiffnessAttr(kp_lin if dof == "linear" else kp_ang)
        api.CreateDampingAttr(kd)
        api.CreateMaxForceAttr(max_force)
        api.CreateTargetPositionAttr(0.0)
        api.CreateTargetVelocityAttr(0.0)
        activated[joint["prim_path"]] = saved
    return activated


def restore_newton_position_drives(stage, activated):
    # type: (object, dict) -> None
    """Restore drive schemas and authored values saved by the activation step."""
    from pxr import UsdPhysics

    for prim_path, saved in activated.items():
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            continue
        dof = saved["_dof"]
        if not saved["_had_api"]:
            prim.RemoveAPI(UsdPhysics.DriveAPI, dof)
            continue
        api = UsdPhysics.DriveAPI(prim, dof)
        attrs = {
            "stiffness": api.GetStiffnessAttr(),
            "damping": api.GetDampingAttr(),
            "max_force": api.GetMaxForceAttr(),
            "target_position": api.GetTargetPositionAttr(),
            "target_velocity": api.GetTargetVelocityAttr(),
        }
        for name, attr in attrs.items():
            if name in saved:
                attr.Set(saved[name])
            else:
                attr.Clear()
