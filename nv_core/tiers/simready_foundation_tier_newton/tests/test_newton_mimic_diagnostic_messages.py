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

from types import SimpleNamespace

from simready.foundation.tier_newton.runtime_tests.articulation_phases import mimic_joint


def test_newton_mimic_messages_preserve_backend_and_setup_triage():
    pair = SimpleNamespace(
        follower_joint_path="/Robot/follower",
        reference_joint_path="/Robot/reference",
        follower_dof_index=None,
        reference_dof_index=0,
        backend="newton",
    )
    messages = [
        mimic_joint._msg_no_mimic_authored("newton"),
        mimic_joint._msg_no_mimic_authored("physx"),
        mimic_joint._msg_unresolvable_pairs(2, 1, pair),
        mimic_joint._msg_all_pairs_unresolvable(1, pair),
        mimic_joint._msg_drift_fix_hint(),
        mimic_joint._msg_direction_mismatch("follower", "reference", 1.0, 1.0),
    ]
    for message in messages:
        assert "NEWTON.DJ.003" in message
        assert "PhysxMimicJointAPI" not in message
        assert "physxMimicJoint:" not in message
        assert "Paste-ready" not in message
        assert "Asset fix" not in message
        assert "tier_core" not in message
        assert "Robotiq/ezu_35" not in message
    assert "/Robot/follower" in messages[2] and "/Robot/reference" in messages[2]
    assert "importer/solver support or test setup" in messages[2]
    assert "not failed" in messages[0]


def test_newton_missing_limits_are_a_test_prerequisite_not_an_invented_contract():
    message = mimic_joint._msg_reference_no_limits("reference", "follower", float("inf"), 1.0)
    assert "test prerequisite" in message and "not itself a NEWTON.DJ.003 conformance rule" in message
    assert "degrees for revolute" in message and "stage units" in message
    assert "runtime tensor units require their own qualified basis" in message
    assert "Do not invent limits" in message
    assert "meters for prismatic" not in message
    assert "requires both" not in message
