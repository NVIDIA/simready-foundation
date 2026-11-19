# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Offline vocabulary membership for CAP039_ObjectAffordances."""

__all__ = ["ObjectAffordancesCapabilityChecker"]

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Sdf, Usd

_ALLOWED_AFFORDANCES = frozenset(
    {
        "pressable",
        "touch_operable",
        "rotatable",
        "slideable",
        "openable",
        "lockable",
        "accepts_insertion",
        "toggleable",
        "adjustable",
    }
)
_STATE_AFFORDANCES = {
    "open": "openable",
    "closed": "openable",
    "toggled_on": "toggleable",
    "toggled_off": "toggleable",
    "locked": "lockable",
    "unlocked": "lockable",
    "empty": "accepts_insertion",
    "occupied": "accepts_insertion",
    "pressed": "pressable",
    "unpressed": "pressable",
    "touched": "touch_operable",
    "untouched": "touch_operable",
}
_ALLOWED_AFFORDANCE_STATES = frozenset(_STATE_AFFORDANCES)


@usd_validation_nvidia.register_rule("ObjectAffordances")
@usd_validation_nvidia.register_requirements(
    cap.ObjectAffordancesRequirements.AFF_001,
    cap.ObjectAffordancesRequirements.AFF_002,
)
class ObjectAffordancesCapabilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Check membership without inferring mechanisms or requiring paired labels."""

    def CheckPrim(self, prim: Usd.Prim):
        if not prim or not prim.IsValid():
            return
        schemas = set(prim.GetAppliedSchemas())
        for taxonomy, allowed, requirement in (
            ("affordance", _ALLOWED_AFFORDANCES, cap.ObjectAffordancesRequirements.AFF_001),
            ("affordance_state", _ALLOWED_AFFORDANCE_STATES, cap.ObjectAffordancesRequirements.AFF_002),
        ):
            if f"SemanticsLabelsAPI:{taxonomy}" not in schemas:
                continue
            attr = prim.GetAttribute(f"semantics:labels:{taxonomy}")
            # Generic structure is validated by the Semantic Labels dependency.
            if not attr or not attr.HasAuthoredValue() or attr.GetTypeName() != Sdf.ValueTypeNames.TokenArray:
                continue
            for time in [Usd.TimeCode.Default(), *(Usd.TimeCode(t) for t in attr.GetTimeSamples())]:
                values = attr.Get(time)
                if not values or isinstance(values, str):
                    continue
                for value in sorted(set(values) - allowed):
                    sample = "default" if time.IsDefault() else str(time.GetValue())
                    self._AddFailedCheck(
                        requirement=requirement,
                        message=(
                            f"{prim.GetPath()} property {attr.GetName()} has disallowed token {value!r} "
                            f"at time {sample}. Allowed values: {', '.join(sorted(allowed))}."
                        ),
                        at=attr,
                    )
