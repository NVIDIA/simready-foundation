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
"""Feature adapters that convert assets into the Isaac Sim composition feature.

Two transformer backends coexist here as distinct Python modules:

- ``isaacsim.asset.transformer`` (aliased ``KitAssetTransformerManager``): the
  legacy Kit-extension backend used by the original ``FET_100_ISAAC@0.1.0`` and
  ``FET100_BASE_ISAACSIM@0.2.0`` adapter paths.
- ``simready.asset_transformer`` (aliased ``SimReadyAssetTransformerManager``):
  the standalone, Kit-free backend used by the standalone composition paths via
  the ``simready_physx_to_isaac_prop`` transform (prop) and the
  ``simready_physx_to_isaac_robot`` transform (robot).

Both backends share the same package-promotion/copy-back logic
(:func:`promotion.promote_transformed_package`) that reintegrates a transformer's
output package into the CIP output stage.
"""

import importlib
import importlib.util
import logging
import shutil
import sys
from pathlib import Path

from isaacsim.asset.transformer import (
    AssetTransformerManager as KitAssetTransformerManager,
)
from isaacsim.asset.transformer import RuleProfile as KitRuleProfile
from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Kind, Usd

try:  # normal package import when CIP loads this directory as a package
    from .promotion import promote_transformed_package, raise_on_rule_failure
except ImportError:  # fallback when loaded as a top-level module on sys.path
    from promotion import promote_transformed_package, raise_on_rule_failure

logger = logging.getLogger(__name__)

# Path to the legacy Kit-extension profile JSON relative to this module
_PROFILE_JSON_PATH = Path(__file__).parent / "asset" / "transformer" / "data" / "isaacsim_structure.json"

# Bundled standalone-transformer transforms used by the standalone composition paths.
_SIMREADY_PROP_TRANSFORM = "simready_physx_to_isaac_prop"
_SIMREADY_ROBOT_TRANSFORM = "simready_physx_to_isaac_robot"


def _ensure_simready_transformer_importable() -> None:
    """Make ``simready.asset_transformer`` importable.

    If the package is already importable (pip-installed distribution), do
    nothing. Otherwise add the in-repo ``src`` root to ``sys.path``. Because both
    ``simready.asset_transformer`` and the tier-core ``simready.foundation`` ship
    ``simready`` as a PEP 420 namespace package, the added path portion merges
    into the existing ``simready`` namespace without shadowing it.
    """
    try:
        if importlib.util.find_spec("simready.asset_transformer") is not None:
            return
    except ModuleNotFoundError:
        # No ``simready`` parent package at all; fall through to add the path.
        pass
    # In-repo source root for the standalone ``simready.asset_transformer``
    # package, used as a fallback when that package is not pip-installed in the
    # runtime (for example the Kit/CIP runtime that loads this adapter directly
    # from repo source).
    # Layout: <repo>/nv_core/cip_specs/isaac_asset_transformer/src/simready/...
    transformer_src = Path(__file__).resolve().parents[2] / "isaac_asset_transformer" / "src"
    src = str(transformer_src)
    if transformer_src.is_dir() and src not in sys.path:
        sys.path.insert(0, src)
        importlib.invalidate_caches()


