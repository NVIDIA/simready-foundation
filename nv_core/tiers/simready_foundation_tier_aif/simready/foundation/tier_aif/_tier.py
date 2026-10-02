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

"""Tier descriptor advertised on the ``simready.tier`` entry-point group.

This object is what the ``simready.tier`` entry point resolves to. It exposes
this tier's content as *per-layer sources* so a consumer (the SimReady loader)
can register them through its existing layered, multi-source flow rather than
having the tier self-register. Resolving the descriptor is dependency-light: it
only computes paths and never imports ``pxr`` or the validators.

The tier name and module are derived from this package's own dotted name. The
descriptor structure is reusable across tiers, while optional tier-owned
content such as the Benchmark test package is configured per tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
_MODULE = __package__ or _PKG_ROOT.name
_NAME = _MODULE.rsplit(".", 1)[-1]

# This tier has no bundled Benchmark test package (unlike tier_core's
# simready_benchmark_kit_suite) -- runtime_tests_path stays unset below.


@dataclass(frozen=True)
class TierContent:
    """Per-layer content sources for an installed SimReady tier.

    Attributes:
        name: Short tier name (matches the ``simready.tier`` entry-point name).
        rules_package: Importable package whose import registers this tier's
            rules + requirements (its ``capabilities/__init__.py`` imports every
            validator module). Prefer importing this over path-based codegen for
            an installed wheel, where requirements are already baked.
        requirements_module: The generated requirements-enum module baked into
            the wheel at build time.
        rules_and_requirements_path: Bundled capability/requirement tree
            (capability + requirement markdown + validators), suitable for the
            loader's path-based registration / dev codegen fallback.
        features_path: Bundled directory of feature definition files.
        profiles_path: Bundled directory of profile definition files.
        runtime_tests_path: Optional bundled Benchmark test-package directory.
            Consumers may ignore this field when they do not execute runtime
            tests; resolving the descriptor never imports the test package.
    """

    name: str
    rules_package: str
    requirements_module: str
    rules_and_requirements_path: Path
    features_path: Path
    profiles_path: Path
    runtime_tests_path: Path | None = None


tier = TierContent(
    name=_NAME,
    rules_package=f"{_MODULE}.capabilities",
    requirements_module=f"{_MODULE}.requirements",
    rules_and_requirements_path=_PKG_ROOT / "capabilities",
    features_path=_PKG_ROOT / "features",
    profiles_path=_PKG_ROOT / "profiles",
    runtime_tests_path=None,
)
