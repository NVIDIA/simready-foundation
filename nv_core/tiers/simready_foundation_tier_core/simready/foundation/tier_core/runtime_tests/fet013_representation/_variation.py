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

"""Shared runtime helpers for the fet013-fet016 asset-variation Evaluate tests.

These helpers sit on top of :mod:`simready.foundation.tier_core.asset_variants`
(the static read/compute layer shared with the ``AV.*`` validators) and add the
two things a *runtime* test needs: enumerate the authored options of a category,
and flip a variant selection on the live stage's **session** layer so the source
asset on disk is never mutated.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from pxr import Usd
from simready.foundation.tier_core import asset_variants as av


def category_entries(stage: Usd.Stage, category: str) -> List[Tuple[str, dict]]:
    """``[(variant_set_name, entry)]`` declared for ``category`` on ``stage``."""
    return [(vs, entry) for cat, vs, entry in av.iter_variation_entries(stage) if cat == category]


def entry_options(stage: Usd.Stage, entry: dict, variant_set_name: str) -> List[str]:
    """Authored option names for ``variant_set_name`` on the entry's prim."""
    prim = stage.GetPrimAtPath(entry.get("prim", ""))
    if not prim or not prim.IsValid():
        return []
    return av.option_names(prim, variant_set_name)


def compose_with_entry_selection(root_layer, entry: dict, variant_set_name: str, option: str) -> Usd.Stage:
    """Open a fresh stage with ``option`` selected on the entry's prim (session layer).

    Unlike :func:`asset_variants.compose_with_selection`, which only reaches
    variant sets on the default prim, this applies the selection to the exact
    prim named in the discovery entry, so per-part sets (``Category:part``)
    compose too. The selection is written on the session layer, never the root
    layer, so the authored defaults are left intact.
    """
    stage = Usd.Stage.Open(root_layer)
    prim = stage.GetPrimAtPath(entry.get("prim", ""))
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        if prim and prim.IsValid():
            prim.GetVariantSet(variant_set_name).SetVariantSelection(option)
    return stage


def runtime_select(stage: Usd.Stage, entry: dict, variant_set_name: str, option: str) -> bool:
    """Set a variant selection on the live stage's session layer. ``True`` on success."""
    prim = stage.GetPrimAtPath(entry.get("prim", ""))
    if not prim or not prim.IsValid():
        return False
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        prim.GetVariantSet(variant_set_name).SetVariantSelection(option)
    return True


def iter_all_options(stage: Usd.Stage, category: str) -> Iterable[Tuple[str, dict, str]]:
    """Yield ``(variant_set_name, entry, option)`` for every option of ``category``."""
    for variant_set_name, entry in category_entries(stage, category):
        for option in entry_options(stage, entry, variant_set_name):
            yield variant_set_name, entry, option


def axis_deltas(baseline, size) -> Dict[str, float]:
    """Per-axis absolute envelope-size deltas, as a JSON-friendly metric dict."""
    if baseline is None or size is None:
        return {"x": -1.0, "y": -1.0, "z": -1.0}
    return {axis: abs(size[i] - baseline[i]) for i, axis in enumerate("xyz")}
