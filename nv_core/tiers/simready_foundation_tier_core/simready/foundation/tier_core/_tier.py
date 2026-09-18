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

import importlib.metadata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_PKG_ROOT = Path(__file__).resolve().parent
_MODULE = __package__ or _PKG_ROOT.name
_NAME = _MODULE.rsplit(".", 1)[-1]


def _owned_package_directory(package_name: str) -> Path | None:
    """Return a package directory owned by this tier's source/distribution.

    Runtime tests are a top-level package in the same distribution as this
    descriptor. Source checkouts are located by their nearest ``pyproject.toml``;
    installed wheels are resolved from distribution RECORD ownership. This
    avoids both fixed parent-depth assumptions and accidentally advertising a
    similarly named package installed by another tier or legacy distribution.
    """
    package_parts = package_name.split(".")
    for project_root in (_PKG_ROOT, *_PKG_ROOT.parents):
        if not (project_root / "pyproject.toml").is_file():
            continue
        package_path = project_root.joinpath(*package_parts)
        return package_path.resolve() if (package_path / "__init__.py").is_file() else None

    descriptor_record = PurePosixPath(*_MODULE.split("."), "_tier.py")
    package_record = PurePosixPath(*package_parts, "__init__.py")
    top_level_package = _MODULE.partition(".")[0]
    try:
        distribution_names = importlib.metadata.packages_distributions().get(top_level_package, ())
    except (AttributeError, OSError):
        return None

    for distribution_name in distribution_names:
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            continue
        records = set(distribution.files or ())
        if descriptor_record not in records or package_record not in records:
            continue
        if Path(distribution.locate_file(descriptor_record)).resolve() != Path(__file__).resolve():
            continue
        package_path = Path(distribution.locate_file(PurePosixPath(*package_parts)))
        return package_path.resolve() if package_path.is_dir() else None
    return None


_RUNTIME_TESTS_ROOT = _owned_package_directory("simready_benchmark_kit_suite")


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
    runtime_tests_path=_RUNTIME_TESTS_ROOT,
)
