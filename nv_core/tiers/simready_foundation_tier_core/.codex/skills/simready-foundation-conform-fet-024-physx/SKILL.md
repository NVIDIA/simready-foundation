---
name: simready-foundation-conform-fet-024-physx
description: "Use for repairing exact CAP024_BaseArticulation.PhysX SimReady conformance for PhysX base-articulation conformance. Use when a profile, validation report, or user request names CAP024_BaseArticulation.PhysX; default to `CAP024_BaseArticulation.PhysX.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_024_PHYSX."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
---

# SimReady Conform CAP024_BaseArticulation.PhysX

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP024_BaseArticulation.PhysX`. It repairs or stages PhysX base-articulation conformance without drifting into another runtime contract.

Default to `CAP024_BaseArticulation.PhysX.0-1-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.PhysX.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP024_BaseArticulation.PhysX.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP024_BaseArticulation.PhysX.0-1-0` | CAP024_BaseArticulation.0-1-0 | `BA.002` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP024_BaseArticulation.PhysX` manifest and the capability markdown before editing.
3. Load requirement docs linked from the capability markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `CAP024_BaseArticulation.PhysX` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `CAP024_BaseArticulation.PhysX` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `CAP024_BaseArticulation.PhysX` manifest and its dependencies.
- **Articulation root placement and PhysX self-collision tuning (`BA.001`, `BA.002`, and runtime sweep/coordination stability):**
  - Ensure exactly one prim in the composed stage carries `PhysicsArticulationRootAPI` (`BA.001`) and apply `PhysxArticulationAPI` on that same articulation root prim in `runnables/physics/physx.usda`.
  - If placing `PhysicsArticulationRootAPI` on `base_link` while `root_joint` targets a non-rigid defaultPrim (`body0 = </Robot>`) causes PhysX to simulate the robot as a floating base (`fixed_base = false`), move `PhysicsArticulationRootAPI` and `PhysxArticulationAPI` onto the fixed `root_joint` in `runnables/physics/physx.usda` and delete `PhysicsArticulationRootAPI` from `base_link` in `physx.usda` (as on `Addverb/Syncro5`).
  - Diagnose non-adjacent or adjacent link collision overlaps (`BA.002` or self-collision locking during sweeps) by inspecting the collider approximations (`convexHull` vs. `convexDecomposition` / `sdf`) and `physics:filteredPairs` first. Only author `bool physxArticulation:enabledSelfCollisions = 0` on the `PhysxArticulationAPI` prim in `runnables/physics/physx.usda` when source evidence or the asset's collider design (such as coarse bounding hulls that overlap across adjacent links without `filteredPairs`, as in the `Addverb/Syncro*` or `Yaskawa/NEX*` examples) establishes that articulation-wide self-collision is unintended; do not disable intended self-collision behavior merely to make a test pass, and prefer refining a self-obstructing concave link collider from `convexHull` to `sdf` or `convexDecomposition` (as in the `NHC12` example) when self-collision is intended.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP024_BaseArticulation.PhysX.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