# NOTE: Every adapter function below must have a UNIQUE name. The CIP feature
# adapter framework records ``func.__name__`` at decoration time and later
# invokes the selected adapter via ``getattr(module, func.__name__)``. Reusing a
# single name (e.g. ``modify_stage``) makes Python's module namespace keep only
# the last definition, so every selected adapter would dispatch to that last
# function regardless of which feature pair matched.
@feature_adapter(
    name="neutral_composition_to_isaacsim",
    input_feature_id="FET_001_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_100_ISAAC",
    output_feature_version="0.1.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_isaac_100_kit(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature."""
    convert_to_isaacsim(input_stage, output_stage)


@feature_adapter(
    name="neutral_composition_to_isaacsim_2",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="0.1.0",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.2.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_legacy_isaac_020_v1(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature."""
    convert_to_isaacsim(input_stage, output_stage)


@feature_adapter(
    name="neutral_composition_to_isaacsim_3",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="1.0.1",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.2.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_legacy_isaac_020_v2(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Modify the stage to add the ISAACSIM feature."""
    convert_to_isaacsim(input_stage, output_stage)


@feature_adapter(
    name="neutral_composition_to_isaacsim_4",
    input_feature_id="FET001_BASE_NEUTRAL",
    input_feature_version="1.0.1",
    output_feature_id="FET100_BASE_ISAACSIM",
    output_feature_version="0.4.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_legacy_isaac_040(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Add the ISAACSIM feature using the legacy Kit backend.

    Kept on the Kit-extension backend so the legacy ``FET100_BASE_ISAACSIM``
    path continues to work while the standalone transformer is adopted through
    the canonical ``FET_100_ISAAC`` / ``FET_101_ISAAC`` feature IDs.
    """
    convert_to_isaacsim(input_stage, output_stage)


@feature_adapter(
    name="minimal_to_isaac_prop_standalone",
    input_feature_id="FET_001_STANDARD",
    input_feature_version="1.0.1",
    output_feature_id="FET_100_ISAAC",
    output_feature_version="0.4.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_isaac_prop(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Add the FET_100_ISAAC@0.4.0 feature using the standalone prop transform."""
    convert_to_isaacsim_prop(input_stage, output_stage)


@feature_adapter(
    name="minimal_to_isaac_robot_standalone",
    input_feature_id="FET_001_STANDARD",
    input_feature_version="1.0.1",
    output_feature_id="FET_101_ISAAC",
    output_feature_version="0.1.0",
    priority=1000,  # low priority, so it runs last
)
def modify_stage_isaac_robot(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Add the FET_101_ISAAC@0.1.0 feature using the standalone robot transform."""
    convert_to_isaacsim_robot(input_stage, output_stage)


def convert_to_isaacsim(input_stage: Usd.Stage, output_stage: Usd.Stage):
    """Convert a PhysX robotic asset to Isaac Sim format (legacy Kit backend).

    Uses the Kit-extension ``AssetTransformerManager`` to apply robot schema
    transformation rules. The manager writes into a temporary package that is
    then reintegrated into the output stage by :func:`_promote_transformed_package`.

    Args:
        input_stage: The source USD stage containing the PhysX asset.
        output_stage: The destination USD stage for the Isaac Sim asset.

    Raises:
        ValueError: If the input stage has no default prim.
        RuntimeError: If the asset transformation fails.
        FileNotFoundError: If the profile JSON file is not found.
    """

    # Validate input stage has a default prim
    if not input_stage.GetDefaultPrim():
        raise ValueError("Input stage must have a default prim")

    output_path = Path(output_stage.GetRootLayer().identifier)
    asset_name = output_path.stem

    # Validate profile JSON exists
    if not _PROFILE_JSON_PATH.exists():
        raise FileNotFoundError(f"Profile JSON not found: {_PROFILE_JSON_PATH}")

    # Load the legacy Kit profile from JSON
    with open(_PROFILE_JSON_PATH, "r", encoding="utf-8") as f:
        profile = KitRuleProfile.from_json(f.read())

    # Configure the profile with asset-specific settings
    profile.interface_asset_name = asset_name + ".usd"

    manager = KitAssetTransformerManager()

    logger.info(f"Running Kit AssetTransformerManager for asset: {asset_name}")
    transformed_package_root = output_path.parent.parent / "temp_transformed_asset"
    if transformed_package_root.exists():
        shutil.rmtree(transformed_package_root)
    transformed_package_root.mkdir(parents=True)
    report = manager.run(input_stage=input_stage, profile=profile, package_root=transformed_package_root)

    raise_on_rule_failure(report)

    del manager
    del report

    promote_transformed_package(output_stage, transformed_package_root, asset_name + ".usd")

    logger.info(f"Successfully converted asset to Isaac Sim format: {asset_name}")


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

    Uses the standalone, Kit-free ``simready.asset_transformer`` package with the
    named bundled transform. Output is written into a temporary package and then
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
    # Imported lazily so the module still imports (and the legacy Kit adapters
    # still register) in environments where the standalone package is absent.
    # First make the bundled package importable when it is not pip-installed in
    # the runtime (for example the Kit/CIP runtime that loads this adapter from
    # repo source).
    _ensure_simready_transformer_importable()
    from simready.asset_transformer import (
        AssetTransformerManager as SimReadyAssetTransformerManager,
    )
    from simready.asset_transformer import load_profile as load_simready_profile
    from simready.asset_transformer import (
        profile_transforms_dir,
    )
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

    register_simready_rules()
    manager = SimReadyAssetTransformerManager()

    logger.info(f"Running SimReady AssetTransformerManager for {asset_kind} asset: {asset_name}")
    transformed_package_root = output_path.parent.parent / "temp_transformed_asset"
    if transformed_package_root.exists():
        shutil.rmtree(transformed_package_root)
    transformed_package_root.mkdir(parents=True)
    report = manager.run(input_stage=input_stage, profile=profile, package_root=str(transformed_package_root))

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
