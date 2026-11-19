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
"""Bounded explicit hand trial controls; no scene access or physics writes."""

import math
from numbers import Integral, Real

from simready.foundation.tier_core.runtime_tests.articulation_phases.gripper_state import (
    FLOAT32_SAFE_COORDINATE_ABS,
)

MAX_HAND_JOINTS = 64
MAX_CLOSE_STEPS = 10000
_SPAN_EPS = 1e-9
_KEYS = {
    "joints",
    "close_delay_steps",
    "approach_pitch_deg",
    "grasp_center_base_m",
    "object_offset_world_xy_m",
    "descent_reference",
}


def _finite(value, description):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError(f"hand trial {description} must be a finite number")
    return float(value)


def _mapping(value, description):
    if not isinstance(value, dict) or len(value) > MAX_HAND_JOINTS:
        raise ValueError(f"hand trial {description} must be a mapping of at most {MAX_HAND_JOINTS} joints")
    for name in value:
        if not isinstance(name, str) or not name or len(name) > 256 or "\0" in name:
            raise ValueError(f"hand trial {description} contains an invalid joint name")
    return value


def _vector(value, size, description):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f"hand trial {description} requires {size} finite metre values")
    return [_finite(item, description) for item in value]


def normalize_hand_trial_controls(raw):
    """Validate the optional serialized configuration, without filling defaults.

    Empty configuration remains empty, so existing automatic motion is unchanged.
    Angular targets are only quantities here; joint identity is checked separately.
    """
    if not isinstance(raw, dict) or set(raw) - _KEYS:
        raise ValueError("hand_trial_controls must be a mapping with known control keys")
    result = {}
    if "joints" in raw:
        joints = _mapping(raw["joints"], "joints")
        if joints:
            result["joints"] = {}
        for name, record in joints.items():
            if not isinstance(record, dict) or set(record) not in ({"hold_rad"}, {"open_rad", "closed_rad"}):
                raise ValueError("hand trial joint records require hold_rad or both open_rad and closed_rad")
            result["joints"][name] = {key: _finite(value, key) for key, value in record.items()}
    if "close_delay_steps" in raw:
        delays = _mapping(raw["close_delay_steps"], "close delays")
        if delays:
            result["close_delay_steps"] = {}
        for name, value in delays.items():
            if isinstance(value, bool) or not isinstance(value, Integral) or not 0 <= value <= MAX_CLOSE_STEPS:
                raise ValueError(f"hand trial close delays require integers in [0, {MAX_CLOSE_STEPS}]")
            result["close_delay_steps"][name] = int(value)
    if "approach_pitch_deg" in raw:
        pitch = _finite(raw["approach_pitch_deg"], "approach pitch")
        if not 0 <= pitch <= 90:
            raise ValueError("hand trial approach pitch must be in [0, 90] degrees")
        result["approach_pitch_deg"] = pitch
    for key, size in (("grasp_center_base_m", 3), ("object_offset_world_xy_m", 2)):
        if key in raw:
            result[key] = _vector(raw[key], size, key)
    if "descent_reference" in raw:
        reference = raw["descent_reference"]
        if reference not in ("fingertips", "grasp_center"):
            raise ValueError("hand trial descent_reference must be fingertips or grasp_center")
        if reference == "grasp_center" and "grasp_center_base_m" not in raw:
            raise ValueError("hand trial grasp_center descent requires grasp_center_base_m")
        result["descent_reference"] = reference
    return result


def resolve_hand_trial_specs(specs, controls, eligible, limits):
    """Apply complete explicit poses to independently owned angular actuators.

    ``eligible`` maps unique joint names to current index/unit/identity metadata.
    An ambiguous geometric role may be resolved explicitly, but the caller must
    still complete the existing live probe and command-restoration safeguards.
    """
    overrides = controls.get("joints", {})
    if not overrides:
        return [dict(spec) for spec in specs]
    if len(eligible) > MAX_HAND_JOINTS:
        raise ValueError("hand trial has too many independently driven joints")
    lower, upper = limits
    if len(lower) != len(upper):
        raise ValueError("hand trial complete joint limits are unavailable")
    by_name = {spec["name"]: dict(spec) for spec in specs}
    if len(by_name) != len(specs):
        raise ValueError("hand trial inferred joint names are ambiguous")
    for name, record in overrides.items():
        identity = eligible.get(name)
        if identity is None or identity.get("unit") != "rad" or not identity.get("identity_resolved"):
            raise ValueError(f"hand trial {name!r} must be a uniquely resolved independently driven angular joint")
        index = identity["idx"]
        if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < len(lower):
            raise ValueError("hand trial selected joint index is invalid")
        lo, hi = _finite(lower[index], "lower limit"), _finite(upper[index], "upper limit")
        if lo > hi:
            raise ValueError("hand trial joint limits are unordered")
        opened = record.get("hold_rad", record.get("open_rad"))
        closed = record.get("hold_rad", record.get("closed_rad"))
        if not lo <= opened <= hi or not lo <= closed <= hi:
            raise ValueError(f"hand trial targets for {name!r} exceed authored limits")
        if max(abs(opened), abs(closed)) > FLOAT32_SAFE_COORDINATE_ABS:
            raise ValueError("hand trial targets exceed the conservative float32 representational safety envelope")
        edited = dict(by_name.get(name, {}), idx=int(index), name=name, open=opened, closed=closed)
        edited["contact_active"] = abs(closed - opened) > _SPAN_EPS
        by_name[name] = edited
    # Keep existing sparse-command order; newly explicit eligible joints append.
    return list(by_name.values())


