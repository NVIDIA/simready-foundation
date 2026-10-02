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

from simready_benchmark_kit_suite.placement_compat import place_with_minimum_clearance


def test_passes_clearance_to_current_engine_api():
    calls = []

    def place(height_factor=4.0, minimum_clearance=0.0):
        calls.append((height_factor, minimum_clearance))

    supported = place_with_minimum_clearance(place, 0.2, height_factor=2.0)

    assert supported is True
    assert calls == [(2.0, 0.2)]


def test_falls_back_to_legacy_engine_api():
    calls = []

    def place(height_factor=4.0):
        calls.append(height_factor)

    supported = place_with_minimum_clearance(place, 0.2, height_factor=2.0)

    assert supported is False
    assert calls == [2.0]
