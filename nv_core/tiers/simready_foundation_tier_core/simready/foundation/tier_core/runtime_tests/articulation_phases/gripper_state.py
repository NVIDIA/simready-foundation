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
"""Selected required native-coordinate validation, independent of joint units."""

import math
from numbers import Integral, Real

import numpy as np

# A conservative representational guard for float32 command/tensor coordinates.
# This is not a physical stop, permitted joint-error threshold, or a claim that
# a particular SDK squared operation has been verified. Native units still need
# separate qualification before coordinates can be interpreted physically.
FLOAT32_SAFE_COORDINATE_ABS = math.sqrt(float(np.finfo(np.float32).max))


def validate_selected_native_positions(raw_positions, dof_count, indices):
    """Validate only required coordinates; unrelated telemetry may be unavailable."""
    if raw_positions is None:
        raise ValueError("missing joint positions")
    if isinstance(raw_positions, np.ndarray) and raw_positions.dtype.kind not in "iuf":
        raise ValueError("joint position tensor requires a real numeric i/u/f dtype")
    # Keep list element types: float coercion could accept strings/bools or
    # discard imaginary parts before their invalid selected values are checked.
    positions = (
        np.asarray(raw_positions) if isinstance(raw_positions, np.ndarray) else np.asarray(raw_positions, dtype=object)
    )
    if positions.shape != (dof_count,):
        raise ValueError("incomplete joint position buffer")
    if not indices or any(
        isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral) or not 0 <= index < dof_count
        for index in indices
    ):
        raise ValueError("invalid selected grasp DOF indices")
    if len(set(indices)) != len(indices):
        raise ValueError("duplicate selected grasp DOF indices")
    selected = positions[list(indices)]
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) for value in selected):
        raise ValueError("selected native positions must contain real numeric values")
    selected = np.asarray(selected, dtype=np.float64)
    if not np.isfinite(selected).all():
        raise ValueError("non-finite selected native positions")
    if np.any(np.abs(selected) > FLOAT32_SAFE_COORDINATE_ABS):
        raise ValueError("selected native positions exceed the conservative float32 representational safety envelope")
    return selected.tolist()
