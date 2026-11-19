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

"""Shared hatch build hook for SimReady validation tiers.

Every tier's ``pyproject.toml`` points at this one file
(``path = "../_tooling/build_hook.py"``); it is not copied per tier.

A tier ships its content committed under ``<tier>/simready/foundation/<tier>/``
(rules_and_reqs + features + profiles + scaffolding, with validators already
importing the tier's own requirements module). The only thing missing from the
committed tree is the generated requirements-enum package, so this hook's sole
job is to generate it from the committed requirement markdown into
``_build/python/<module>/requirements``; the tier's ``pyproject.toml``
force-includes that into the wheel. Dependency notices selected by each tier
are included under ``PACKAGE-LICENSES/`` in the wheel.

An editable install (``pip install -e``, see ``dev_install.py``) additionally
gets that generated package mirrored into the checkout, because a tier's own
package ``__path__`` is the only place its validators can import it from. Any
other build removes that mirror again, so a checkout used for development still
produces a clean wheel. See :meth:`CustomBuildHook._sync_checkout_mirror`.

It reads three keys from its own ``[tool.hatch.build.hooks.custom]`` table:

* ``module`` -- the tier's dotted package (e.g. ``simready.foundation.prop_robotics_neutral``)
* ``reverse_domain`` -- requirement-code namespace (e.g. ``com.nvidia.simready``)
* ``package_licenses`` -- filenames from the repository's ``PACKAGE-LICENSES`` directory

Codegen needs ``usd_profiles_nvidia`` (and ``pxr``), so it runs in the build env.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        module = self.config["module"]
        reverse_domain = self.config["reverse_domain"]
        requirements_module = f"{module}.requirements"

        rules_root = root / module.replace(".", "/") / "rules_and_reqs"
        if not rules_root.is_dir():
            raise FileNotFoundError(f"Rules and requirements tree not found: {rules_root}")

        # Only clear _build/python, the codegen scratch this hook owns.
        build_python = root / "_build" / "python"
        if build_python.exists():
            shutil.rmtree(build_python)
        build_python.mkdir(parents=True, exist_ok=True)

        # Generate the requirements enums from the committed requirement markdown.
        # package_name is the tier's final module so the generated code resolves
        # at the installed location (it's force-included as <module>/requirements).
        from usd_profiles_nvidia.codegen import PythonGenerator

        PythonGenerator(
            capabilities_root=str(rules_root),
            destination_dir=str(build_python),
            package_name=requirements_module,
            reverse_domain=reverse_domain,
        ).generate()

        self._sync_checkout_mirror(root, build_python, requirements_module, editable=version == "editable")

        notice_root = root / "PACKAGE-LICENSES"
        if not notice_root.is_dir():
            notice_root = root.parents[2] / "PACKAGE-LICENSES"
        for filename in self.config.get("package_licenses", []):
            if Path(filename).name != filename:
                raise ValueError(f"Invalid package license filename: {filename}")
            notice = notice_root / filename
            if not notice.is_file():
                raise FileNotFoundError(f"Package license not found: {notice}")
            build_data.setdefault("force_include", {})[str(notice)] = f"PACKAGE-LICENSES/{filename}"

    @staticmethod
    def _sync_checkout_mirror(
        root: Path,
        build_python: Path,
        requirements_module: str,
        *,
        editable: bool,
    ) -> None:
        """Maintain the in-checkout copy of the generated requirements package.

        For an **editable** install the copy is created; for any other build it is
        removed. Both directions matter:

        *Created*, because an editable install exposes the tier through a ``.pth``
        entry pointing at this checkout, and the tier is a *regular* package, so
        its ``__path__`` is that single directory. The copy ``force-include``
        places under ``site-packages`` can therefore never be imported -- only the
        namespace ancestors (``simready``, ``simready.foundation``) merge across
        locations, and the search stops at the first real package it finds.
        Mirroring here is what lets each validator's ``import
        <module>.requirements`` resolve in editable mode.

        *Removed*, because the wheel builder ships the committed tree via
        ``packages`` **and** the generated tree via ``force-include``. A mirror
        left behind by an earlier editable install is inside the committed tree,
        so both would contribute the same archive paths and hatchling aborts with
        "A second file is being added to the wheel archive at the same path".
        Ignore rules are not a dependable guard: hatchling resolves VCS ignore
        files relative to the tier directory, so a rule kept at the tiers root
        does not exclude it. Clearing the mirror on every non-editable build makes
        wheel output independent of whatever the checkout was last used for.

        Standard wheel contents are byte-identical with or without an editable
        install having happened first.
        """
        in_tree = root / Path(*requirements_module.split("."))
        if in_tree.exists():
            shutil.rmtree(in_tree)
        if editable:
            shutil.copytree(build_python / Path(*requirements_module.split(".")), in_tree)
