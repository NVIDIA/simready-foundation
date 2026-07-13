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

import os
import re
import shutil

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        src_dir = "docs"
        dst_dir = os.path.join("_build", "docs")

        if not os.path.exists(src_dir):
            if not os.path.exists(dst_dir):
                raise ValueError("docs and _build/docs directories do not exist")
            return

        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)

        shutil.copytree(src_dir, dst_dir)

        for root, _, files in os.walk(dst_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)

                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Replace Kit imports with PyPi imports
                    new_content = re.sub(
                        r"\bomni\.asset_validator\.core\b",
                        "omni.asset_validator",
                        content,
                    )
                    new_content = re.sub(
                        r"\bomni\.capabilities\b",
                        "simready.foundation.core.requirements",
                        new_content,
                    )
                    new_content = re.sub(
                        r"\bregisterRule\b",
                        "register_rule",
                        new_content,
                    )

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
