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
"""Discover and register standalone transformer rules."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil

from simready.asset_transformer import RuleInterface, RuleRegistry

logger = logging.getLogger(__name__)

_EXCLUDED_SUBPACKAGES = frozenset({"tests"})


def discover_rule_classes() -> list[type[RuleInterface]]:
    """Return importable concrete rule classes in deterministic order.

    Specialized robot and conversion rules may depend on optional Isaac
    packages. Missing optional dependencies skip only those rule modules.
    """
    import simready.asset_transformer.rules as rules_package

    package_root = rules_package.__name__
    discovered: dict[str, type[RuleInterface]] = {}
    for module_info in pkgutil.walk_packages(rules_package.__path__, prefix=f"{package_root}."):
        relative_name = module_info.name[len(package_root) + 1 :]
        if relative_name.split(".", 1)[0] in _EXCLUDED_SUBPACKAGES:
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping optional rule module %s: %s", module_info.name, exc)
            continue
        for _, rule_class in inspect.getmembers(module, inspect.isclass):
            if rule_class is RuleInterface or not issubclass(rule_class, RuleInterface):
                continue
            if inspect.isabstract(rule_class) or rule_class.__module__ != module.__name__:
                continue
            fqcn = f"{rule_class.__module__}.{rule_class.__qualname__}"
            discovered[fqcn] = rule_class
    return [discovered[name] for name in sorted(discovered)]


def register_all_rules() -> list[type[RuleInterface]]:
    """Register every currently importable rule and return the registered classes."""
    registry = RuleRegistry()
    rules = discover_rule_classes()
    for rule_class in rules:
        registry.register(rule_class)
    return rules
