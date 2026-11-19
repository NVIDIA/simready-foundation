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
"""Remove inactive collision schema stacks from renderable prims."""

from __future__ import annotations

from pxr import Sdf, Usd

from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    inactive_render_collision_schemas,
    traverse,
)

ADAPTER_NAME = "remove_inactive_render_collision_schemas"
ADAPTER_VERSION = "1.0.1"


class SeparationRefused(RuntimeError):
    """The inactive schema is on instance-proxy geometry and cannot be edited safely."""


def _without_schemas(existing: Sdf.TokenListOp, stale: list[str]) -> Sdf.TokenListOp:
    """Remove schemas while preserving unrelated explicit and list-op opinions."""
    stale_set = set(stale)
    op = Sdf.TokenListOp()
    if existing.isExplicit:
        op.explicitItems = [
            token for token in existing.explicitItems if token not in stale_set
        ]
        return op

    for field_name in (
        "addedItems",
        "prependedItems",
        "appendedItems",
        "orderedItems",
    ):
        setattr(
            op,
            field_name,
            [token for token in getattr(existing, field_name) if token not in stale_set],
        )
    op.deletedItems = list(existing.deletedItems) + [
        token for token in stale if token not in existing.deletedItems
    ]
    return op


def _remove_schema_stack(
    stage: Usd.Stage, path: Sdf.Path, schemas: list[str]
) -> None:
    stage.OverridePrim(path)
    spec = stage.GetEditTarget().GetLayer().GetPrimAtPath(path)
    if spec is None:
        raise RuntimeError(f"Could not author an override for <{path}>.")
    existing = (
        spec.GetInfo("apiSchemas")
        if spec.HasInfo("apiSchemas")
        else Sdf.TokenListOp()
    )
    spec.SetInfo("apiSchemas", _without_schemas(existing, schemas))


def cook_stage(stage: Usd.Stage) -> int:
    """Remove each editable inactive render-collision schema stack.

    Returns the number of prims repaired. Candidate resolution is all-or-nothing:
    an instance proxy blocks the pass before any schema list is changed.
    """
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        return 0

    candidates: list[tuple[Usd.Prim, list[str]]] = []
    for prim in traverse(default_prim):
        schemas = inactive_render_collision_schemas(prim)
        if schemas:
            candidates.append((prim, schemas))

    blocked = [
        str(prim.GetPath())
        for prim, _schemas in candidates
        if prim.IsInstanceProxy()
    ]
    if blocked:
        raise SeparationRefused(
            "Inactive collision schemas are authored through instance proxies: "
            f"{sorted(blocked)}. Edit the source prototype instead of de-instancing it."
        )

    animated = [str(prim.GetPath()) for prim, _ in candidates
                if (attr := prim.GetAttribute('physics:collisionEnabled')) and attr.GetNumTimeSamples()]
    if animated:
        raise SeparationRefused(
            f"Collision enablement is time-sampled on {animated}; preserve its collision schemas."
        )

    for prim, schemas in candidates:
        _remove_schema_stack(stage, prim.GetPath(), schemas)
    return len(candidates)
