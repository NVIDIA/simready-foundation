# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Every shipped Core checker must initialize through the consumer's factory."""

import inspect
import sys

import pytest
from usd_validation_nvidia import BaseRuleChecker
from usd_validation_nvidia._compliance_checker import ComplianceChecker

import simready.foundation.tier_core.rules_and_reqs  # noqa: F401


def _core_checkers():
    checkers = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith("simready.foundation.tier_core.rules_and_reqs."):
            continue
        for candidate in vars(module).values():
            if (
                inspect.isclass(candidate)
                and candidate is not BaseRuleChecker
                and issubclass(candidate, BaseRuleChecker)
                and candidate.__module__ == name
            ):
                checkers.add(candidate)
    assert checkers, "No installed Core checker classes were discovered"
    return sorted(checkers, key=lambda cls: (cls.__module__, cls.__name__))


@pytest.mark.parametrize("checker_type", _core_checkers(), ids=lambda cls: cls.__name__)
def test_core_checker_initializes_through_engine(checker_type):
    engine = ComplianceChecker()
    engine.AddRule(checker_type)
    assert not engine.issues, [issue.message for issue in engine.issues]
    assert len(engine.rules) == 1
    assert type(engine.rules[0]) is checker_type
