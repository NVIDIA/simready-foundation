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
"""Compatibility helpers for room placement APIs supplied by the engine wheel."""

import inspect


def place_with_minimum_clearance(method, minimum_clearance, **kwargs):
    """Call a room placement method without breaking older engine wheels.

    Returns ``True`` when the engine supports and receives
    ``minimum_clearance``. Older engine wheels are called with their original
    arguments and return ``False`` so the test can report that the improved
    placement was unavailable without aborting the run.
    """
    try:
        parameters = inspect.signature(method).parameters.values()
    except (TypeError, ValueError):
        parameters = ()

    supports_clearance = any(
        parameter.name == "minimum_clearance" or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )
    if supports_clearance:
        method(minimum_clearance=minimum_clearance, **kwargs)
    else:
        method(**kwargs)
    return supports_clearance
