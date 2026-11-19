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
"""Shared transformer output-package promotion logic.

This module intentionally depends only on Pixar USD (``pxr``) and the standard
library so it can be imported and unit-tested without the Kit-extension or CIP
runtime dependencies that the adapter decorators in ``__init__.py`` require.
The standalone ``simready.asset_transformer`` backend reintegrates its output
packages through :func:`promote_transformed_package`.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from pxr import Sdf, Usd

logger = logging.getLogger(__name__)


def raise_on_rule_failure(report) -> None:
    """Raise ``RuntimeError`` on the first failed rule; log successful rule logs.

    Args:
        report: An execution report exposing ``results``; each result has
            ``success``, ``error``, ``rule`` (with ``name``), and ``log``.

    Raises:
        RuntimeError: On the first rule whose ``success`` is falsy, or when the
            output has unresolved composition arcs. The transformer then
            publishes nothing even though every rule succeeded.
    """
    for result in report.results:
        if not result.success:
            logger.error(f"Rule '{result.rule.name}' failed: {result.error}")
            raise RuntimeError(f"Asset transformation failed: {result.error}")
        for log_entry in result.log:
            logger.debug(f"[{result.rule.name}] {log_entry.get('message', '')}")
    composition_errors = list(getattr(report, "composition_errors", None) or [])
    if composition_errors:
        logger.error(f"Transformed package has {len(composition_errors)} unresolved composition arc(s)")
        raise RuntimeError(f"Asset transformation produced unresolved composition: {composition_errors[0]}")


def promote_transformed_package(
    output_stage: Usd.Stage, transformed_package_root: Path, interface_filename: str
) -> None:
    """Reintegrate a transformer output package into ``output_stage``.

    Asset transformation had a number of issues working "in place", so the
    backend outputs to a temporary package that this helper promotes into the
    output stage: the transformed root layer's contents are copied into the
    output root layer, and the remaining outputs (payloads/, materials/,
    Textures/, etc.) are moved up alongside the output root layer where its
    sublayer / reference paths expect them.

    Args:
        output_stage: The destination stage whose root layer receives the result.
        transformed_package_root: Temporary package produced by a transformer.
        interface_filename: Root layer filename written inside the temporary
            package (for example ``asset.usd``).

    Raises:
        RuntimeError: If the expected transformed package or layers are missing.
    """
    transformed_package_root = Path(transformed_package_root)
    if not transformed_package_root.is_dir():
        raise RuntimeError(f"Expected transformed asset directory not found: {transformed_package_root}")

    output_root_layer = output_stage.GetRootLayer()
    if output_root_layer is None:
        raise RuntimeError("Failed to get output root layer")

    output_root_path = Path(output_root_layer.identifier).resolve()
    package_dir = Path(output_root_layer.identifier).parent

    transformed_root_layer_path = transformed_package_root / interface_filename
    if not transformed_root_layer_path.exists():
        raise RuntimeError(f"Transformed root layer not found at expected location: {transformed_root_layer_path}")

    # CIP stages a package with copy-all semantics. Remove copied package
    # directories and sibling root-layer representations before promoting the
    # transformed package; NP.005 permits exactly one root USD file here.
    try:
        for entry in list(package_dir.iterdir()):
            if entry.is_dir() and entry.name != ".thumbs":
                shutil.rmtree(entry)
            elif (
                entry.is_file()
                and entry.resolve() != output_root_path
                and entry.suffix.lower() in {".usd", ".usda", ".usdc", ".usdz"}
            ):
                entry.unlink()
    except Exception as e:
        # not fatal, but we catch the exception and log it
        logger.warning(f"Warning cleaning staged package content: {e}")

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

    # Promote the remaining transformer outputs up one level into package_dir so
    # they sit alongside the output root layer. Skip the transformed root layer
    # file itself -- its contents already live in the output root layer via the
    # ``Sdf.CopySpec`` above.
    transformed_root_layer_resolved = transformed_root_layer_path.resolve()
    for entry in list(transformed_package_root.iterdir()):
        if entry.resolve() == transformed_root_layer_resolved:
            continue
        destination = package_dir / entry.name
        shutil.move(str(entry), str(destination))

    shutil.rmtree(transformed_package_root)
