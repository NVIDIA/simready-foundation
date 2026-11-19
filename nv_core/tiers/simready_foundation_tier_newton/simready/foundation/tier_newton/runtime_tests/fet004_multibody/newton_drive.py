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

import math
import struct
import sys
from numbers import Real

from simready.foundation.tier_newton.runtime_tests.articulation_phases._diagnostic_notes import (
    note_secondary_error,
    record_required_cleanup_failure,
)

_DRIVE_ATTRIBUTES = {
    "stiffness": "Stiffness",
    "damping": "Damping",
    "max_force": "MaxForce",
    "target_position": "TargetPosition",
    "target_velocity": "TargetVelocity",
}


def _retire(ctx, primary):
    # Latch before optional reporting, including cancellation and old callers.
    sys._simready_evaluate_kit_engine_retired = True
    record_required_cleanup_failure(ctx, "Required Newton temporary drive cleanup failed.", primary)


def _fields(spec):
    return {name: spec.GetInfo(name) for name in spec.ListInfoKeys()} if spec else None


def _metadata(layer, path):
    spec = layer.GetPrimAtPath(path)
    return spec.GetInfo("apiSchemas") if spec and spec.HasInfo("apiSchemas") else None


def _setting(value, name, unlimited=False):
    """Preserve representable commands; do not fabricate invalid numeric input."""
    try:
        valid = not isinstance(value, bool) and isinstance(value, Real)
        if not valid or (not math.isfinite(value) and not (unlimited and value == math.inf)):
            raise ValueError("requires a real float32 value")
        if value < 0:
            raise ValueError("requires a nonnegative drive gain or force ceiling")
        converted = struct.unpack("f", struct.pack("f", value))[0]
        if math.isfinite(value) and not math.isfinite(converted):
            raise ValueError("exceeds native float32 range")
        if value != 0 and converted == 0:
            raise ValueError("nonzero value underflows native float32")
        return converted
    except (TypeError, ValueError, OverflowError, struct.error) as error:
        raise RuntimeError(f"Invalid Newton temporary drive setting {name}: {error}") from error


def _snapshot(stage, prim, dof):
    from pxr import Sdf, UsdPhysics

    target = stage.GetEditTarget()
    path = prim.GetPath()
    layer = target.GetLayer()
    if target.MapToSpecPath(path) != path or not layer.permissionToEdit:
        raise RuntimeError("Newton temporary drives require a writable unmapped local edit target")
    api = UsdPhysics.DriveAPI(prim, dof)
    saved = {"_had_api": bool(api), "_dof": dof}
    attrs = {name: getattr(api, "Get" + suffix + "Attr")() for name, suffix in _DRIVE_ATTRIBUTES.items()}
    backup = Sdf.Layer.CreateAnonymous("newton-drive-undo")
    Sdf.CreatePrimInLayer(backup, path)
    properties = {}
    for name, attr in attrs.items():
        if attr and attr.HasAuthoredValueOpinion():
            saved[name] = attr.Get()  # Legacy inventory, never restoration authority.
        property_path = path.AppendProperty(f"drive:{dof}:physics:{_attribute_suffix(name)}")
        original = layer.GetAttributeAtPath(property_path)
        properties[str(property_path)] = _fields(original)
        if original and not Sdf.CopySpec(layer, property_path, backup, property_path):
            raise RuntimeError("Cannot snapshot Newton temporary drive attribute")
    saved["_undo"] = {
        "stage": stage,
        "layer": layer,
        "path": path,
        "backup": backup,
        "metadata": _metadata(layer, path),
        "properties": properties,
        "sealed": False,
        "restored": False,
        "parents": {str(parent): bool(layer.GetPrimAtPath(parent)) for parent in path.GetPrefixes()},
    }
    return saved


def _attribute_suffix(name):
    return {"max_force": "maxForce", "target_position": "targetPosition", "target_velocity": "targetVelocity"}.get(
        name, name
    )


def _seal(saved):
    state = saved["_undo"]
    state["sealed"] = False
    expected = {path: _fields(state["layer"].GetAttributeAtPath(path)) for path in state["properties"]}
    metadata = _metadata(state["layer"], state["path"])
    state["expected"] = expected
    state["expected_metadata"] = metadata
    state["sealed"] = True


