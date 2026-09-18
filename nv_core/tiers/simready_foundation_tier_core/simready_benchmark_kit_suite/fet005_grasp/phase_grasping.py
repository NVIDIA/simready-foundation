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
2. **Settle.** Detect bilateral finger/object stability, freeze the squeeze
   target that produced it, and require an additional continuous observation
   dwell before Lifting starts. Without this, Lifting can begin during the
   first-contact rebound of tightly-sized or round targets.
"""

import math

from simready_benchmark_kit_suite.fet005_grasp.grasp_geometry import (
    contact_preloaded_close_travel,
    pair_closure_reaches_contact,
)
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
        self._close_ramp_speed = float(cfg.get("close_ramp_speed_m_s", 0.04))
        # Post-ramp hold: lets the PD-driven gripper joints physically
        # converge onto the object before we move to Lifting.  0.3s at
        # 240Hz = 72 frames of settle.
        self._settle_duration = float(cfg.get("close_settle_seconds", 0.3))
        self._settle_frames = int(self._settle_duration * self._fps)
        self._convergence_hold_seconds = float(cfg.get("close_convergence_hold_seconds", 0.1))
        self._convergence_hold_frames = max(2, int(self._convergence_hold_seconds * self._fps))
        self._post_stability_seconds = float(cfg.get("post_grasp_stability_seconds", 0.3))
        self._post_stability_frames = max(0, int(self._post_stability_seconds * self._fps))
        self._convergence_tolerance = float(cfg.get("close_convergence_tolerance", 0.0005))
        self._object_settle_tolerance = float(cfg.get("close_object_settle_tolerance", 0.0005))
        self._contact_travel_tolerance = float(cfg.get("close_contact_travel_tolerance", 0.002))
        self._contact_compression = float(cfg.get("grasp_contact_compression", 0.005))
        self._max_settle_seconds = float(cfg.get("close_max_settle_seconds", 2.0))
        self._max_settle_frames = max(self._settle_frames, int(self._max_settle_seconds * self._fps))
        self._pad_tol = float(cfg.get("pad_touching_tolerance", 0.002))
        self._start_frame = None  # type: Optional[int]
        self._settle_start_frame = None  # type: Optional[int]
        self._stable_start_frame = None  # type: Optional[int]
        self._stable_detected_frame = None  # type: Optional[int]
        self._stable_target = None  # type: Optional[float]
        self._close_position = None  # type: Optional[float]
        self._contact_acquired = False
        self._done = False
        self._settle_samples = []  # type: List[Tuple[float, float, Tuple[float, float, float]]]
        # Diagnostic snapshots: object XY at the instant Grasping began,
        # so we can report XY drift during close (slipping / swinging).
        self._obj_start_xyz = None  # type: Optional[tuple]

    def reset_close_target(self):
        # type: () -> None
        """Invalidate cached close position (called after repositioning)."""
        self._close_position = None
        self._contact_acquired = False

    @property
    def tracking_active(self):
        # type: () -> bool
        """Keep following the live grasp line until the closing aperture is reached.

        Before contact, the asset may still settle away from the authored
        world-space line, so freezing the gantry can produce an empty grasp.
        Once the fingers have reached the expected object aperture, continued
        recentering can turn an asymmetric contact into a positive-feedback
        chase that pushes the object across the floor.
        """
        return not self._contact_acquired

    def _sample_settled_grasp(self, robot, tracker, props):
        # type: (Any, AssetPoseTracker, Dict[str, Any]) -> Dict[str, Any]
        """Measure bilateral closure plus finger and object stability."""
        finger_positions = robot.get_finger_joint_positions()
        object_center = tracker.center_history[-1] if tracker.center_history else None
        if object_center is not None:
            self._settle_samples.append(
                (
                    finger_positions[0],
                    finger_positions[1],
                    tuple(float(value) for value in object_center),
                )
            )
        else:
            self._settle_samples.clear()
        if len(self._settle_samples) > self._convergence_hold_frames:
            self._settle_samples.pop(0)

        required_travel = max(
            0.0,
            float(props.get("expected_contact_travel", 0.0)) - self._contact_travel_tolerance,
        )
        object_motion = float("inf")
        fingers_stable = False
        object_stable = False
        if len(self._settle_samples) == self._convergence_hold_frames:
            left_values = [sample[0] for sample in self._settle_samples]
            right_values = [sample[1] for sample in self._settle_samples]
            centers = [sample[2] for sample in self._settle_samples]
            reference_center = centers[-1]
            object_motion = max(math.dist(center, reference_center) for center in centers)
            fingers_stable = (
                max(left_values) - min(left_values) <= self._convergence_tolerance
                and max(right_values) - min(right_values) <= self._convergence_tolerance
            )
            object_stable = object_motion <= self._object_settle_tolerance

        total_travel = abs(finger_positions[0]) + abs(finger_positions[1])
        required_total_travel = 2.0 * required_travel
        aperture_closed = pair_closure_reaches_contact(
            finger_positions[0],
            finger_positions[1],
            props.get("expected_contact_travel", 0.0),
            self._contact_travel_tolerance,
        )
        if aperture_closed:
            self._contact_acquired = True
        return {
            "converged": fingers_stable and object_stable and aperture_closed,
            "finger_positions": finger_positions,
            "required_travel": required_travel,
            "total_travel": total_travel,
            "required_total_travel": required_total_travel,
            "object_motion": object_motion,
        }

    def _finish_success(self, frame, time, robot, tracker, props, sample):
        # type: (int, float, Any, AssetPoseTracker, Dict[str, Any], Dict[str, Any]) -> Dict[str, Any]
        """Finish Grasping immediately once the held object is settled."""
        self._done = True
        finger_positions = sample["finger_positions"]
        joint_pos = finger_positions[0]
        close_target = robot.get_gripper_joint_target()
        close_gap = abs(joint_pos - close_target)
        obj_xy_drift = 0.0
        if self._obj_start_xyz is not None and tracker.center_history:
            end = tracker.center_history[-1]
            dx = end[0] - self._obj_start_xyz[0]
            dy = end[1] - self._obj_start_xyz[1]
            obj_xy_drift = (dx * dx + dy * dy) ** 0.5

        return {
            "phase_name": "Grasping",
            "frame": frame,
            "time": time,
            "message": (
                "Gripper reached a settled grasp at frame %d "
                "(target=%.4f, left=%.4f, right=%.4f, total_travel=%.4f, "
                "required_total_travel=%.4f, "
                "object_motion=%.6f over %.3fs, obj_xy_drift=%.4f)"
                % (
                    frame,
                    close_target,
                    finger_positions[0],
                    finger_positions[1],
                    sample["total_travel"],
                    sample["required_total_travel"],
                    sample["object_motion"],
                    self._convergence_hold_seconds,
                    obj_xy_drift,
                )
            ),
            "failed": False,
            "gripper_closed_frame": frame,
            "grasp_obj_xy_drift_m": round(obj_xy_drift, 4),
            "grasp_close_gap_m": round(close_gap, 4),
            "grasp_close_joint_position": round(joint_pos, 4),
            "grasp_close_right_position": round(finger_positions[1], 4),
            "grasp_object_settle_motion_m": round(sample["object_motion"], 6),
            "grasp_post_stability_seconds": self._post_stability_seconds,
        }

    def _begin_or_continue_stability_dwell(
        self,
        frame,
        time,
        robot,
        tracker,
        props,
        sample,
    ):
        # type: (int, float, Any, AssetPoseTracker, Dict[str, Any], Dict[str, Any]) -> Optional[Dict[str, Any]]
        """Freeze squeeze at first stability and require a continuous dwell."""
        if self._stable_target is None:
            if not sample["converged"]:
                return None
            self._stable_target = robot.get_gripper_joint_target()
            self._stable_detected_frame = frame
            self._stable_start_frame = frame

        robot.close(self._stable_target)
        if not sample["converged"]:
            self._stable_start_frame = None
        elif self._stable_start_frame is None:
            self._stable_start_frame = frame

        if self._stable_start_frame is not None and frame - self._stable_start_frame >= self._post_stability_frames:
            return self._finish_success(frame, time, robot, tracker, props, sample)

        if self._stable_detected_frame is not None and frame - self._stable_detected_frame >= self._max_settle_frames:
            self._done = True
            return {
                "phase_name": "Grasping",
                "frame": frame,
                "time": time,
                "message": (
                    "Grasping failed: settled grasp did not remain stable "
                    "for %.3fs before lift" % self._post_stability_seconds
                ),
                "failed": True,
            }
        return None

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        if self._done:
            return None

        robot = scene.robot
        props = scene.scene_properties

        # Stability was already detected. Keep the exact squeeze target that
        # produced it instead of continuing to close into the object.
        if self._stable_target is not None:
            robot.close(self._stable_target)
            sample = self._sample_settled_grasp(robot, tracker, props)
            return self._begin_or_continue_stability_dwell(
                frame,
                time,
                robot,
                tracker,
                props,
                sample,
            )

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
            # The projected body AABB is only an estimate of the local cross
            # section at the authored grasp line. Command a small additional
            # closure so a position drive develops holding force when it meets
            # the real collider instead of stopping at a zero-load aperture.
            self._close_position = contact_preloaded_close_travel(
                self._close_position,
                grasp_dist,
                pad_scale,
                self._contact_compression,
            )
        except (KeyError, TypeError):
            if self._close_position is None:
                self._close_position = 0.05

        # Newton's tensor controller does not consistently enforce the PhysX
        # max-joint-velocity attribute. Cap the commanded target ramp directly:
        # fast enough for a practical test, but well below the original
        # 0.167 m/s impact-heavy 0.5-second ramp.
        if self._close_ramp_speed > 1e-9:
            velocity_limited_frames = math.ceil(abs(self._close_position) / self._close_ramp_speed * self._fps)
            self._close_frames = max(self._close_frames, velocity_limited_frames)

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
            sample = self._sample_settled_grasp(robot, tracker, props)
            return self._begin_or_continue_stability_dwell(
                frame,
                time,
                robot,
                tracker,
                props,
                sample,
            )

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
        sample = self._sample_settled_grasp(robot, tracker, props)
        if not sample["converged"]:
            if settle_elapsed < self._max_settle_frames:
                return None
            self._done = True
            left_pos, right_pos = sample["finger_positions"]
            return {
                "phase_name": "Grasping",
                "frame": frame,
                "time": time,
                "message": (
                    "Grasping failed: fingers did not stabilize before lift "
                    "(left=%.6f, right=%.6f, total_travel=%.6f, "
                    "required_total_travel=%.6f, "
                    "object_motion=%.6f, finger_tolerance=%.6f, "
                    "object_tolerance=%.6f over %.3fs)"
                    % (
                        left_pos,
                        right_pos,
                        sample["total_travel"],
                        sample["required_total_travel"],
                        sample["object_motion"],
                        self._convergence_tolerance,
                        self._object_settle_tolerance,
                        self._convergence_hold_seconds,
                    )
                ),
                "failed": True,
                "grasp_close_left_position": round(left_pos, 6),
                "grasp_close_right_position": round(right_pos, 6),
            }

        return self._begin_or_continue_stability_dwell(
            frame,
            time,
            robot,
            tracker,
            props,
            sample,
        )
