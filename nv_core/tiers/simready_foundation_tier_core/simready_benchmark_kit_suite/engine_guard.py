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
"""Engine-aware guards shared across the physics test families.

The PhysX path is never gated here: PhysX is lenient and runs the sample assets
correctly, so ``physx`` always reports "ready". The guards only act under a
non-PhysX backend (Newton), which is stricter than PhysX in ways that would
otherwise crash the session:

- Newton parses the whole USD stage up front and aborts scene init on USD
  composition errors (e.g. an unresolved internal reference) that PhysX
  tolerates and simulates anyway. When init aborts, ``timeline.play()`` still
  returns, but ``SimulationManager`` has no physics sim view; a test that then
  steps the (broken) simulation crashes the Kit process.

``newton_scene_initialized`` lets a physics test verify, right after ``play()``,
that the active engine actually built a simulation. Under PhysX it is always
True. Under Newton it is False when init aborted, so the caller skips honestly
(``NEWTON_SCENE_SKIP``) instead of stepping a broken sim and crashing.
"""

NEWTON_SCENE_SKIP = (
    "Newton could not initialize this asset's physics scene (USD composition "
    "errors, or a schema PhysX tolerates but Newton rejects). Skipped on Newton "
    "to avoid stepping a broken simulation; PhysX runs this asset normally. This "
    "is an engine-strictness / asset-authoring gap, not a runtime failure."
)


def newton_scene_initialized():
    # type: () -> bool
    """True if the active engine built a physics simulation after ``play()``.

    Always True under PhysX (never gated). Under Newton, returns False when
    ``SimulationManager.get_physics_sim_view()`` is missing or invalid -- Newton
    aborted scene init (composition errors or an unsupported schema). Returns
    True (do not gate) whenever the engine or the SimulationManager API cannot be
    queried, so a detection gap never turns a runnable asset into a false skip.

    Call this AFTER ``play()`` and at least one pumped update, because Newton
    initializes physics in the play callback on the next frame.
    """
    try:
        from simready_benchmark_engine_kit.physics_utils import active_physics_engine

        if active_physics_engine() == "physx":
            return True
    except Exception:
        return True

    try:
        from isaacsim.core.simulation_manager import SimulationManager

        view = SimulationManager.get_physics_sim_view()
    except Exception:
        return True  # cannot query -> do not gate

    if view is None:
        return False
    is_valid = getattr(view, "is_valid", None)
    try:
        return bool(is_valid()) if callable(is_valid) else True
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Loose-joint articulation wrapping (shared by every physics test family)
# ---------------------------------------------------------------------------
#
# PhysX runs an asset's loose (maximal-coordinate) joints directly; Newton
# reduces physics to reduced-coordinate articulations and ABORTS scene init
# when it sees loose joints with no articulation root. A correctly-authored
# prop that works on PhysX is not deficient, so rather than skip it or demand
# an articulation root in the USD, every physics test wraps its loose joints in
# an articulation on the LIVE stage before play() (the asset on disk is
# unchanged). Only clean joint trees are wrapped; anything the wrapper cannot
# safely represent is left loose and the scene-init guard skips it honestly.

_ARTICULATION_JOINT_TYPES = ("PhysicsRevoluteJoint", "PhysicsPrismaticJoint", "PhysicsFixedJoint")


def asset_has_articulation(stage):
    # type: (object) -> bool
    """Return whether any stage prim carries ArticulationRootAPI."""
    try:
        for prim in stage.Traverse():
            schemas = prim.GetMetadata("apiSchemas")
            names = list(getattr(schemas, "GetAppliedItems", lambda: [])()) if schemas else []
            if any("ArticulationRootAPI" in n for n in names):
                return True
        return False
    except Exception:
        return False


def _rigid_body_ancestor(stage, path):
    # type: (object, object) -> object
    """Walk up from ``path`` to the nearest prim carrying RigidBodyAPI, else the
    original ``path``. A body relationship often targets a collider mesh child;
    the articulation link is the rigid body."""
    prim = stage.GetPrimAtPath(path)
    while prim and prim.IsValid() and prim != stage.GetPseudoRoot():
        sch = prim.GetMetadata("apiSchemas")
        names = list(getattr(sch, "GetAppliedItems", lambda: [])()) if sch else []
        if any("RigidBodyAPI" in n for n in names):
            return prim.GetPath()
        prim = prim.GetParent()
    return path


def articulationize_loose_joints(ctx, stage):
    # type: (object, object) -> bool
    """Wrap an asset's loose (maximal-coordinate) joints in a reduced-coordinate
    articulation on the live stage so Newton can build the scene (and PhysX can
    drive them stably).

    Repoints each joint's body relationships to their rigid-body links and
    applies ArticulationRootAPI to the base link(s) -- a link that is a joint
    parent but never a joint child. Only acts when the joints form a clean tree:
    every joint connects exactly two links, no link has two parents, and every
    link traces back to a root. A joint to world, a shared child, a loop, or a
    spherical/D6 joint (driven by a velocity nudge an articulation ignores) is
    left loose, and the scene-init guard skips such assets honestly.
    Already-articulated assets are left untouched. Returns True if the asset now
    carries an articulation.
    """
    if asset_has_articulation(stage):
        return True

    from pxr import UsdPhysics

    joint_prims = [
        p for p in stage.Traverse() if str(p.GetTypeName()).startswith("Physics") and "Joint" in str(p.GetTypeName())
    ]
    if not joint_prims:
        return False

    if any(str(p.GetTypeName()) not in _ARTICULATION_JOINT_TYPES for p in joint_prims):
        return False

    edges = []  # (joint_prim, parent_path, child_path)
    parent_of = {}  # child link (str) -> parent link (str)
    links = set()  # type: set
    for jp in joint_prims:
        j = UsdPhysics.Joint(jp)
        b0 = [_rigid_body_ancestor(stage, t) for t in j.GetBody0Rel().GetTargets()]
        b1 = [_rigid_body_ancestor(stage, t) for t in j.GetBody1Rel().GetTargets()]
        if len(b0) != 1 or len(b1) != 1:
            return False  # joint to world or multi-body: not a clean tree
        parent, child = str(b0[0]), str(b1[0])
        if child in parent_of or parent == child:
            return False  # shared child or self-loop: not a tree
        parent_of[child] = parent
        links.update((parent, child))
        edges.append((jp, b0[0], b1[0]))

    roots = [ln for ln in links if ln not in parent_of]
    if not roots:
        return False  # every link has a parent: a closed loop, not a tree

    for child in parent_of:
        seen = set()
        cur = child
        while cur in parent_of:
            if cur in seen:
                return False  # cycle
            seen.add(cur)
            cur = parent_of[cur]

    for jp, p0, p1 in edges:
        j = UsdPhysics.Joint(jp)
        j.GetBody0Rel().SetTargets([p0])
        j.GetBody1Rel().SetTargets([p1])
    from pxr import PhysxSchema

    applied = []
    for r in roots:
        prim = stage.GetPrimAtPath(r)
        if prim and prim.IsValid():
            UsdPhysics.ArticulationRootAPI.Apply(prim)
            PhysxSchema.PhysxArticulationAPI.Apply(prim).CreateEnabledSelfCollisionsAttr(False)
            applied.append(r)
    ctx.step(
        "Wrapped %d loose joint(s) in an articulation (self-collision off); "
        "ArticulationRootAPI on: %s" % (len(edges), ", ".join(applied))
    )
    return True
