---
name: simready-foundation-conform-cap-102-isaac
description: "Use for repairing exact CAP102_RigidBodyCollapse.Isaac SimReady rigid-body-collapse conformance by safely collapsing eligible fixed-joint bodies without changing simulation behavior."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
    - optimization
---

# SimReady Conform CAP102_RigidBodyCollapse.Isaac

## Purpose

Use this skill when a selected capability, profile, validation report, or user
request names `CAP102_RigidBodyCollapse.Isaac`. Repair only `OPT.001`.
Visual merging belongs to `CAP103_VisualMeshMerge.Isaac`.

Default to `CAP102_RigidBodyCollapse.Isaac.0-1-0` when no version is supplied.

## Source of Truth

Read these files before editing an asset:

- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP102_RigidBodyCollapse.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP102_RigidBodyCollapse.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/requirements/fixed-joint-no-mergeable-body-pair.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/validation.py`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/asset_handler_modules/isaac_optimization/fixed_joint_merge.py`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/asset_handler_modules/isaac_optimization/_massprops.py`

This capability has no dependencies. The adapter checks the composed bodies and
their mass properties before editing.

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | None | `OPT.001` |

## Inputs

| Input | Requirement |
|---|---|
| `usd_asset` | Source USD asset or package root. |
| `output_root` | Staged output directory. |
| `selected_version` | Exact version; defaults to `0-1-0`. |
| `validation_report` | Preferred report identifying `OPT.001`. |
| `adapter_host` | CIP, Kit, or Python 3.12 environment with USD. |

## Workflow

1. Load the exact manifest, capability page, requirement, validator, and adapter.
2. Validate the source against `CAP102_RigidBodyCollapse.Isaac`. If `OPT.001` passes, do not
   mutate the asset.
3. Stage a complete copy beneath `output_root`, including local sublayers;
   never silently mutate source. Shared reference and payload sources can stay
   referenced. Failed collapse restores all staged local layers.
4. Verify every candidate body's physics settings and mass properties.
5. Run `fixed_joint_rigid_body_merge`.
6. Save, close, reopen, and validate the staged artifact.
7. Stop when `CAP102_RigidBodyCollapse.Isaac` passes. Do not run the visual-mesh adapter unless
   `CAP103_VisualMeshMerge.Isaac` is separately selected.

## Safety Rules

- Preserve each dissolved body's subtree, world pose, unrelated applied schemas,
  relationship targets, and custom data.
- Compare mass, center of mass, full inertia tensors and center-of-mass velocity
  with the source, including rotated bodies with unequal inertias.
- Repoint every active joint on the stage and rebase its anchors.
- Check joints between independently collapsed groups, including moved holders.
- Preserve the exact collider pairs excluded by body-level collision filters;
  expand filters onto the original colliders instead of widening their scope.
- Do not collapse a body carrying a contact-report API or supported Isaac sensor.
- Do not create replacement geometry.
- For shape-changing convex hulls, decomposition or simplification, require
  complete authored
  `physics:mass`, `physics:diagonalInertia`, `physics:centerOfMass`, and
  `physics:principalAxes`. A closed SDF source surface is measurable; an open
  surface repaired by runtime cooking needs measured runtime mass properties.

## Blocked Cases

The adapter preflights every candidate assembly. Report `blocked` without
partial mutation when:

- a candidate body has no resolvable mass properties;
- a shape-changing approximation lacks complete authored mass properties;
- shear or non-uniform scale prevents a safe inertia transform;
- bodies have conflicting solver settings or simulation owners, incompatible
  initial velocities, time-sampled physics or transforms, or an articulation
  root that would be dissolved;
- a moving body uses `physics:localSpaceVelocities` custom data;
- an additional joint could become enabled and connect the collapsed body to itself;
- `Usd.NamespaceEditor` refuses the required move;
- the staged output cannot be saved and reopened.

## Validation

When only the bundled profile is available, run:

```bash
simready-validate --profile Asset-Optimization --version 1.0.0 <staged-asset>
```

Judge this skill only on `OPT.001`; report an `OPT.002` failure as the
separate `CAP103_VisualMeshMerge.Isaac` gate.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | Exact capability, normally `CAP102_RigidBodyCollapse.Isaac.0-1-0`. |
| `input` | Source asset inspected. |
| `output` | Staged output path. |
| `assemblies_collapsed` | Eligible assemblies collapsed. |
| `validation` | Reopened artifact and command used. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | First remaining blocker or separately selected capability. |
