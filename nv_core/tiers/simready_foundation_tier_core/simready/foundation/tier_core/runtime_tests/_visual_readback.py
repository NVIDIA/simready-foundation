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
"""Required visual acceptance configuration; diagnostic presentation is separate."""

import math
from numbers import Real


def validate_visual_config(
    config,
    *,
    fractions=(),
    positive=(),
    nonnegative=(),
    counts=(),
    positive_counts=(),
    minimum_counts=(),
    count_limits=(),
):
    """Reject invalid configured gates before loading or mutating a scene.

    Only quantities defined as pixel/frame fractions use [0,1]. Unbounded
    positive ratios such as color dominance keep their documented domain.
    Defaults and valid explicitly configured zero fractions are unchanged.
    """
    common_positive = ("camera_padding", "asset_load_timeout")
    common_counts = ("settle_frames",)
    rules = {
        **dict.fromkeys(fractions, "fraction"),
        **dict.fromkeys(common_positive + tuple(positive), "positive"),
        **dict.fromkeys(nonnegative, "nonnegative"),
        **dict.fromkeys(common_counts + tuple(counts), "count"),
        **dict.fromkeys(positive_counts, "positive_count"),
    }
    for name, kind in rules.items():
        if name not in config:
            continue
        value = config[name]
        try:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError("requires a finite real number")
            if kind == "fraction" and not 0.0 <= value <= 1.0:
                raise ValueError("requires a fraction in [0,1]")
            if kind in ("positive", "positive_count") and value <= 0:
                raise ValueError("requires a positive value")
            if kind == "nonnegative" and value < 0:
                raise ValueError("requires a nonnegative value")
            if kind in ("count", "positive_count") and (value < 0 or value != math.trunc(value)):
                raise ValueError("requires an integer count")
        except (TypeError, ValueError, OverflowError) as error:
            raise RuntimeError(f"Invalid visual measurement configuration: {name} {error}") from error
    for name, minimum in minimum_counts:
        if config[name] < minimum:
            raise RuntimeError(
                f"Invalid visual measurement configuration: {name} requires at least {minimum} observations"
            )
    for name, capacity_name in count_limits:
        if config[name] > config[capacity_name]:
            raise RuntimeError(f"Invalid visual measurement configuration: {name} cannot exceed {capacity_name}")


def required_visual_fraction(value, label):
    """Require a measured fraction; missing/nonfinite observations are not zeros."""
    try:
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("requires a finite fraction in [0,1]")
        return float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"Required visual measurement {label} is invalid: {error}") from error


def required_object_pixel_count(result, label):
    """Require an actual integer mask size, including a valid measured empty mask."""
    try:
        value = result.object_pixel_count
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(value)
            or value < 0
            or value != math.trunc(value)
        ):
            raise ValueError("requires a finite nonnegative integer count")
        return int(value)
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        raise RuntimeError(f"Required visual measurement {label} object-pixel count is invalid") from error


def qualified_object_ratios(ctx, references, comparisons, *, prefix, ratio_name, kind, **comparison_options):
    """Measure only references with the existing >=100-pixel usable denominator.

    An empty comparison after a usable reference is a real difference, not an
    omitted pair. Callers retain their own full-coverage/allowed-omission policy.
    """
    if len(references) != len(comparisons) or not references:
        raise RuntimeError(f"Required {prefix} capture sequence is unavailable or incomplete")
    ratios, indices, omitted = [], [], []
    for index, (reference, comparison) in enumerate(zip(references, comparisons, strict=True)):
        result = ctx.compare_object_pixels(reference, comparison, **comparison_options)
        if required_object_pixel_count(result, f"{prefix}[{index}]") < 100:
            omitted.append(index)
            continue
        try:
            value = getattr(result, ratio_name)
        except AttributeError as error:
            raise RuntimeError(f"Required visual measurement {prefix}[{index}] {ratio_name} is unavailable") from error
        ratios.append(required_visual_fraction(value, f"{prefix}[{index}] {ratio_name}"))
        indices.append(index)
    ctx.add_metric(f"{prefix}_qualified_{kind}", len(indices))
    ctx.add_metric(f"{prefix}_omitted_{kind}", len(omitted))
    ctx.add_metric(f"{prefix}_omitted_indices", omitted)
    if omitted:
        from simready.foundation.tier_core.runtime_tests._visual_diagnostics import visual_warning

        visual_warning(
            ctx,
            f"{prefix}: {len(omitted)} {kind} have fewer than 100 reference object pixels "
            f"(zero-based indices {omitted}); their ratios are not measured. "
            "This may be an edge-on view or a rendering/framing issue, not an established asset defect.",
        )
    return ratios, indices


def required_boolean_mask(mask, label):
    """Require an observed nonempty-shape boolean image, including valid empty masks."""
    try:
        shape = tuple(mask.shape)
        valid = mask.dtype.kind == "b" and len(shape) == 2 and all(size > 0 for size in shape)
    except Exception as error:
        raise RuntimeError(f"Required {label} image mask is unavailable or invalid") from error
    if not valid:
        raise RuntimeError(f"Required {label} image mask must have a nonempty 2D boolean structure")
    return mask
