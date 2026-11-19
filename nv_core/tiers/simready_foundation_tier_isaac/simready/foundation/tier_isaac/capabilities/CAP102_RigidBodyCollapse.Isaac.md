# Rigid-Body Collapse

| Property | Value |
| --- | --- |
| Capability | `CAP102_RigidBodyCollapse.Isaac.0-1-0` |
| Owning tier | Isaac |
| Requirement | [`OPT.001`](../rules_and_reqs/isaac_sim/optimizations/requirements/fixed-joint-no-mergeable-body-pair.md) |
| Dependencies | None |
| Profile | [Asset-Optimization@1.0.0](../profiles/asset-optimization.md) |

## Pass condition

No eligible pair of dynamic rigid bodies remains connected by an enabled,
unbreakable fixed joint.

The validator inspects fixed joints and resolves their body targets from the
composed stage. It excludes world anchors, disabled or breakable joints,
kinematic or disabled bodies, and bodies needed for the supported sensors or
contact reporting listed in the requirement.

The input is one composed USD stage with a default prim. No original model,
conversion history, or SimReady stamp is needed. An asset with no applicable
content passes. A pass establishes this structural condition for the asset's
selected composition.

## Validate and repair

1. Run `simready-validate --profile Asset-Optimization --version 1.0.0 asset.usd`
   and inspect `OPT.001`.
2. If this check passes, leave the asset unchanged.
3. If it fails, run `fixed_joint_rigid_body_merge` on a staged copy.
4. Save, reopen, and validate again. Report repair blockers with the affected
   prim and missing precondition.

The adapter moves each dissolved body's subtree under the retained body,
preserves world transforms, aggregates mass, center of mass, and inertia, and
repoints joints and body relationships. It runs first in the full profile.

Mass resolution is an adapter precondition. Shape-changing collider
approximations need positive authored mass and diagonal inertia; SDF surfaces
remain measurable. If a candidate's mass cannot be resolved safely, the adapter
refuses the entire pass before mutation. An optimization failure can therefore
require correcting the asset's mass data before automatic repair.

The callback is independently available from
`simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization`.
The installed `simready.feature_adapters` provider declares this capability as
the adapter's exact output, selected by `Asset-Optimization@1.0.0`.

## Validation evidence

Tests cover direct and payloaded composition, eligibility exclusions, schema
preservation, joint remapping, mass aggregation, and repeatability. Mass and
inertia preservation are checked with before/after adapter evidence.
