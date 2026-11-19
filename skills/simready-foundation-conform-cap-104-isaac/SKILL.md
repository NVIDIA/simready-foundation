---
name: simready-foundation-conform-cap-104-isaac
description: "Use for repairing exact CAP104_RenderCollisionSeparation.Isaac SimReady render-collision-separation conformance without changing active collider behavior."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
    - optimization
---

# SimReady Conform CAP104_RenderCollisionSeparation.Isaac

## Purpose

Use this skill when a selected capability, profile, validation report, or user
request names `CAP104_RenderCollisionSeparation.Isaac`. Repair only `OPT.003`.
Body collapse and visual merging belong to `CAP102_RigidBodyCollapse.Isaac` and
`CAP103_VisualMeshMerge.Isaac`.

Default to `CAP104_RenderCollisionSeparation.Isaac.0-1-0` when no version is supplied.

## Source of Truth

Read these files before editing an asset:

- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP104_RenderCollisionSeparation.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP104_RenderCollisionSeparation.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/requirements/render-only-no-inactive-collision-schemas.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/validation.py`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/asset_handler_modules/isaac_optimization/render_collision_separation.py`

This capability has no dependencies. The adapter inspects the composed
collision settings before removing inactive schemas.

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | None | `OPT.003` |

## Inputs

| Input | Requirement |
|---|---|
| `usd_asset` | Source USD asset or package root. |
| `output_root` | Staged output directory. |
| `selected_version` | Exact version; defaults to `0-1-0`. |
| `validation_report` | Preferred report identifying `OPT.003`. |
| `adapter_host` | CIP, Kit, or Python 3.12 environment with USD. |

## Workflow

1. Load the exact manifest, capability page, requirement, validator, and adapter.
2. Validate the source against `CAP104_RenderCollisionSeparation.Isaac`. If `OPT.003` passes, do not
   mutate the asset.
3. Stage a complete copy beneath `output_root`; never silently mutate source.
4. Snapshot active collider paths, owners, world transforms, and
   physics-material targets.
5. Count authored and composed collision schema tokens and inactive slots.
6. Run `remove_inactive_render_collision_schemas`.
7. Save, close, reopen, and validate the staged artifact. Compare the active
   collider snapshot and schema/slot counts with the source.
8. If an Isaac/PhysX runtime is available, record its active simulator-shape
   count. Otherwise report that runtime evidence as not run; do not infer it
   from schema counts.
9. Stop when `CAP104_RenderCollisionSeparation.Isaac` passes. Run other adapters
   only when their capabilities are selected.

## Safety Rules

- Remove only known collision schema tokens from `default` or `render`
  purpose prims with no enabled `PhysicsCollisionAPI`.
- Preserve unrelated schema list operations and property opinions.
- Never enable collision to silence the validator.
- Never edit an instance proxy or de-instance shared topology; repair the source
  prototype instead.
- Do not instance or combine visual topology in this workflow.
- Require active collider paths, owners, transforms, and physics-material
  targets to remain equal before and after.

## Blocked Cases

Report `blocked` without saving partial output when:

- a candidate is authored through an instance proxy;
- a candidate's collision enablement is time-sampled;
- an active collider snapshot differs after repair;
- required schema list operations cannot be preserved;
- the staged output cannot be saved and reopened.

## Validation

When only the bundled profile is available, run:

```bash
simready-validate --profile Asset-Optimization --version 1.0.0 <staged-asset>
```

Judge this skill only on `OPT.003`; report `OPT.001` or `OPT.002` failures
as their separate capability gates.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | Exact capability, normally `CAP104_RenderCollisionSeparation.Isaac.0-1-0`. |
| `input` | Source asset inspected. |
| `output` | Staged output path. |
| `schemas_removed` | Authored and composed collision schema counts. |
| `inactive_slots` | Counts before and after repair. |
| `active_shapes` | Runtime shape counts, or explicitly `not run`. |
| `collider_equivalence` | Ownership, transform, and material comparison. |
| `validation` | Reopened artifact and command used. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | First remaining blocker or separately selected capability. |
