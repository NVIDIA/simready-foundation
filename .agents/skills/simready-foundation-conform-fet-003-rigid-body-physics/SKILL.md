---
name: simready-foundation-conform-fet-003-rigid-body-physics
description: "Use for repairing SimReady rigid-body and collider conformance for neutral or PhysX prop assets."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physics
---


# SimReady Conform FET-003 Rigid Body Physics

## Purpose
Use this workflow skill after FET000_CORE and FET001_BASE_NEUTRAL pass and the next profile validation gate is `FET003_BASE_NEUTRAL` or `FET003_BASE_PHYSX`. It brings a staged USD asset toward the SimReady rigid body physics contract while preserving visual hierarchy, physical scale, and source traceability.

This is an authoring and repair skill, not the final validator. Work on a staged copy under the requested output directory, rerun the same validation gate after each repair stage, and stop at the first remaining FET003 validation failure that needs user intent or upstream conversion data.

## Prerequisites

Read the source-of-truth files named below before editing. Work on staged outputs where the skill requires them, and keep validation evidence with the result.

## Source of Truth

Before changing an asset, load the exact FET003 manifest selected by the profile:

- `nv_core/sr_specs/docs/features/FET_003_base_neutral-0.1.0-rigid_body_physics.json`
- `nv_core/sr_specs/docs/features/FET_003_base_physx-0.1.0-rigid_body_physics.json`
- `nv_core/sr_specs/docs/features/FET_003_base_physx-0.2.0-rigid_body_physics.json`
- `nv_core/sr_specs/docs/features/FET_003-rigid_body_physics.md`

Treat the selected JSON manifest as authoritative for the required IDs. If the markdown, manifest, validator, or report disagree on a requirement ID, follow the validation report for the current gate and call out the mismatch in the stage summary.

For per-requirement repair details, read `references/fet003-requirements.md` when a FET003 validation report or inspection identifies matching failures.

## Inputs

Collect these before editing:

