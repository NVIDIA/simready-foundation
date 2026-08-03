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
"""Phase 3: Grasping -- close gripper, detect pad-touching failure.

Two-step flow:

1. **Ramp.** Close the gripper smoothly from fully open to the final
   ``close_position`` over ``close_duration`` seconds, checking each
   frame whether the pads have met each other (empty grasp = fail).
2. **Settle.** Hold the full close command for
   ``close_settle_seconds`` so the joint PD controller can physically
   finish closing onto the object before Lifting starts.  Without this,
   Lifting commands a rise while the gripper is still closing, and the
   object slips out on tightly-sized or round targets.
"""

from simready_benchmark_kit_suite.fet005_grasp.grasp_utils import (
    detect_pads_touching,
)


class GraspingPhase:
    """Close the gripper smoothly, hold for physical convergence, detect failure."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._fps = int(cfg["physics_fps"])
        self._close_duration = float(cfg.get("close_duration", 1.5))
        self._close_frames = int(self._close_duration * self._fps)
        # Post-ramp hold: lets the PD-driven gripper joints physically
        # converge onto the object before we move to Lifting.  0.3s at
        # 240Hz = 72 frames of settle.
        self._settle_duration = float(cfg.get("close_settle_seconds", 0.3))
        self._settle_frames = int(self._settle_duration * self._fps)
        self._pad_tol = float(cfg.get("pad_touching_tolerance", 0.002))
        self._start_frame = None  # type: Optional[int]
        self._settle_start_frame = None  # type: Optional[int]
        self._close_position = None  # type: Optional[float]
        self._done = False
        # Diagnostic snapshots: object XY at the instant Grasping began,
        # so we can report XY drift during close (slipping / swinging).
        self._obj_start_xyz = None  # type: Optional[tuple]

    def reset_close_target(self):
        # type: () -> None
        """Invalidate cached close position (called after repositioning)."""
        self._close_position = None

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        robot = scene.robot
        props = scene.scene_properties

        # Recompute close position every frame (grasp_dist changes with tracking)
        try:
            grasp_dist = props["gripper_position_info"]["grasp_distance"]
            pad_scale = props["gripper_pad_properties"]["scale"]
            pad_to_surf = props.get("pad_to_surface_distance", grasp_dist / 2.0)
            half_grasp = grasp_dist / 2.0
            pad_half = pad_scale / 2.0
            if pad_to_surf < half_grasp:
                self._close_position = pad_to_surf
            else:
                self._close_position = half_grasp - pad_half
        except (KeyError, TypeError):
            if self._close_position is None:
                self._close_position = 0.05

        if self._start_frame is None:
            self._start_frame = frame
            if tracker.center_history:
                self._obj_start_xyz = tracker.center_history[-1]

        elapsed = frame - self._start_frame

        # --- Ramp: command a smoothly increasing close target ---
        if elapsed < self._close_frames:
            progress = elapsed / self._close_frames
            target = -self._close_position * progress
            robot.close(target)

            # Check pads touching (joint positions recorded by sim loop)
            if detect_pads_touching(tracker, props, self._pad_tol):
                self._done = True
                return {
                    "phase_name": "Grasping",
                    "frame": frame,
                    "time": time,
                    "message": "Grasping failed: pads touched (no object)",
                    "failed": True,
                    "pads_touching": True,
                }
            return None

        # --- Settle: hold the full close command and let joints converge ---
        # Issues the final target every frame so the PD controller keeps
        # pulling the gripper against the object.  Also re-checks the
        # pads-touching failure -- an empty grasp may converge during the
        # settle window rather than during the ramp.
        if self._settle_start_frame is None:
            self._settle_start_frame = frame
        robot.close(-self._close_position)

        if detect_pads_touching(tracker, props, self._pad_tol):
            self._done = True
            return {
                "phase_name": "Grasping",
                "frame": frame,
                "time": time,
                "message": "Grasping failed: pads touched (no object)",
                "failed": True,
                "pads_touching": True,
            }

        settle_elapsed = frame - self._settle_start_frame
        if settle_elapsed < self._settle_frames:
            return None  # still settling; keep holding the close command

        # Settle complete -- gripper has had time to physically close.
        self._done = True
        joint_pos = robot.get_gripper_joint_position()

        # Diagnostics: how far did the object drift in XY during close,
        # and how close is the actual gripper joint to the commanded target?
        obj_xy_drift = 0.0
        if self._obj_start_xyz is not None and tracker.center_history:
            end = tracker.center_history[-1]
            dx = end[0] - self._obj_start_xyz[0]
            dy = end[1] - self._obj_start_xyz[1]
            obj_xy_drift = (dx * dx + dy * dy) ** 0.5
        close_target = -self._close_position
        close_gap = abs(joint_pos - close_target)

        return {
            "phase_name": "Grasping",
            "frame": frame,
            "time": time,
            "message": (
                "Gripper closed + settled at frame %d "
                "(close_pos=%.4f, joint_pos=%.4f, settle=%.2fs, "
                "grasp_dist=%.4f, pad_scale=%.4f, obj_xy_drift=%.4f, "
                "close_gap=%.4f)"
                % (
                    frame,
                    self._close_position,
                    joint_pos,
                    self._settle_duration,
                    props.get("gripper_position_info", {}).get("grasp_distance", 0),
                    props.get("gripper_pad_properties", {}).get("scale", 0),
                    obj_xy_drift,
                    close_gap,
                )
            ),
            "failed": False,
            "gripper_closed_frame": frame,
            "grasp_obj_xy_drift_m": round(obj_xy_drift, 4),
            "grasp_close_gap_m": round(close_gap, 4),
            "grasp_close_joint_position": round(joint_pos, 4),
        }
