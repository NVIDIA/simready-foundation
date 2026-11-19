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
"""Carry source package thumbnails over to the generated interface layer."""

from __future__ import annotations

import os
import shutil

from simready.asset_transformer import RuleConfigurationParam, RuleInterface

_DEFAULT_THUMBNAILS_FOLDER = ".thumbs"


class ThumbnailCopyRule(RuleInterface):
    """Copy ``.thumbs/<size>/<source file>*`` images and rename them for the interface.

    Thumbnails are keyed by the root layer filename, for example
    ``.thumbs/256x256/asset.usd.png``. The transform writes a new interface
    layer (usually ``asset.usda``), so the source thumbnails must be copied
    and renamed to stay discoverable (SR.002).
    """

    def get_configuration_parameters(self) -> list[RuleConfigurationParam]:
        return [
            RuleConfigurationParam(
                name="thumbnails_folder",
                display_name="Thumbnails Folder",
                param_type=str,
                description="Folder beside the root layer that holds per-resolution thumbnails.",
                default_value=_DEFAULT_THUMBNAILS_FOLDER,
            ),
        ]

    def _interface_asset_name(self, input_stage_path: str) -> str:
        interface_asset_name = self.args.get("interface_asset_name")
        if interface_asset_name:
            return os.path.basename(interface_asset_name)
        return os.path.splitext(os.path.basename(input_stage_path))[0] + ".usda"

    def process_rule(self) -> str | None:
        params = self.args.get("params", {}) or {}
        thumbnails_folder = params.get("thumbnails_folder") or _DEFAULT_THUMBNAILS_FOLDER
        input_stage_path = self.args.get("input_stage_path") or ""
        if not input_stage_path:
            self.log_operation("No input stage path; thumbnail copy skipped")
            return None

        source_name = os.path.basename(input_stage_path)
        target_name = self._interface_asset_name(input_stage_path)
        source_root = os.path.join(os.path.dirname(os.path.abspath(input_stage_path)), thumbnails_folder)
        if not os.path.isdir(source_root):
            self.log_operation(f"No source thumbnails folder: {source_root}")
            return None

        copied = 0
        for resolution in sorted(os.listdir(source_root)):
            source_dir = os.path.join(source_root, resolution)
            if not os.path.isdir(source_dir):
                continue
            for filename in sorted(os.listdir(source_dir)):
                suffix = filename[len(source_name) :]
                # Match "asset.usd.png" and "asset.usd_light.png", not "asset.usda.png".
                if not filename.startswith(source_name) or not suffix.startswith((".", "_")):
                    continue
                source_file = os.path.join(source_dir, filename)
                if not os.path.isfile(source_file):
                    continue
                destination_dir = os.path.join(self.package_root, thumbnails_folder, resolution)
                destination_file = os.path.join(destination_dir, target_name + suffix)
                os.makedirs(destination_dir, exist_ok=True)
                # copyfile does not carry a read-only source mode into the package.
                shutil.copyfile(source_file, destination_file)
                copied += 1

        self.log_operation(f"ThumbnailCopyRule copied {copied} thumbnail(s) for {target_name}")
        return None
