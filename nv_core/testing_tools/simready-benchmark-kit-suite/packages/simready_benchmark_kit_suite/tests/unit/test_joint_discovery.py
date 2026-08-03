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
"""Tests for joint discovery pure-logic helpers."""
from simready_benchmark_kit_suite.fet004_multibody.joint_discovery import (
    compute_test_force,
    sanitize_metric_name,
)


def test_compute_test_force_with_drive():
    """Drive max_force present: apply 1.2x."""
    force = compute_test_force(max_force=100.0, multiplier=1.2, default=5.0, cap=1e7)
    assert abs(force - 120.0) < 0.01


def test_compute_test_force_passive_joint():
    """No drive (max_force=None): use default."""
    force = compute_test_force(max_force=None, multiplier=1.2, default=5.0, cap=1e7)
    assert abs(force - 5.0) < 0.01


def test_compute_test_force_zero_max():
    """max_force=0: use default."""
    force = compute_test_force(max_force=0.0, multiplier=1.2, default=5.0, cap=1e7)
    assert abs(force - 5.0) < 0.01


def test_compute_test_force_capped():
    """Very large max_force: cap to max_test_force_n."""
    force = compute_test_force(max_force=1e12, multiplier=1.2, default=5.0, cap=1e7)
    assert abs(force - 1e7) < 1.0


def test_compute_test_force_inf_capped():
    """Infinite max_force: cap to max_test_force_n."""
    force = compute_test_force(max_force=float("inf"), multiplier=1.2, default=5.0, cap=1e7)
    assert abs(force - 1e7) < 1.0


def test_sanitize_metric_name_simple():
    assert sanitize_metric_name("shoulder_joint") == "shoulder_joint"


def test_sanitize_metric_name_special_chars():
    assert sanitize_metric_name("joint/link.01") == "joint_link_01"


def test_sanitize_metric_name_spaces():
    assert sanitize_metric_name("my joint") == "my_joint"
