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

import asyncio
from types import SimpleNamespace

import pytest
from simready.foundation.tier_newton.runtime_tests.articulation_phases import (
    _kinematic_bounds as guard,
)


def _raise(error):
    raise error


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_actual_newton_guard_trip_keeps_required_spatial_interruption(secondary_type):
    secondary = secondary_type("optional guard metric interrupted")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(secondary))
    snapshot = SimpleNamespace(min_point=(0, 0, 0), max_point=(1, 1, 1), volume=1)
    current = SimpleNamespace(min_point=(0, 0, 0), max_point=(20, 20, 20), volume=8000)
    reference = guard.SpatialGuardReference(snapshot, 1.0, ctx, "frs")
    with pytest.raises(guard.SpatialGuardInterruption, match="spatial safety guard"):
        guard.check_guard_reference(current, reference, 8.0)


@pytest.mark.parametrize("secondary_type", [asyncio.CancelledError, KeyboardInterrupt])
def test_no_primary_newton_metric_keeps_first_execution_cancellation(secondary_type):
    first = secondary_type("first execution cancellation")
    ctx = SimpleNamespace(add_metric=lambda *args: _raise(first))
    with pytest.raises(secondary_type) as caught:
        guard._guard_metric(ctx, "reference", {}, primary=None)
    assert caught.value is first
