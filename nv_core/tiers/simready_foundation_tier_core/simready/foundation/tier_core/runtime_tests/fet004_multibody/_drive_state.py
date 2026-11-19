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
import struct
from numbers import Real

from pxr import Sdf, Usd, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
)

_FIELDS = ("type", "stiffness", "damping", "targetVelocity", "maxForce")


def _property_fields(layer, path):
    spec = layer.GetPropertyAtPath(path)
    return None if spec is None else {name: spec.GetInfo(name) for name in spec.ListInfoKeys()}


def _api_field(layer, path):
    spec = layer.GetPrimAtPath(path)
    return (True, spec.GetInfo("apiSchemas")) if spec is not None and spec.HasInfo("apiSchemas") else (False, None)


def capture_drive_state(stage, path, axis):
    """Capture exact local opinions before any schema or attribute mutation."""
    if axis not in ("angular", "linear"):
        raise RuntimeError("FET004 required scalar drive axis is unsupported")
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        raise RuntimeError("FET004 required scalar drive prim is unavailable")
    target = stage.GetEditTarget()
    layer = target.GetLayer()
    mapped = target.MapToSpecPath(prim.GetPath())
    if not mapped or not mapped.IsAbsolutePath() or not layer.permissionToEdit:
        raise RuntimeError("FET004 scalar drive requires a writable mapped edit target")
    backup = Sdf.Layer.CreateAnonymous("core-drive-undo")
    properties = {}
    for suffix in _FIELDS:
        name = f"drive:{axis}:physics:{suffix}"
        local_path = mapped.AppendProperty(name)
        original = _property_fields(layer, local_path)
        if original is not None:
            Sdf.CreatePrimInLayer(backup, mapped)
            if not Sdf.CopySpec(layer, local_path, backup, local_path):
                raise RuntimeError("FET004 could not capture a required drive opinion")
        properties[name] = {"path": local_path, "original": original, "expected": original, "restored": False}
    parents = []
    ancestor = mapped
    while ancestor != Sdf.Path.absoluteRootPath:
        parents.append((ancestor, layer.GetPrimAtPath(ancestor) is not None))
        ancestor = ancestor.GetParentPath()
    return {
        "stage": stage,
        "target": target,
        "layer": layer,
        "path": str(path),
        "mapped": mapped,
        "axis": axis,
        "backup": backup,
        "properties": properties,
        "api_original": _api_field(layer, mapped),
        "api_expected": _api_field(layer, mapped),
        "api_restored": False,
        "parents": parents,
        "sealed": False,
        "restored": False,
    }


def seal_drive_state(state):
    """Own only the exact post-write state, not another writer's later edits."""
    for item in state["properties"].values():
        item["expected"] = _property_fields(state["layer"], item["path"])
    state["api_expected"] = _api_field(state["layer"], state["mapped"])
    state["sealed"] = True


def _verify_expected(state):
    if _api_field(state["layer"], state["mapped"]) != state["api_expected"]:
        raise RuntimeError("FET004 temporary drive API opinions changed concurrently")
    for item in state["properties"].values():
        if _property_fields(state["layer"], item["path"]) != item["expected"]:
            raise RuntimeError("FET004 temporary drive attribute opinions changed concurrently")


def required_drive_value(api, suffix, value):
    """Require the authored control write and a matching representable readback."""
    if isinstance(value, bool) or not isinstance(value, Real) or math.isnan(value):
        raise RuntimeError("FET004 required drive control must be a real numeric value")
    if suffix != "targetVelocity" and value < 0:
        raise RuntimeError("FET004 required drive damping/force must be nonnegative")
    if not math.isfinite(value) and not (suffix == "maxForce" and value == math.inf):
        raise RuntimeError("FET004 required drive control must be finite")
    creator = {
        "stiffness": api.CreateStiffnessAttr,
        "damping": api.CreateDampingAttr,
        "targetVelocity": api.CreateTargetVelocityAttr,
        "maxForce": api.CreateMaxForceAttr,
    }[suffix]
    attr = creator()
    if not attr or not attr.Set(float(value)):
        raise RuntimeError("FET004 required temporary drive control write was rejected")
    observed = attr.Get()
    if not isinstance(observed, Real) or isinstance(observed, bool):
        raise RuntimeError("FET004 required temporary drive control readback is unavailable")
    try:
        expected = struct.unpack("f", struct.pack("f", float(value)))[0]
    except (OverflowError, struct.error) as error:
        raise RuntimeError(
            "FET004 required drive control cannot be represented by its native float attribute"
        ) from error
    if math.isfinite(value) and (not math.isfinite(expected) or (value != 0 and expected == 0)):
        raise RuntimeError("FET004 required drive control cannot be represented by its native float attribute")
    if observed != expected:
        raise RuntimeError("FET004 required temporary drive control readback disagrees")