def validate_close_delays(controls, specs, total_steps, ramp_steps):
    """A delayed ramp must finish inside the existing close step budget."""
    delays = controls.get("close_delay_steps", {})
    if not controls:
        return {}
    if (
        isinstance(total_steps, bool)
        or isinstance(ramp_steps, bool)
        or not isinstance(total_steps, Integral)
        or not isinstance(ramp_steps, Integral)
        or not 1 <= total_steps <= MAX_CLOSE_STEPS
        or not 1 <= ramp_steps <= total_steps
    ):
        raise ValueError("hand trial close step budget is invalid or exceeds its bound")
    moving = {spec["name"] for spec in specs if abs(float(spec["closed"]) - float(spec["open"])) > _SPAN_EPS}
    if set(delays) - moving:
        raise ValueError("hand trial delayed joints must be resolved closing joints")
    if max(delays.values(), default=0) + ramp_steps > total_steps:
        raise ValueError("hand trial delayed ramps exceed close_steps; increase the bounded close budget")
    return dict(delays)


def delayed_close_targets(starts, specs, step, ramp_steps, delays):
    """Signed smooth ramps; delayed joints hold their measured starting pose."""
    if len(starts) != len(specs):
        raise ValueError("hand trial starts must match resolved grasp targets")
    targets = []
    for start, spec in zip(starts, specs, strict=True):
        elapsed = step - delays.get(spec["name"], 0)
        fraction = min(1.0, max(0.0, elapsed / ramp_steps))
        eased = fraction * fraction * (3.0 - 2.0 * fraction)
        targets.append(start + (float(spec["closed"]) - start) * eased)
    return targets


def effective_trial_controls(
    shape, controls, specs, identities, config, object_size_m, object_mass_kg, max_opening_m, procedure_defaults=None
):
    """Serializable resolved controls; native joint units are never guessed."""
    default_fraction = 0.5 if shape == "sphere" else 0.85
    mass_override = config.get("tested_mass_kg_override")
    configured = bool(controls) or (mass_override is not None and float(mass_override) > 0)
    configured = configured or float(config["object_size_fraction"]) != 0.7
    configured = configured or float(config["payload_mass_fraction"]) != default_fraction
    procedure_settings = {}
    if procedure_defaults is not None:
        excluded = {
            "hand_trial_controls",
            "diagnostic_native_contact_pairs",
            "shapes",
            "camera_side_sign",
            "camera_elevation",
            "camera_margin_factor",
            "video_fps_max",
            "close_log_every",
        }
        defaults = dict(procedure_defaults, payload_mass_fraction=default_fraction)
        defaults.update(physics_fps=240.0, carrier_merge_rail=True, detect_limit_inset_frac=0.05)
        for key, default in defaults.items():
            if key in excluded:
                continue
            value = config.get(key, default)
            procedure_settings[key] = value
            configured = configured or value != default
    joints = []
    for spec in specs[:MAX_HAND_JOINTS]:
        identity = identities.get(spec["name"], {})
        joints.append(
            {
                "name": spec["name"],
                "dof_index": int(spec["idx"]),
                "role": "closure" if abs(float(spec["closed"]) - float(spec["open"])) > _SPAN_EPS else "held",
                "open_target": float(spec["open"]),
                "closed_target": float(spec["closed"]),
                "close_delay_steps": controls.get("close_delay_steps", {}).get(spec["name"], 0),
                "unit": identity.get("unit", "unknown_native"),
                "identity_resolved": bool(identity.get("identity_resolved", False)),
            }
        )
    return {
        "schema_version": 1,
        "shape": shape,
        "configured_trial": bool(configured),
        "object_size_m": float(object_size_m),
        "object_mass_kg": float(object_mass_kg),
        "max_opening_m": float(max_opening_m),
        "hand_controls": controls,
        "procedure_settings": procedure_settings,
        "joints": joints,
        "joints_omitted": max(0, len(specs) - MAX_HAND_JOINTS),
        "object_offset_world_xy_m": controls.get("object_offset_world_xy_m", [0.0, 0.0]),
        "grasp_center_base_m": controls.get("grasp_center_base_m"),
        "approach_pitch_deg": controls.get("approach_pitch_deg"),
        "descent_reference": controls.get("descent_reference", "fingertips"),
    }
