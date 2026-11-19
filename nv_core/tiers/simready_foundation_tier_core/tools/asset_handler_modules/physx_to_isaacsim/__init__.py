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
"""Kit-free adapters that add Isaac Sim composition to props and robots."""

import logging
import shutil
from pathlib import Path

from pxr import Kind, Usd

from .. import feature_adapter
from .materialize import materialize_stage, stage_source_path
from .promotion import promote_transformed_package, raise_on_rule_failure

logger = logging.getLogger(__name__)

# SimReady profiles used by the standalone public transformer.
_SIMREADY_PROP_TRANSFORM = "simready_physx_to_isaac_prop"
_SIMREADY_ROBOT_TRANSFORM = "simready_physx_to_isaac_robot"


@feature_adapter(
    name="minimal_to_isaac_prop_standalone",
    input_feature_id="FET001_MinimalPlaceableVisual.1-0-1",
    output_feature_id="CAP100_IsaacComposition.Isaac.0-4-0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_isaac_prop(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Add the FET_100_ISAAC@0.4.0 feature using the standalone prop transform."""
    convert_to_isaacsim_prop(input_stage, output_stage)


@feature_adapter(
    name="minimal_to_isaac_robot_standalone",
    input_feature_id="FET001_MinimalPlaceableVisual.1-0-1",
    output_feature_id="CAP101_RobotComposition.Isaac.0-1-0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_isaac_robot(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Add the FET_101_ISAAC@0.1.0 feature using the standalone robot transform."""
    convert_to_isaacsim_robot(input_stage, output_stage)


def convert_to_isaacsim_prop(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Convert a PhysX prop asset to Isaac Sim format (standalone backend).

    Thin wrapper over :func:`_convert_with_simready_transform` using the
    ``simready_physx_to_isaac_prop`` transform.

    Args:
        input_stage: The source USD stage containing the PhysX prop.
        output_stage: The destination USD stage for the Isaac Sim asset.

    Raises:
        ValueError: If the input stage has no default prim.
        RuntimeError: If the asset transformation fails.
    """
    _convert_with_simready_transform(input_stage, output_stage, _SIMREADY_PROP_TRANSFORM, "prop")


def convert_to_isaacsim_robot(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Convert a PhysX robot asset to Isaac Sim format (standalone backend).

    Thin wrapper over :func:`_convert_with_simready_transform` using the
    ``simready_physx_to_isaac_robot`` transform.

    Args:
        input_stage: The source USD stage containing the PhysX robot.
        output_stage: The destination USD stage for the Isaac Sim asset.

    Raises:
        ValueError: If the input stage has no default prim.
        RuntimeError: If the asset transformation fails.
    """
    _convert_with_simready_transform(input_stage, output_stage, _SIMREADY_ROBOT_TRANSFORM, "robot")


def _convert_with_simready_transform(
    input_stage: Usd.Stage, output_stage: Usd.Stage, transform_name: str, asset_kind: str
):
    """Run the standalone ``simready.asset_transformer`` backend for one transform.

    Uses the public, Kit-free ``isaacsim.asset.transformer`` package with the
    named SimReady transform. Output is written into a temporary package and then
    reintegrated into the output stage by :func:`promotion.promote_transformed_package`.

    Args:
        input_stage: The source USD stage containing the PhysX asset.
        output_stage: The destination USD stage for the Isaac Sim asset.
        transform_name: Bundled transform alias (a ``profile_transforms`` JSON stem).
        asset_kind: Human-readable asset category used only for log messages.

    Raises:
        ValueError: If the input stage has no default prim.
        RuntimeError: If the asset transformation fails.
    """
    # Imported lazily so validation-only consumers do not load transformer code.
    # Load the integration first so a missing optional extra has an install hint.
    from simready.asset_transformer import AssetTransformerManager
    from simready.asset_transformer import load_profile as load_simready_profile
    from simready.asset_transformer import profile_transforms_dir
    from isaacsim.asset.transformer.rules import (
        register_all_rules as register_upstream_rules,
    )
    from simready.asset_transformer.patches import apply_simready_rule_patches
    from simready.asset_transformer.rules import (
        register_all_rules as register_simready_rules,
    )

    if not input_stage.GetDefaultPrim():
        raise ValueError("Input stage must have a default prim")

    output_path = Path(output_stage.GetRootLayer().identifier)
    asset_name = output_path.stem

    # Resolve the bundled transform by explicit path so profile loading does not
    # depend on importlib.resources alias lookups in the host runtime.
    profile_path = profile_transforms_dir() / f"{transform_name}.json"
    profile = load_simready_profile(profile_path)
    # Align the generated interface layer name with the promotion helper's lookup.
    profile.interface_asset_name = asset_name + ".usd"

    apply_simready_rule_patches()
    register_upstream_rules()
    register_simready_rules()
    manager = AssetTransformerManager()

    logger.info(f"Running SimReady AssetTransformerManager for {asset_kind} asset: {asset_name}")
    transformed_package_root = output_path.parent.parent / "temp_transformed_asset"
    if transformed_package_root.exists():
        shutil.rmtree(transformed_package_root)
    transformed_package_root.mkdir(parents=True)

    # simready.derive passes an anonymous snapshot as the input stage. Rules save
    # edits back into composed layers and anchor package paths to the source
    # file, so give the transformer a file-backed copy in that case.
    transformer_input: Usd.Stage | str = input_stage
    materialized_root = None
    if stage_source_path(input_stage) is None:
        materialized_root = output_path.parent.parent / "temp_source_asset"
        if materialized_root.exists():
            shutil.rmtree(materialized_root)
        transformer_input = str(materialize_stage(input_stage, materialized_root, output_path.name))
        logger.info(f"Materialized in-memory input stage for the transformer: {transformer_input}")
    try:
        report = manager.run(input_stage=transformer_input, profile=profile, package_root=str(transformed_package_root))
    finally:
        if materialized_root is not None:
            shutil.rmtree(materialized_root, ignore_errors=True)

    raise_on_rule_failure(report)

    del manager
    del report

    promote_transformed_package(output_stage, transformed_package_root, asset_name + ".usd")

    # ISA.001 requires the composed interface default prim to be a component
    # model. The standalone transform does not author model kind, so stamp it on
    # the promoted output stage here for both the prop and robot paths.
    _ensure_component_kind(output_stage)

    logger.info(f"Successfully converted {asset_kind} asset to Isaac Sim format: {asset_name}")


def _ensure_component_kind(output_stage: Usd.Stage) -> None:
    """Set ``kind = component`` on the output stage's default prim (ISA.001).

    The promotion step rewrites the output root layer from the transformer's
    package, which does not carry a model ``kind``. Stamp ``component`` on the
    default prim so the Isaac composition requirement ``ISA.001`` is satisfied.

    Args:
        output_stage: The destination stage whose default prim receives the kind.
    """
    default_prim = output_stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        logger.warning("Output stage has no valid default prim; skipping kind=component stamp")
        return
    Usd.ModelAPI(default_prim).SetKind(Kind.Tokens.component)
    output_stage.GetRootLayer().Save()