def _finish_write(state, operation):
    _verify_expected(state)
    state["sealed"] = False
    try:
        with Usd.EditContext(state["stage"], state["target"]):
            operation()
    except BaseException as primary:
        try:
            seal_drive_state(state)
        except BaseException as secondary:
            note_secondary_error(
                primary, lambda secondary=secondary: f"Drive undo qualification also failed: {secondary}"
            )
        raise
    else:
        seal_drive_state(state)


def activate_drive_state(state, velocity, damping, max_force=None):
    """Apply required velocity-mode controls, retaining partial mutation state."""

    def write():
        prim = state["stage"].GetPrimAtPath(state["path"])
        api = UsdPhysics.DriveAPI.Apply(prim, state["axis"])
        if not api or not prim.HasAPI(UsdPhysics.DriveAPI, state["axis"]):
            raise RuntimeError("FET004 required temporary DriveAPI application failed")
        required_drive_value(api, "stiffness", 0.0)
        required_drive_value(api, "damping", damping)
        required_drive_value(api, "targetVelocity", velocity)
        if max_force is not None:
            required_drive_value(api, "maxForce", max_force)

    _finish_write(state, write)


def update_drive_damping(state, damping):
    def write():
        api = UsdPhysics.DriveAPI(state["stage"].GetPrimAtPath(state["path"]), state["axis"])
        if not api:
            raise RuntimeError("FET004 active scalar drive is unavailable")
        required_drive_value(api, "damping", damping)

    _finish_write(state, write)


def restore_drive_state(state):
    """Undo owned exact local specs; preserve conflicts and allow partial retry."""
    if state["restored"]:
        return
    if not state["sealed"]:
        raise RuntimeError("FET004 partial drive state could not be qualified for required undo")
    errors = []
    with Usd.EditContext(state["stage"], state["target"]):
        for name, item in state["properties"].items():
            if item["restored"]:
                continue
            try:
                current = _property_fields(state["layer"], item["path"])
                if current == item["original"]:
                    item["restored"] = True
                    continue
                if current != item["expected"]:
                    raise RuntimeError("FET004 drive attribute restoration found concurrent opinions")
                if current is not None:
                    prim = state["stage"].GetPrimAtPath(state["path"])
                    if not prim.RemoveProperty(name) or _property_fields(state["layer"], item["path"]) is not None:
                        raise RuntimeError("FET004 required drive property removal failed")
                    item["expected"] = None  # Qualified intermediate state permits a CopySpec retry.
                if item["original"] is not None:
                    Sdf.CreatePrimInLayer(state["layer"], state["mapped"])
                    if not Sdf.CopySpec(state["backup"], item["path"], state["layer"], item["path"]):
                        raise RuntimeError("FET004 required original drive property restoration failed")
                if _property_fields(state["layer"], item["path"]) != item["original"]:
                    raise RuntimeError("FET004 original drive property opinion was not restored")
                item["restored"] = True
            except BaseException as error:
                errors.append(error)
        if not state["api_restored"]:
            try:
                current = _api_field(state["layer"], state["mapped"])
                if current != state["api_original"]:
                    if current != state["api_expected"]:
                        raise RuntimeError("FET004 drive API restoration found concurrent opinions")
                    spec = state["layer"].GetPrimAtPath(state["mapped"])
                    if state["api_original"][0]:
                        spec.SetInfo("apiSchemas", state["api_original"][1])
                    elif spec is not None and spec.HasInfo("apiSchemas"):
                        spec.ClearInfo("apiSchemas")
                    if _api_field(state["layer"], state["mapped"]) != state["api_original"]:
                        raise RuntimeError("FET004 original DriveAPI opinions were not restored")
                state["api_restored"] = True
            except BaseException as error:
                errors.append(error)
    if errors:
        for secondary in errors[1:]:
            note_secondary_error(errors[0], lambda secondary=secondary: f"Another drive undo failed: {secondary}")
        raise errors[0]
    for path, existed in state["parents"]:
        spec = state["layer"].GetPrimAtPath(path)
        if existed or spec is None or spec.properties or spec.nameChildren or spec.ListInfoKeys() != ["specifier"]:
            continue
        if spec.specifier != Sdf.SpecifierOver:
            continue
        edit = Sdf.BatchNamespaceEdit()
        edit.Add(path, Sdf.Path.emptyPath)
        if not state["layer"].Apply(edit) or state["layer"].GetPrimAtPath(path) is not None:
            raise RuntimeError("FET004 required empty drive override cleanup failed")
    state["restored"] = True
