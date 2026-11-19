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
"""An unexcited drive is not a measured response or a passing observation."""

from types import SimpleNamespace

import numpy as np
import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    drive_gain_validation as phase,
)


def test_aggregate_never_counts_unobserved_excitation_as_pass_or_failure():
    result = phase.aggregate_dgv_summary(
        [
            {"name": "observed", "ok": True},
            {"name": "tiny", "ok": None, "evaluated": False},
        ]
    )
    assert result["joints_tested"] == 1
    assert result["joints_passed"] == 1
    assert result["joints_failed"] == 0
    assert result["joints_not_evaluated"] == ["tiny"]


@pytest.mark.asyncio
async def test_actual_runner_reports_execution_gap_when_no_observable_step_is_performed(monkeypatch):
    metrics, skipped, commands = {}, [], []
    robot = SimpleNamespace(
        prim_path="/robot",
        dof_names=["tiny"],
        get_joint_position_limits=lambda: (np.array([0.0]), np.array([1.0])),
        get_joint_positions=lambda: np.array([0.0]),
        set_joint_position_targets=commands.append,
    )

    async def settle(*_args, **_kwargs):
        return None

    monkeypatch.setattr(phase, "settle_nominal", settle)
    monkeypatch.setattr(phase, "owned_articulation", lambda selected, *_args, **_kwargs: selected)
    monkeypatch.setattr(phase, "compute_world_aligned_bbox", lambda *_args: None)
    ctx = SimpleNamespace(
        step=lambda *_: None,
        add_metric=lambda name, value: metrics.update({name: value}),
        skip=skipped.append,
        warn=lambda *_: None,
    )
    config = dict(phase.get_defaults(), step_magnitude_deg=1e-9)
    with pytest.raises(RuntimeError, match="no observable legal excitation"):
        await phase.run_drive_gain_validation(
            ctx,
            robot,
            {
                "passive_joint_indices": [],
                "mimic_follower_indices": [],
                "loop_joint_indices": [],
            },
            config,
        )
    assert skipped == []
    assert commands == []
    assert metrics["dgv_joints_tested"] == 0
    assert metrics["dgv_joints_passed"] == 0
    assert metrics["dgv_joints_failed"] == 0
    assert metrics["dgv_joints_not_evaluated"] == ["tiny"]
