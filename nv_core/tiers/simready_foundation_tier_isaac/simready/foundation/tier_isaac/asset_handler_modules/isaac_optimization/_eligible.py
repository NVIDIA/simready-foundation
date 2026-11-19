# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Which rigid bodies a fixed-joint merge may combine.

The adapter and validator share eligibility: dynamic bodies joined by an
unbreakable fixed joint, with no requirement to simulate either separately.
"""

from __future__ import annotations

from pxr import Usd, UsdPhysics

from simready.foundation.tier_isaac.rules_and_reqs.isaac_sim.optimizations._common import (
    is_dynamic_body,
    is_joint_enabled,
    is_unbreakable,
    joints,
    needs_separate_simulation,
    resolved_joint_bodies,
)

def mergeable_pairs(stage: Usd.Stage) -> list[tuple[str, str, str]]:
    """Every (joint, body0, body1) an unbreakable fixed joint makes mergeable."""
    found = []
    for joint_prim in joints(stage):
        if not joint_prim.IsActive() or not UsdPhysics.FixedJoint(joint_prim):
            continue
        if not is_unbreakable(joint_prim)[0]:
            continue  # a finite break force is authored behaviour
        if not is_joint_enabled(joint_prim):
            continue  # a disabled joint is not welding anything
        body0, body1 = resolved_joint_bodies(stage, joint_prim)
        if not body0 or not body1:
            continue  # one end is the world
        if body0[0] == body1[0]:
            continue  # both ends resolve to the same body; nothing to merge
        a, b = stage.GetPrimAtPath(body0[0]), stage.GetPrimAtPath(body1[0])
        if not (is_dynamic_body(a) and is_dynamic_body(b)):
            continue  # kinematic or disabled bodies are pinned deliberately
        if needs_separate_simulation(a) or needs_separate_simulation(b):
            continue
        found.append((str(joint_prim.GetPath()), body0[0], body1[0]))
    return found


def merge_groups(stage: Usd.Stage) -> dict[str, list[str]]:
    """Connected components of mergeable pairs, keyed by the retained body.

    The retained body is the one closest to the stage root, so the merged
    assembly keeps the path a consumer is most likely to already address.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _joint, a, b in mergeable_pairs(stage):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    clusters: dict[str, list[str]] = {}
    for node in list(parent):
        clusters.setdefault(find(node), []).append(node)

    groups = {}
    default_path = str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else ""
    for members in clusters.values():
        retained = sorted(members, key=lambda p: (p.count("/"), p != default_path, p))[0]
        groups[retained] = sorted(members)
    return groups


def dissolved_joints(stage: Usd.Stage) -> list[str]:
    """The joints a merge deactivates."""
    return sorted({j for j, _a, _b in mergeable_pairs(stage)})