def _restore(stage, saved):
    from pxr import Sdf

    state = saved["_undo"]
    if state["stage"] != stage:
        raise RuntimeError("Newton drive undo belongs to a different stage")
    if state["restored"]:
        return
    if not state["sealed"]:
        raise RuntimeError("Newton drive undo ownership was not sealed")
    layer = state["layer"]
    spec = layer.GetPrimAtPath(state["path"])
    if not spec:
        raise RuntimeError("Newton drive owner prim disappeared; restoration is unqualified")
    changes = {
        path: old
        for path, old in state["properties"].items()
        if state["expected"][path] != old and _fields(layer.GetAttributeAtPath(path)) != old
    }
    for path in changes:
        if _fields(layer.GetAttributeAtPath(path)) != state["expected"][path]:
            raise RuntimeError(f"Newton drive attribute changed concurrently; preserved: {path}")
    metadata_changed = (
        state["metadata"] != state["expected_metadata"] and _metadata(layer, state["path"]) != state["metadata"]
    )
    if metadata_changed and _metadata(layer, state["path"]) != state["expected_metadata"]:
        raise RuntimeError("Newton drive API metadata changed concurrently; preserved")
    for path, old in changes.items():
        prop = layer.GetAttributeAtPath(path)
        if prop:
            if spec.RemoveProperty(prop) is False or layer.GetAttributeAtPath(path):
                raise RuntimeError("Newton temporary drive attribute removal was not acknowledged")
            state["expected"][path] = None  # Proven intermediate state for a safe restore retry.
        if old is not None and not Sdf.CopySpec(state["backup"], path, layer, path):
            raise RuntimeError("Cannot restore Newton temporary drive attribute")
        if _fields(layer.GetAttributeAtPath(path)) != old:
            raise RuntimeError("Newton temporary drive attribute restoration was not acknowledged")
    if metadata_changed:
        if state["metadata"] is None:
            acknowledgement = spec.ClearInfo("apiSchemas")
        else:
            acknowledgement = spec.SetInfo("apiSchemas", state["metadata"])
        if acknowledgement is False or _metadata(layer, state["path"]) != state["metadata"]:
            raise RuntimeError("Newton temporary drive API restoration was not acknowledged")
    for path, existed in sorted(state["parents"].items(), key=lambda item: item[0].count("/"), reverse=True):
        parent = layer.GetPrimAtPath(path)
        if (
            not existed
            and parent
            and parent.specifier == Sdf.SpecifierOver
            and not parent.properties
            and not parent.nameChildren
            and set(parent.ListInfoKeys()) <= {"specifier"}
        ):
            del (parent.nameParent or layer.pseudoRoot).nameChildren[parent.name]
    state["restored"] = True


def _drive_dof_for_joint(joint):
    # type: (dict) -> object
    type_name = joint.get("type_name")
    if type_name == "PhysicsRevoluteJoint":
        return "angular"
    if type_name == "PhysicsPrismaticJoint":
        return "linear"
    return None


def activate_newton_position_drives(stage, drive_joints, cfg, ctx=None):
    # type: (object, list, dict) -> dict
    """Author temporary position-drive parameters before Newton compiles USD.

    Isaac Sim 6.0's Newton GPU articulation view cannot safely rewrite gains
    after play (the controller mixes CPU index buffers with CUDA gain buffers).
    Newton does consume gains authored on the USD joints before compilation, so
    stage them here and restore every changed local opinion after the run.
    The caller must qualify stopped physics before activation/restoration.
    Partial activation is transactional; rollback never guesses ownership.
    """
    from pxr import UsdPhysics

    kp_ang = _setting(cfg.get("newton_drive_stiffness_angular", 1.0e4), "angular stiffness")
    kp_lin = _setting(cfg.get("newton_drive_stiffness_linear", 1.0e5), "linear stiffness")
    kd = _setting(cfg.get("newton_drive_damping", 5.0e2), "damping")
    max_force = _setting(cfg.get("drive_max_force", 1.0e7), "max_force", unlimited=True)
    activated = {}
    try:
        for joint in drive_joints:
            dof = _drive_dof_for_joint(joint)
            if dof is None:
                continue
            prim = stage.GetPrimAtPath(joint["prim_path"])
            if not prim or not prim.IsValid():
                raise RuntimeError("Newton temporary drive joint is unavailable")
            if joint["prim_path"] in activated:
                raise RuntimeError("Duplicate Newton temporary drive owner")
            saved = _snapshot(stage, prim, dof)
            activated[joint["prim_path"]] = saved  # Register undo before first write.
            api = UsdPhysics.DriveAPI.Apply(prim, dof)
            if not api or not prim.HasAPI(UsdPhysics.DriveAPI, dof):
                raise RuntimeError("Newton temporary DriveAPI application was not acknowledged")
            values = {
                "stiffness": kp_lin if dof == "linear" else kp_ang,
                "damping": kd,
                "max_force": max_force,
                "target_position": 0.0,
                "target_velocity": 0.0,
            }
            for name, value in values.items():
                attr = getattr(api, "Create" + _DRIVE_ATTRIBUTES[name] + "Attr")()
                if not attr or attr.Set(value) is False or attr.Get() != value:
                    raise RuntimeError(f"Newton temporary drive write was not acknowledged: {name}")
                local = saved["_undo"]["layer"].GetAttributeAtPath(attr.GetPath())
                if not local or not local.HasInfo("default") or local.GetInfo("default") != value:
                    raise RuntimeError(f"Newton temporary drive local opinion was not acknowledged: {name}")
            _seal(saved)
        return activated
    except BaseException as primary:
        for saved in activated.values():
            try:
                _seal(saved)  # Qualify the actual partial writes before rollback.
            except BaseException as error:
                _retire(ctx, primary)
                note_secondary_error(primary, lambda error=error: f"Newton drive rollback sealing also failed: {error}")
        try:
            restore_newton_position_drives(stage, activated, ctx=ctx)
        except BaseException as error:
            note_secondary_error(primary, lambda error=error: f"Newton drive rollback also failed: {error}")
        raise


def restore_newton_position_drives(stage, activated, ctx=None):
    # type: (object, dict) -> None
    """Restore exact owned local opinions; call only after qualified stop."""
    primary = None
    for saved in reversed(list(activated.values())):
        try:
            _restore(stage, saved)
        except BaseException as error:
            _retire(ctx, primary or error)
            if primary is None:
                primary = error
            else:
                note_secondary_error(primary, lambda error=error: f"Another Newton drive restore failed: {error}")
    if primary is not None:
        raise primary
