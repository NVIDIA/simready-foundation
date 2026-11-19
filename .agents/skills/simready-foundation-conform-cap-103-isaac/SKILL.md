---
name: simready-foundation-conform-cap-103-isaac
description: "Use for repairing exact CAP103_VisualMeshMerge.Isaac SimReady visual-mesh-merge conformance without changing rendering or collision behavior."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
    - optimization
---

# SimReady Conform CAP103_VisualMeshMerge.Isaac

## Purpose

Use this skill when a selected capability, profile, validation report, or user
request names `CAP103_VisualMeshMerge.Isaac`. Repair only `OPT.002`.
Body collapse belongs to `CAP102_RigidBodyCollapse.Isaac`.

Default to `CAP103_VisualMeshMerge.Isaac.0-1-0` when no version is supplied.

## Source of Truth

Read these files before editing an asset:

- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP103_VisualMeshMerge.Isaac.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/capabilities/CAP103_VisualMeshMerge.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/requirements/rigid-body-no-multiple-visual-meshes.md`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/rules_and_reqs/isaac_sim/optimizations/validation.py`
- `nv_core/tiers/simready_foundation_tier_isaac/simready/foundation/tier_isaac/asset_handler_modules/isaac_optimization/visual_mesh_merge.py`

This capability has no dependencies. Each merge group contains meshes owned by
the same rigid body in the composed stage.

| Version | Dependencies | Requirements |
|---|---|---|
| `0-1-0` | None | `OPT.002` |

## Inputs

| Input | Requirement |
|---|---|
| `usd_asset` | Source USD asset or package root. |
| `output_root` | Staged output directory. |
| `selected_version` | Exact version; defaults to `0-1-0`. |
| `validation_report` | Preferred report identifying `OPT.002`. |
| `adapter_host` | CIP, Kit, or Python 3.12 environment with a compatible USD runtime and `usd-optimize>=1.4.0`. |

## Workflow

1. Load the exact manifest, capability page, requirement, validator, and adapter.
2. Validate the source against `CAP103_VisualMeshMerge.Isaac`. If `OPT.002` passes, do not
   mutate the asset.
3. Stage a complete copy beneath `output_root`; never silently mutate source.
4. Run `rigid_body_visual_mesh_merge`. It works independently and also sees
   any earlier collapse when `CAP102_RigidBodyCollapse.Isaac` was separately selected.
5. Require usd-optimize to produce one identifiable merged mesh per group.
6. Save, close, reopen, and validate the staged artifact.
7. Stop when `CAP103_VisualMeshMerge.Isaac` passes. Do not run the fixed-body adapter unless
   `CAP102_RigidBodyCollapse.Isaac` is separately selected.

## Safety Rules

- Merge only visual meshes owned by the same rigid body.
- Never merge collision geometry.
- Preserve materials and non-conflicting survivor property specs, including
  relationships, connections, metadata, variability, and time samples.
- Compare world-space geometry, normals, UVs, and face material assignments
  after reopening. A lower mesh count alone does not establish preservation.
- Preserve primvar types, values, indices, element sizes, metadata and inherited
  constants. Report unsupported values.
- Drop a survivor attribute only when another source mesh authors a conflicting
  value that would be false for part of the merged result.
- Preserve usd-optimize diagnostics; do not guess which output mesh survived.

## Blocked Cases

Report `blocked` without saving partial output when:

- usd-optimize is unavailable or fails;
- a merge produces no single identifiable new mesh;
- required material or property state cannot be preserved;
- a candidate uses `full` or `preview` purpose-specific material bindings;
- mixed bound and unbound faces require clearing an inherited or collection
  material default that remains effective;
- a candidate has animated geometry, transforms, or visibility; skinning;
  non-subset children; or its own rigid-body API;
- the staged output cannot be saved and reopened.

## Validation

When only the bundled profile is available, run:

```bash
simready-validate --profile Asset-Optimization --version 1.0.0 <staged-asset>
```

Judge this skill only on `OPT.002`; report an `OPT.001` failure as the
separate `CAP102_RigidBodyCollapse.Isaac` gate.

## Report Fields

| Field | Meaning |
|---|---|
| `capability` | Exact capability, normally `CAP103_VisualMeshMerge.Isaac.0-1-0`. |
| `input` | Source asset inspected. |
| `output` | Staged output path. |
| `mesh_groups_merged` | Eligible per-body mesh groups merged. |
| `validation` | Reopened artifact and command used. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | First remaining blocker or separately selected capability. |