| Input | Requirement |
|---|---|
| `usd_asset` | Required `.usd`, `.usda`, `.usdc`, or unpacked USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` | Profile being validated, such as `prop-robotics-neutral`, `prop-robotics-physx`, or another profile that includes FET003. |
| `profile_version` | Profile version, if supplied by the user or validation command. |
| `validation_report` | Preferred JSON or markdown report from the failing profile or feature validation gate. |
| `fet003_variant` | Selected feature ID and version, such as `FET003_BASE_NEUTRAL@0.1.0` or `FET003_BASE_PHYSX@0.2.0`. Infer from the profile when possible. |
| `rigid_body_policy` | Whether the asset should behave as one rigid body, multiple independent bodies, or an articulated/multibody asset. Default to one rigid body only when the profile and asset structure make that clear. |
| `collider_strategy` | Explicit strategy for collision geometry: existing collider meshes, visual mesh reuse, simplified proxy geometry, primitive proxy, PhysX mesh merge, or block for user choice. |
| `mass_source` | Explicit mass value, property report, source metadata, or user-approved default. Do not invent physical mass silently. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the input asset exists and that FET000_CORE and FET001_BASE_NEUTRAL are already passing on the same staged asset. If they still fail, hand back to `simready-foundation-conform-fet-000-core` or `simready-foundation-conform-fet-001-minimal` first.
2. Parse the validation report and filter to FET003 failures. Do not repair later profile features such as FET004 multibody physics or FET005 grasp physics in this skill.
3. Load the selected FET003 manifest version and the requirement repair map.
4. Create a staged output folder under `output_root`; do not mutate the source unless the user explicitly asks for in-place repair.
5. Inspect the stage before editing:
   - default prim, root prim, root xform ops, stage units, and composed bounds
   - existing `UsdPhysics.RigidBodyAPI`, `CollisionAPI`, `MeshCollisionAPI`, and `MassAPI`
   - mesh and Gprim candidates for collision geometry
   - instanceable prims, instance proxies, prototypes, nested rigid bodies, and skew or non-uniform scale
   - invisible or physics-only geometry purpose values
   - PhysX schemas and mesh-merge collections when a PhysX FET003 variant is selected
6. Decide the rigid-body model before authoring:
   - Use one rigid body on the asset root or another clear xformable body root for simple movable props.
   - Use multiple rigid bodies only when the profile and asset structure clearly call for independent bodies.
   - Stop and hand off to FET004-oriented work when the asset needs articulated joints or multibody semantics.
7. Apply repairs in this order:
   - Remove or relocate invalid rigid-body and collision APIs before adding new ones.
   - Apply `UsdPhysics.RigidBodyAPI` only to valid `UsdGeomXformable` body roots.
   - Apply `UsdPhysicsCollisionAPI` only to valid collider prims for the selected FET003 variant.
   - Apply `UsdPhysicsMeshCollisionAPI` only where allowed by the selected neutral or PhysX rule.
   - Author mass only from an explicit source or user-approved policy.
   - Fix instancing, nesting, skew, and non-uniform collider scale issues.
   - Mark invisible collision-only meshes with `purpose = "guide"`.
8. Rerun the same profile validation gate, or the narrowest available FET003 validation gate.
9. Summarize the stage as passed, failed, skipped, or blocked. Stop when FET003 passes or the next FET003 failure requires source geometry, property prediction, mass data, collider intent, or a different feature skill.

## Examples

Example request:

```text
Repair FET003 rigid body physics failures on a prop USD asset.
```

Expected result summary:

```text
staged_asset: repaired copy or output directory
validation: selected feature/profile gate and report path
remaining_failures: next failing requirement IDs, if any
```

## Repair Policy

Make automatic repairs only when the intended result is mechanical and locally verifiable:

- Add `UsdPhysics.RigidBodyAPI` to a single xformable asset root when the asset is clearly a one-piece movable rigid body.
- Move `CollisionAPI` from an invalid Xform to a descendant Gprim only when that descendant is the clear collision representation.
- Add `CollisionAPI` to existing dedicated collider geometry when naming, purpose, or hierarchy clearly identifies it as collision geometry.
- Add `MeshCollisionAPI` to meshes only when mesh collision is the selected collider strategy and `CollisionAPI` is also present.
- Set `purpose = "guide"` on invisible collision-only mesh geometry.
- Remove `RigidBodyAPI`, `CollisionAPI`, or `MeshCollisionAPI` from invalid prims only when a valid replacement is authored in the same staged asset or the API is plainly accidental.
- Preserve the asset's composed physical size after any transform or scale repair.

Block and report instead of guessing when:

- The asset could be a static prop rather than a dynamic rigid body.
- Multiple plausible rigid body roots exist.
- Collision geometry must be generated from CAD/source data and no accepted collider strategy is available.
- Mass is missing and there is no explicit property source or user-approved default.
- De-instancing or baking transforms would change shared composition semantics.
- Nested rigid bodies likely indicate joints or articulation that belong to FET004.
- PhysX mesh merge is required but PhysX schemas or collection APIs are unavailable in the local environment.

## Variant Guidance

For `FET003_BASE_NEUTRAL`, prefer standard OpenUSD `UsdPhysics` schemas and avoid PhysX-only collider patterns. `CollisionAPI` belongs on `UsdGeomGprim` prims, and mesh-specific collision belongs on `UsdGeomMesh` prims that also have `CollisionAPI`.

For `FET003_BASE_PHYSX`, follow the selected manifest version. PhysX variants may allow `CollisionAPI` or `MeshCollisionAPI` on a mesh-merge Xform when `PhysxMeshMergeCollisionAPI` is applied and the `collisionmeshes` collection resolves to at least one Gprim. Do not use PhysX-only repairs for a neutral profile.

## Validation Handoff

Preserve reports under the staged output directory. If the Physical AI Skill Hub validation commands are available, use the same profile gate that exposed the failure:

```bash
uv run --python 3.12 validate-simready-profile <staged-usd> \
  --profile <profile> \
  --profile-version <version> \
  --foundation-root <simready-foundation-root> \
  --foundation-spec-root <simready-foundation-root>/nv_core/sr_specs/docs \
  --report <output-root>/simready-profile-after-fet003.json
```

Count this skill as successful when the selected FET003 variant passes, even if the full profile still fails on later features. Report those remaining failures as handoff work for their own skills.

## Limitations

- Do not silently mutate the source asset; work on the requested staged output.
- Do not hide later profile failures after the selected feature gate passes or fails.
- Do not invent geometry, metadata, or runtime behavior that conflicts with the asset intent.

## Troubleshooting

- Error: validation tooling is unavailable. Solution: run the narrowest available USD or static check and report the gap.
- Error: a repair would change asset intent. Solution: stop and ask for direction or stage the smallest reversible edit.
- Error: later profile gates still fail. Solution: report the next failing feature and hand off to the matching conformance skill.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.
- `references/` contains detailed requirement notes; load only the files needed for the active validation failure.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `input_usd_path` | Original USD path. |
| `output_usd_path` | Latest staged/repaired USD path. |
| `profile` and `profile_version` | Validation target. |
| `fet003_variant` | Selected FET003 feature ID and version. |
| `rigid_body_roots` | Prims with `UsdPhysics.RigidBodyAPI` after repair. |
| `collider_prims` | Prims with collision APIs after repair. |
| `mass_source` | Source of authored mass values, or why mass repair was blocked. |
| `requirements_repaired` | Requirement IDs changed by this skill. |
| `requirements_blocked` | Requirement IDs that need user intent, property data, or upstream conversion. |
| `validation_report` | Path to the rerun validation report. |
| `next_step` | Usually the next failing profile feature or a blocked FET003 requirement. |

Keep the user-facing summary short: what rigid-body data changed, which FET003 variant was validated, what still fails, and the first validation gate that blocks progress.
