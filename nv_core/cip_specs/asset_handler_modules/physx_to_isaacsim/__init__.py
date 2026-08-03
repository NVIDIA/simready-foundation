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
"""Feature adapter to convert PhysX robotic assets to Isaac Sim format.

This adapter uses the AssetStructureManager to apply the robot schema
transformation rules to convert assets to the Isaac Sim structure.
"""

import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from isaacsim.asset.transformer import AssetTransformerManager, RuleProfile
from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Kind, Sdf, Usd

logger = logging.getLogger(__name__)

# Path to the profile JSON relative to this module
_PROFILE_JSON_PATH = Path(__file__).parent / "asset" / "transformer" / "data" / "isaacsim_structure.json"

@feature_adapter(
    name="neutral_composition_to_isaacsim",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="0.1.0",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.1.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature.
    """
    convert_to_isaacsim(input_stage, output_stage)

@feature_adapter(
    name="neutral_composition_to_isaacsim_2",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="0.1.0",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.2.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature.
    """
    convert_to_isaacsim(input_stage, output_stage)  

@feature_adapter(
    name="neutral_composition_to_isaacsim_3",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="1.0.1",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.2.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature.
    """
    convert_to_isaacsim(input_stage, output_stage)


def convert_to_isaacsim(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Convert a PhysX robotic asset to Isaac Sim format.

    Uses the AssetTransformerManager to apply robot schema transformation rules.
    The input stage is saved to a temporary file, processed by the manager,
    and the results are copied back to the output stage.

    Args:
        input_stage: The source USD stage containing the PhysX asset.
        output_stage: The destination USD stage for the Isaac Sim asset.

    Raises:
        ValueError: If the input stage has no default prim.
        RuntimeError: If the asset transformation fails.
        FileNotFoundError: If the profile JSON file is not found.
    """

    # Validate input stage has a default prim
    input_default_prim = input_stage.GetDefaultPrim()
    if not input_default_prim:
        raise ValueError("Input stage must have a default prim")

    default_prim_name = input_default_prim.GetName()

    # Determine output paths
    output_layer = output_stage.GetRootLayer()
    output_path = Path(output_layer.identifier)
    input_filename = Path(input_stage.GetRootLayer().identifier)
    package_root = str(output_path.parent)
    asset_name = output_path.stem

    # Validate profile JSON exists
    if not _PROFILE_JSON_PATH.exists():
        raise FileNotFoundError(f"Profile JSON not found: {_PROFILE_JSON_PATH}")

    # Load the profile from JSON
    with open(_PROFILE_JSON_PATH, "r", encoding="utf-8") as f:
        profile = RuleProfile.from_json(f.read())

    # Configure the profile with asset-specific settings
    profile.interface_asset_name = asset_name + ".usd"

    # Create manager (rules already registered in the singleton registry above)
    manager = AssetTransformerManager()

    # Run the transformation
    logger.info(f"Running AssetTransformerManager for asset: {asset_name}")
    # create a temporary directory for the transformed asset at the same level as the output path
    transformed_package_root = output_path.parent.parent / "temp_transformed_asset"
    if transformed_package_root.exists():
        shutil.rmtree(transformed_package_root)
    transformed_package_root.mkdir(parents=True)
    report = manager.run(input_stage=input_stage, profile=profile, package_root=transformed_package_root)

    # Check for errors in rule execution
    for result in report.results:
        if not result.success:
            error_msg = f"Rule '{result.rule.name}' failed: {result.error}"
            logger.error(error_msg)
            raise RuntimeError(f"Asset transformation failed: {result.error}")
        else:
            # Log successful rule operations
            for log_entry in result.log:
                logger.debug(f"[{result.rule.name}] {log_entry.get('message', '')}")

    del manager
    del report

    # asset transformation had a number of issues working "in place", so we output to a new temp
    # directory and then reintegrate the transformed asset into the output stage
    package_dir = Path(package_root)

    if not transformed_package_root.is_dir():
        raise RuntimeError(f"Expected transformed asset directory not found: {transformed_package_root}")

    output_root_layer = output_stage.GetRootLayer()
    if output_root_layer is None:
        raise RuntimeError(f"Failed to get output root layer")

    #
    transformed_root_layer_path = transformed_package_root / (asset_name + ".usd")
    if not transformed_root_layer_path.exists():
        raise RuntimeError(f"Transformed root layer not found at expected location: " f"{transformed_root_layer_path}")

    # delete all folders except the transformed_asset folder and .thumbs
    for entry in list(package_dir.iterdir()):
        if entry.is_dir() and entry.name != ".thumbs":
            shutil.rmtree(entry)

    transformed_layer = Sdf.Layer.FindOrOpen(str(transformed_root_layer_path))
    if transformed_layer is None:
        raise RuntimeError(f"Failed to open transformed root layer: {transformed_root_layer_path}")

    output_root_layer.Clear()
    Sdf.CopySpec(
        transformed_layer,
        Sdf.Path.absoluteRootPath,
        output_root_layer,
        Sdf.Path.absoluteRootPath,
    )
    # ``Sdf.CopySpec`` copies the pseudo-root prim spec but not layer-level
    # metadata. Carry over the fields the downstream pipeline relies on.
    output_root_layer.subLayerPaths = list(transformed_layer.subLayerPaths)
    if transformed_layer.defaultPrim:
        output_root_layer.defaultPrim = transformed_layer.defaultPrim
    if transformed_layer.documentation:
        output_root_layer.documentation = transformed_layer.documentation
    if transformed_layer.customLayerData:
        output_root_layer.customLayerData = dict(transformed_layer.customLayerData)
    output_root_layer.Save()

    # Drop our open reference before mutating the directory so the layer
    # registry doesn't hold a handle to a file we're about to move/remove.
    del transformed_layer

    # Promote the remaining transformer outputs (payloads/, materials/,
    # Textures/, etc.) up one level into package_dir so they sit alongside
    # the input stage's root layer where its sublayer / reference paths
    # expect to find them. Skip the transformed root layer file itself --
    # its contents already live in input_stage's root layer via the
    # ``Sdf.CopySpec`` above, and the destination slot is reserved for the
    # preserved input stage file.
    transformed_root_layer_resolved = transformed_root_layer_path.resolve()
    for entry in list(transformed_package_root.iterdir()):
        if entry.resolve() == transformed_root_layer_resolved:
            continue
        destination = package_dir / entry.name
        shutil.move(str(entry), str(destination))

    shutil.rmtree(transformed_package_root)

    logger.info(f"Successfully converted asset to Isaac Sim format: {asset_name}")
