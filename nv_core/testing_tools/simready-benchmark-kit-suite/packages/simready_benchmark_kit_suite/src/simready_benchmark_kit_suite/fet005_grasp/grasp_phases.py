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
"""9-phase state machine for grasp-and-lift tests.

Manages the ordered sequence of phases: Stability -> GripperPositioning ->
Grasping -> Lifting -> HoldBeforeShake -> Shake -> HoldAfterShake ->
Opening -> Dropping. Stops at first failure.
"""

from simready_benchmark_kit_suite.fet005_grasp.phase_dropping import DroppingPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_grasping import GraspingPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_gripper_pos import (
    GripperPositioningPhase,
)
from simready_benchmark_kit_suite.fet005_grasp.phase_hold import HoldPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_lifting import LiftingPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_opening import OpeningPhase
from simready_benchmark_kit_suite.fet005_grasp.phase_shake import ShakePhase
from simready_benchmark_kit_suite.fet005_grasp.phase_stability import StabilityPhase


class GraspPhaseManager:
    """Sequential 9-phase state machine for grasp-and-lift."""

    def __init__(self, cfg):
        # type: (Dict[str, Any]) -> None
        self._stability = StabilityPhase(cfg)
        self._gripper_pos = GripperPositioningPhase(cfg)
        self._grasping = GraspingPhase(cfg)
        self._lifting = LiftingPhase(cfg)
        self._hold_before = HoldPhase(cfg, label="HoldBeforeShake")
        self._shake = ShakePhase(cfg)
        self._hold_after = HoldPhase(cfg, label="HoldAfterShake")
        self._opening = OpeningPhase(cfg)
        self._dropping = DroppingPhase(cfg)

        self._phases = [
            self._stability,
            self._gripper_pos,
            self._grasping,
            self._lifting,
            self._hold_before,
            self._shake,
            self._hold_after,
            self._opening,
            self._dropping,
        ]  # type: List[Any]
        self._phase_names = [
            "Stability",
            "GripperPositioning",
            "Grasping",
            "Lifting",
            "HoldBeforeShake",
            "Shake",
            "HoldAfterShake",
            "Opening",
            "Dropping",
        ]
        self._current = 0
        self._final_result = None  # type: Optional[Dict[str, Any]]

    _STABILITY_INDEX = 0
    _GRASPING_INDEX = 2
    _LIFTING_INDEX = 3

    @property
    def current_phase_name(self):
        # type: () -> str
        if self._current < len(self._phase_names):
            return self._phase_names[self._current]
        return "Complete"

    @property
    def tracking_active(self):
        # type: () -> bool
        """True if the gripper should track (re-center over) the grasp line.

        Tracking runs only through Stability and GripperPositioning. It
        STOPS once Grasping begins: while the pads are closing, the gantry
        must hold its xy position and only move the fingers. If it keeps
        re-centering over the object during Grasping, an asymmetric
        first-contact nudge moves the object, the gantry chases it, the
        pads press again -- a positive-feedback loop that pushes a light
        object across the floor instead of grasping it in place.
        """
        return self._current < self._GRASPING_INDEX

    @property
    def stability_complete(self):
        # type: () -> bool
        """True once the Stability phase has finished."""
        return self._current > self._STABILITY_INDEX

    @property
    def capture_active(self):
        # type: () -> bool
        """True when we should capture frames (after Stability)."""
        return self._current > self._STABILITY_INDEX

    def check_frame(self, frame, time, scene, tracker):
        # type: (int, float, Any, AssetPoseTracker) -> Optional[Dict[str, Any]]
        """Run the current phase. Returns result dict when done or failed."""
        if self._final_result is not None:
            return None
        if self._current >= len(self._phases):
            return None

        result = self._phases[self._current].check_frame(frame, time, scene, tracker)
        if result is None:
            return None

        # Phase completed
        if result.get("failed", False):
            self._final_result = result
            return result

        # Phase-transition hooks
        if self._current == 1:
            # After GripperPositioning, reset grasping close target
            self._grasping.reset_close_target()
        elif self._current == 7:
            # After Opening, pass drop_start_z to Dropping
            self._dropping.set_drop_start_z(self._opening.drop_start_z)

        # Advance to next phase
        self._current += 1
        if self._current >= len(self._phases):
            # All phases completed successfully
            self._final_result = {
                "phase_name": "GraspAndLift",
                "frame": frame,
                "time": time,
                "message": "All 9 phases completed successfully",
                "failed": False,
            }
            return self._final_result

        return None  # Continue with next phase
