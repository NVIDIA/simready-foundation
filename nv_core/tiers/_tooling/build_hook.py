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
(capabilities + features + profiles + scaffolding, with validators already
importing the tier's own requirements module). The only thing missing from the
committed tree is the generated requirements-enum package, so this hook's sole
job is to generate it from the committed capability markdown into
``_build/python/<module>/requirements``; the tier's ``pyproject.toml``
force-includes that into the wheel.

It reads two keys from its own ``[tool.hatch.build.hooks.custom]`` table:

* ``module`` -- the tier's dotted package (e.g. ``simready.foundation.prop_robotics_neutral``)
* ``reverse_domain`` -- requirement-code namespace (e.g. ``com.nvidia.simready``)

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

        capabilities_root = root / module.replace(".", "/") / "capabilities"
        if not capabilities_root.is_dir():
            raise FileNotFoundError(f"Capabilities tree not found: {capabilities_root}")

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
            capabilities_root=str(capabilities_root),
            destination_dir=str(build_python),
            package_name=requirements_module,
            reverse_domain=reverse_domain,
        ).generate()
