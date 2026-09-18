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

"""Load-order regression for runtime-only BA.002 registration.

Isaac Sim ships the real BA.002 checker and may import/register it before this
tier's placeholder. The placeholder must not replace that implementation.

Requires an installed ``simready-foundation-tier-core`` wheel (with generated
requirements) plus ``usd-validation-nvidia`` and ``pxr``.
"""

from __future__ import annotations

import pytest

usd_validation_nvidia = pytest.importorskip("usd_validation_nvidia")
pytest.importorskip("pxr")
pytest.importorskip("simready.foundation.tier_core.requirements")


def _clear_ba002_owner(ba002) -> None:
    registry = usd_validation_nvidia.RequirementsRegistry()
    owner = registry.get_validator(ba002)
    if owner is None:
        return
    usd_validation_nvidia.unregister_requirements(owner)
    try:
        usd_validation_nvidia.unregister_rule(owner)
    except Exception:
        # Category registry may not have the rule if only requirements were mapped.
        pass
    assert not registry.is_implemented(ba002)


def test_isaac_first_keeps_isaac_ba002_checker():
    """If Isaac registers BA.002 first, the tier placeholder must leave it alone."""
    from simready.foundation.tier_core.capabilities.physics_bodies.base_articulation import (
        validation as ba_mod,
    )

    ba002 = ba_mod.cap.BaseArticulationRequirements.BA_002
    _clear_ba002_owner(ba002)

    @usd_validation_nvidia.register_rule("BaseArticulation")
    @usd_validation_nvidia.register_requirements(ba002, override=True)
    class FakeIsaacBA002(usd_validation_nvidia.BaseRuleChecker):
        """Stand-in for isaacsim.asset.validation's real BA.002 checker."""

    registry = usd_validation_nvidia.RequirementsRegistry()
    assert registry.is_implemented(ba002)
    assert registry.get_validator(ba002) is FakeIsaacBA002

    registered = ba_mod.register_ba002_placeholder()

    assert registered is False
    assert registry.get_validator(ba002) is FakeIsaacBA002
    assert registry.get_validator(ba002) is not ba_mod.RuntimeOnlyBA002Registration

    _clear_ba002_owner(ba002)


def test_tier_first_registers_placeholder_when_missing():
    """With no prior BA.002 checker, the placeholder must register itself."""
    from simready.foundation.tier_core.capabilities.physics_bodies.base_articulation import (
        validation as ba_mod,
    )

    ba002 = ba_mod.cap.BaseArticulationRequirements.BA_002
    _clear_ba002_owner(ba002)

    registered = ba_mod.register_ba002_placeholder()

    registry = usd_validation_nvidia.RequirementsRegistry()
    assert registered is True
    assert registry.is_implemented(ba002)
    assert registry.get_validator(ba002) is ba_mod.RuntimeOnlyBA002Registration
    assert ba_mod.RuntimeOnlyBA002Registration not in usd_validation_nvidia.CategoryRuleRegistry().rules

    _clear_ba002_owner(ba002)


def test_isaac_checker_replaces_tier_placeholder():
    """An Isaac checker loaded later must replace the standalone placeholder."""
    from simready.foundation.tier_core.capabilities.physics_bodies.base_articulation import (
        validation as ba_mod,
    )

    ba002 = ba_mod.cap.BaseArticulationRequirements.BA_002
    _clear_ba002_owner(ba002)
    assert ba_mod.register_ba002_placeholder() is True

    @usd_validation_nvidia.register_rule("BaseArticulation")
    @usd_validation_nvidia.register_requirements(ba002, override=True)
    class FakeIsaacBA002(usd_validation_nvidia.BaseRuleChecker):
        """Stand-in for the runtime checker loaded after the core tier."""

    registry = usd_validation_nvidia.RequirementsRegistry()
    assert registry.get_validator(ba002) is FakeIsaacBA002
    assert registry.get_validator(ba002) is not ba_mod.RuntimeOnlyBA002Registration

    _clear_ba002_owner(ba002)
