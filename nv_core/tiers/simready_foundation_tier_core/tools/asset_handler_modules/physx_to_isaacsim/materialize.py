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
"""Write an in-memory (for example anonymous snapshot) stage to disk for the transformer."""

from __future__ import annotations

import os
from pathlib import Path

from pxr import Sdf, Usd

_USD_EXTENSIONS = (".usd", ".usda", ".usdc")


def stage_source_path(stage: Usd.Stage) -> str | None:
    """Return the root layer's file path when the whole layer graph is file-backed."""
    root = stage.GetRootLayer()
    if root.anonymous or not root.realPath:
        return None
    pending, seen = [root], set()
    while pending:
        layer = pending.pop()
        if layer.identifier in seen:
            continue
        seen.add(layer.identifier)
        if layer.anonymous:
            return None
        for dependency in layer.GetCompositionAssetDependencies():
            found = Sdf.Layer.Find(layer.ComputeAbsolutePath(dependency)) or Sdf.Layer.Find(dependency)
            if found is not None:
                pending.append(found)
    return root.realPath


def materialize_stage(stage: Usd.Stage, destination: Path, root_filename: str) -> Path:
    """Export *stage*'s root layer and every anonymous layer it composes under *destination*.

    ``simready.derive`` hands adapters an anonymous snapshot of the output
    stage. The transformer rules save edits back into composed layers and
    anchor package paths to the source file, so they need real files. Composed
    file-backed layers are referenced by absolute path; anonymous ones are
    written next to the root and re-linked with explicit relative paths.

    Returns:
        Path of the exported root layer.
    """
    destination.mkdir(parents=True, exist_ok=True)
    root = stage.GetRootLayer()
    targets: dict[str, Path] = {root.identifier: destination / root_filename}
    order: list[Sdf.Layer] = []
    pending = [root]
    while pending:
        layer = pending.pop(0)
        if layer in order:
            continue
        order.append(layer)
        for dependency in layer.GetCompositionAssetDependencies():
            found = Sdf.Layer.Find(dependency)
            if found is None or not found.anonymous or found.identifier in targets:
                continue
            name = found.GetDisplayName() or "layer.usda"
            if not name.lower().endswith(_USD_EXTENSIONS):
                name += ".usda"
            targets[found.identifier] = destination / "layers" / f"{len(targets):03d}_{name}"
            pending.append(found)

    for layer in order:
        target = targets[layer.identifier]
        target.parent.mkdir(parents=True, exist_ok=True)
        copy = Sdf.Layer.CreateAnonymous(target.suffix)
        copy.TransferContent(layer)
        for dependency in layer.GetCompositionAssetDependencies():
            found = Sdf.Layer.Find(dependency)
            if found is not None and found.identifier in targets:
                relative = os.path.relpath(targets[found.identifier], target.parent).replace(os.sep, "/")
                if not relative.startswith("../"):
                    relative = f"./{relative}"
                copy.UpdateCompositionAssetDependency(dependency, relative)
        if not copy.Export(str(target)):
            raise RuntimeError(f"Could not materialize adapter input layer: {target}")
    return targets[root.identifier]
