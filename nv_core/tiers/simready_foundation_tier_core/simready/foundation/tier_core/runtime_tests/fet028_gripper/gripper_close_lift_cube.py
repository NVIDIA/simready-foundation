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

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet028_gripper import gripper_close_lift


@test(
    features=[
        {"id": "FET028_Gripper.Isaac.0-1-0", "version": "*"},
    ],
    name="gripper_close_lift_cube",
    description=gripper_close_lift.DESCRIPTION_TEMPLATE.format(
        shape="cube",
        payload_pct=85,
    ),
    expected_video=gripper_close_lift.EXPECTED_VIDEO_TEMPLATE.format(
        shape="cube",
        color="A cyan",
    ),
    version="1.4.9",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=gripper_close_lift._config_defaults_for_shape("cube"),
    max_duration=600,
)
async def test_gripper_close_lift_cube(ctx):
    """Run the configured sequence; default cube mass is 85% of resolved payload."""
    await gripper_close_lift.run(ctx)
