# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sublayer and prim-spec lookups shared by the AIF capability validators.

An AIF asset composes its metadata and its connection points from named
sublayers. Every capability needs the same two answers -- which layer holds the
metadata, and what the default prim on it declares -- so both live here rather
than once per capability.
"""
from typing import Optional

from pxr import Sdf, Tf, Usd

# An AIF sublayer is identified by a fragment of its filename. Any of USD's three
# file extensions is accepted: the extension records how the layer is encoded and
# says nothing about what it holds.
_USD_EXTENSIONS = (".usd", ".usda", ".usdc")


def resolve_sublayer(stage: Usd.Stage, sublayer_path: str) -> Optional[Sdf.Layer]:
    """Resolve one of the root layer's sublayer paths to an open layer."""
    root_layer = stage.GetRootLayer()

    # A layer already in the composed stack, matched on filename. The comparison
    # is an equality against the path being resolved: a substring test picks up
    # any other layer whose name happens to contain the same fragment.
    target_filename = sublayer_path.replace("\\", "/").split("/")[-1].lower()
    for layer in stage.GetLayerStack():
        if layer.identifier.replace("\\", "/").split("/")[-1].lower() == target_filename:
            return layer

    # Opening raises on a layer USD cannot parse -- a truncated crate file, a
    # binary .usdc holding text. A validator reports that as a finding on the
    # rules that needed the layer; it does not abort the run.
    try:
        resolved = Sdf.ComputeAssetPathRelativeToLayer(root_layer, sublayer_path)
        layer = Sdf.Layer.FindOrOpen(resolved)
        if layer:
            return layer
        return Sdf.Layer.FindRelativeToLayer(root_layer, sublayer_path)
    except Tf.ErrorException:
        return None


def find_sublayer(stage: Usd.Stage, name_fragment: str) -> Optional[Sdf.Layer]:
    """Return the sublayer holding `name_fragment`, preferring the asset's own.

    AM.001 asks for "a sublayer with 'properties' in its filename", which more
    than one sublayer can satisfy -- a shared `Shared_material_properties.usda`
    matches as readily as the asset's own `Generic_CRAH_Properties.usda`. The asset's
    own layer wins, named for the root layer, and the looser match is the
    fallback so an asset that does not follow the naming convention still
    resolves.
    """
    root_layer = stage.GetRootLayer()
    if not root_layer:
        return None

    stem = root_layer.identifier.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0].lower()
    candidates = []
    for sublayer_path in root_layer.subLayerPaths:
        filename = sublayer_path.replace("\\", "/").split("/")[-1].lower()
        if name_fragment not in filename or not filename.endswith(_USD_EXTENSIONS):
            continue
        preferred = filename.rsplit(".", 1)[0] == f"{stem}_{name_fragment}"
        candidates.append((0 if preferred else 1, sublayer_path))

    for _, sublayer_path in sorted(candidates, key=lambda c: c[0]):
        layer = resolve_sublayer(stage, sublayer_path)
        if layer:
            return layer
    return None


def properties_prim_spec(stage: Usd.Stage) -> Optional[Sdf.PrimSpec]:
    """Return the default prim spec on the asset's properties sublayer."""
    layer = find_sublayer(stage, "properties")
    if not layer or not layer.defaultPrim:
        return None
    return layer.GetPrimAtPath(f"/{layer.defaultPrim}")


def asset_class_value(stage: Usd.Stage) -> Optional[str]:
    """Return the authored `aif:core:assetClass` value, unnormalised."""
    prim_spec = properties_prim_spec(stage)
    if not prim_spec:
        return None
    attr = prim_spec.attributes.get("aif:core:assetClass")
    if not attr or not attr.default:
        return None
    return str(attr.default)
