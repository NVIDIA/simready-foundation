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


class MotionObserver:
    """Bridge newer Evaluate recording APIs while supporting older runners.

    Explicit times are nominal step estimates. Omitted times use the Kit
    timeline clock, which is not claimed to be a solver execution clock.
    Duplicate timeline timestamps are omitted, not invented or interpolated.
    """

    def __init__(self, ctx, name, channels, metadata=None, sample_stride=1):
        self.ctx = ctx
        self.history = None
        self.last_time = None
        self.last_capture_time = None
        self.warned = False
        self.sample_stride = max(1, int(sample_stride))
        self.observation_count = 0
        self.last_phase = None
        begin = getattr(ctx, "begin_motion_history", None)
        if callable(begin):
            try:
                self.history = begin(name, channels, metadata=metadata)
            except Exception:
                self._warn()

    def _warn(self):
        if self.history is not None:
            try:
                self.history.mark_partial("observer could not record every observation")
            except Exception:
                pass
        if not self.warned:
            self.ctx.warn("Measured motion evidence is incomplete or unavailable; test criteria are unchanged.")
            self.warned = True

    def sample(self, values, time_s=None, phase=""):
        if self.history is None:
            return
        self.observation_count += 1
        if phase == self.last_phase and (self.observation_count - 1) % self.sample_stride:
            return
        self.last_phase = phase
        try:
            source = "estimated"
            if time_s is None:
                import omni.timeline

                time_s = float(omni.timeline.get_timeline_interface().get_current_time())
                source = "timeline"
            time_s = float(time_s)
            if not math.isfinite(time_s) or (self.last_time is not None and time_s <= self.last_time):
                self._warn()
                return
            values = dict(values)
            for channel, value in values.items():
                if value is None:
                    continue  # Explicitly unavailable/unmeasured, not a fabricated zero.
                try:
                    finite = not isinstance(value, bool) and math.isfinite(float(value))
                except (TypeError, ValueError, OverflowError):
                    finite = False
                if not finite:
                    values[channel] = None
                    self._warn()
            self.history.sample(time_s, values, phase=phase, clock_source=source)
            self.last_time = time_s
        except Exception:
            self._warn()

    def finish(self, reason):
        if self.history is not None:
            try:
                self.history.finish(reason)
            except Exception:
                self._warn()

    def record_capture(self, path):
        """Associate a successful capture with the latest retained observation.

        Rendering can advance time; this deliberately does not claim an exact
        rendered timestamp or a frame index in the encoded video.
        """
        record = getattr(self.history, "record_capture", None)
        if path and callable(record) and self.last_time is not None:
            # Several captures can follow the same retained (stride-sampled)
            # observation. One marker represents that association; duplicate
            # captures are not missing measurements or a clock failure.
            if self.last_capture_time is not None and self.last_time <= self.last_capture_time:
                return
            try:
                record(self.last_time)
                self.last_capture_time = self.last_time
            except Exception:
                self._warn()


def drop_metadata(ctx, physics_fps, capture_fps):
    """Best-effort authored context, not solver contact telemetry or tuning."""
    if not callable(getattr(ctx, "begin_motion_history", None)):
        return {}
    info = {
        "physics_fps": physics_fps,
        "encoded_video_fps": capture_fps,
        "capture_interval_steps": None,
        "capture_time_basis": "successful capture after recorded observation; render ticks and retries may advance scene",
        "meters_per_unit": None,
        "initial_bbox_size_stage_length": None,
        "authored_colliders": [],
        "measured_contact_points": None,
        "contact_telemetry_available": False,
    }
    try:
        if physics_fps is not None and capture_fps is not None:
            info["capture_interval_steps"] = max(1, int(physics_fps) // int(capture_fps))
        import omni.usd
        from pxr import Usd, UsdGeom, UsdPhysics

        stage = omni.usd.get_context().get_stage()
        info["meters_per_unit"] = float(UsdGeom.GetStageMetersPerUnit(stage))
        bounds = ctx.get_asset_bounds()
        info["initial_bbox_size_stage_length"] = [float(bounds.max[i] - bounds.min[i]) for i in range(3)]
        asset_root = stage.GetPrimAtPath("/World/AssetRoot")
        if not asset_root or not asset_root.IsValid():
            raise ValueError("Asset root is unavailable for authored collider context")
        count = 0
        for prim in Usd.PrimRange(asset_root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)):
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            count += 1
            if len(info["authored_colliders"]) >= 8:
                continue
            collision = UsdPhysics.MeshCollisionAPI(prim)
            settings = {"prim_path": str(prim.GetPath())[:256], "approximation": None}
            if collision:
                settings["approximation"] = collision.GetApproximationAttr().Get()
            for key in ("contactOffset", "restOffset"):
                value = prim.GetAttribute("physxCollision:" + key).Get()
                settings[key] = float(value) if value is not None and math.isfinite(float(value)) else None
            info["authored_colliders"].append(settings)
        info["authored_collider_count"] = count
        info["collider_context_omitted"] = max(0, count - len(info["authored_colliders"]))
        info["collision_context_basis"] = (
            "authored USD attributes in the asset subtree, including instance proxies; "
            "not effective cooked geometry or measured contacts"
        )
    except Exception:
        info["context_partial"] = True
        ctx.warn("Drop measurement context is incomplete; test criteria are unchanged.")
    return info


def joint_metadata(stage, root, name, root_path=None):
    """Resolve unique joint identity and authored drive values without guessing."""
    from pxr import UsdGeom, UsdPhysics

    info = {
        "joint_name": name,
        "unit": "unknown_native",
        "unit_basis": "joint identity/type unresolved; native tensor units not inferred",
        "identity_resolved": False,
    }
    from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_identity import (
        joint_for_native_name,
        selected_joint_prims,
    )

    try:
        joints = selected_joint_prims(stage, root_path or str(root.GetPath()), [name], root)
        prim = joint_for_native_name(joints, name)
    except RuntimeError:
        return info
    if prim is None:
        return info
    info.update({"prim_path": str(prim.GetPath()), "identity_resolved": True})
    if prim.IsA(UsdPhysics.RevoluteJoint):
        unit, drive_name = "rad", "angular"
        info["unit_basis"] = "articulation tensor angular positions/velocities use radians/radians per second"
    elif prim.IsA(UsdPhysics.PrismaticJoint):
        unit, drive_name = "unknown_native", "linear"
        info["unit_basis"] = (
            "native linear articulation tensor scale not verified; stage metersPerUnit does not establish tensor units"
        )
    else:
        return info
    info["unit"] = unit
    info["meters_per_unit"] = float(UsdGeom.GetStageMetersPerUnit(stage))
    drive = UsdPhysics.DriveAPI(prim, drive_name)
    authored = {}
    if drive:
        for key, attribute in (
            ("stiffness", drive.GetStiffnessAttr()),
            ("damping", drive.GetDampingAttr()),
            ("max_force", drive.GetMaxForceAttr()),
        ):
            value = attribute.Get()
            authored[key] = float(value) if value is not None and math.isfinite(float(value)) else None
    info["authored_drive"] = authored
    return info
