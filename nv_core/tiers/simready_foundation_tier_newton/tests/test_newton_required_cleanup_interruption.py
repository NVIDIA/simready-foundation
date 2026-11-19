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
from simready.foundation.tier_newton.runtime_tests.articulation_phases import _diagnostic_notes
from simready.foundation.tier_newton.runtime_tests.fet004_multibody import joint_movement


@pytest.mark.asyncio
@pytest.mark.parametrize("secondary_type", [RuntimeError, asyncio.CancelledError, KeyboardInterrupt])
@pytest.mark.parametrize("primary_type", [None, RuntimeError, asyncio.CancelledError])
async def test_actual_scalar_cleanup_preserves_primary_without_editing_unqualified_live_graph(
    monkeypatch, secondary_type, primary_type
):
    primary = primary_type("original native readback failed") if primary_type else None
    secondary = secondary_type("cleanup stop interrupted")
    calls = []
    retired = []
    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=retired.append))

    def stop():
        calls.append("stop")
        if len(calls) > 1:
            raise secondary

    def restore(*args):
        calls.append("restore")

    async def trial(*args):
        if primary is not None:
            raise primary
        return "observed", []

    monkeypatch.setattr(joint_movement, "_reset_transforms", lambda *args: None)
    monkeypatch.setattr(joint_movement, "activate_newton_position_drives", lambda *args, **kwargs: {})
    monkeypatch.setattr(joint_movement, "restore_newton_position_drives", restore)
    monkeypatch.setattr(joint_movement, "_run_newton_drive_sim_impl", trial)
    with pytest.raises(type(primary) if primary is not None else secondary_type) as caught:
        await joint_movement._run_newton_drive_sim(
            ctx, None, "asset", [], {}, SimpleNamespace(stop=stop), {}, 1, 1, False, 1
        )
    if primary is not None:
        assert caught.value is primary
    elif not isinstance(secondary, Exception):
        assert caught.value is secondary
    else:
        assert caught.value.__cause__ is secondary
    assert calls == ["stop", "stop"] and retired == ["Required Newton temporary drive cleanup failed."]


def test_owner_local_retirement_diagnostic_cannot_mask_primary():
    primary = RuntimeError("original")

    def broken(reason):
        raise KeyboardInterrupt("optional delivery interrupted")

    ctx = SimpleNamespace(_engine_session=SimpleNamespace(record_required_cleanup_failure=broken))
    _diagnostic_notes.record_required_cleanup_failure(ctx, "Required cleanup failed.", primary)
    assert str(primary) == "original"
