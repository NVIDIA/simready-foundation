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

from simready_benchmark.core.decorator import test
from simready_benchmark_kit_suite.fet028_gripper import gripper_close_lift


@test(
    features=[{"id": "FET_028_ISAAC", "version": ">=0.1.0"}],
    name="gripper_close_lift_cube",
    description=gripper_close_lift.DESCRIPTION_TEMPLATE.format(
        shape="cube",
        payload_pct=85,
    ),
    expected_video=gripper_close_lift.EXPECTED_VIDEO_TEMPLATE.format(
        shape="cube",
        color="A cyan",
    ),
    version="1.4.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=gripper_close_lift._config_defaults_for_shape("cube"),
    max_duration=300,
)
async def test_gripper_close_lift_cube(ctx):
    """Run the close-lift-shake-drop sequence on an 85% payload cube."""
    await gripper_close_lift.run(ctx)
