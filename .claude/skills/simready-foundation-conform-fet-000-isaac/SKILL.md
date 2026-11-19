---
name: simready-foundation-conform-fet-000-isaac
description: "Use for repairing exact CAP000_Core.Isaac SimReady conformance: Isaac packaging Core (clean folder, thumbnail, physics attribute/schema source layer). Use when a profile, validation report, or user request names CAP000_Core.Isaac; default `CAP000_Core.Isaac.0-2-0` (use `CAP000_Core.Isaac.0-1-0` when a profile pins it). Foundations 1 ID: FET_000_ISAAC."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - isaac
    - core
---

# SimReady Conform CAP000_Core.Isaac

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP000_Core.Isaac`. It repairs or stages Isaac packaging Core on top of neutral Core, without drifting into robot identity or another runtime contract.

`CAP000_Core.Isaac` adds Isaac package cleanliness, thumbnail, and physics-layer placement expectations to an asset that already satisfies neutral Core. Robot naming, schema, type, and root-joint policy belong to `CAP021_RobotCore.Isaac`.

Default to `CAP000_Core.Isaac.0-2-0` when the user asks for this capability without a version. Use `CAP000_Core.Isaac.0-1-0` when the profile, validation report, or user explicitly pins it. The two versions carry the same `RC.*` requirements; `0-2-0` depends on neutral `CAP000_Core.0-2-0` (which omits `NP.006` and `SR.001`) while `0-1-0` depends on neutral `CAP000_Core.0-1-0`. If the report names a different `CAP000_Core.<Runtime>` capability, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.Isaac.0-2-0.json` (latest)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.Isaac.0-1-0.json` (preserved)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.Isaac.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.0-2-0.json` (dependency; `CAP000_Core.0-1-0.json` for the `0-1-0` line)
- Requirement docs under `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/isaac_sim/robot_core/requirements/`:
  - `clean-folder.md` (RC.001)
  - `thumbnail-exist.md` (RC.004)
  - `verify-robot-physics-attribute-source-layer.md` (RC.005)
  - `verify-robot-physics-schema-source-layer.md` (RC.006)

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP000_Core.Isaac.0-2-0` | CAP000_Core.0-2-0 | `RC.001`, `RC.004`, `RC.005`, `RC.006` |
| `CAP000_Core.Isaac.0-1-0` | CAP000_Core.0-1-0 | `RC.001`, `RC.004`, `RC.005`, `RC.006` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version.
2. Ensure the matching neutral Core gate (`CAP000_Core.0-2-0`, or `CAP000_Core.0-1-0` when the pinned version selects it) is in shape first; if Core fails, hand off to `simready-foundation-conform-fet-000-standard` before this skill.
3. Load the `CAP000_Core.Isaac` manifest, the capability markdown, and the RC.001/004/005/006 requirement docs.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only `RC.001`, `RC.004`, `RC.005`, and `RC.006`. Do not rewrite robot identity (`RC.003`, `RC.007`-`RC.009`).
6. Rerun the same profile gate or the narrowest available feature/capability validation gate.
7. Summarize the selected version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Keep only the interface asset and required subfolders at the package root; remove stray sibling files (`RC.001`).
- Place the thumbnail at `.thumbs/256x256/<asset-filename>.png` next to the validated root asset (`RC.004`). When an entrypoint USD is renamed to satisfy `RC.003`, rename or generate the matching `.thumbs/256x256/<new-asset-filename>.png` thumbnail as well.
- **Physics attribute and schema source-layer rules (`RC.005`, `RC.006`):**
  - `RC.005` (`VerifyRobotPhysicsAttributesSourceLayer`) and `RC.006` (`VerifyRobotPhysicsSchemaSourceLayer`) require every `physics:*` attribute (except `physics:collisionEnabled` on a prim with `PhysicsCollisionAPI`) and every `Physics*` or `Physx*` API schema in the stage's layer stack to be authored in a layer whose identifier ends with `physics.usd`, `physics.usda`, or `physics.usdc` (`r"physics\.usd[ac]?$"`).
  - Move any stray `PhysicsMassAPI`, `PhysicsRigidBodyAPI`, `PhysicsCollisionAPI`, `PhysicsMeshCollisionAPI`, `PhysicsJointStateAPI:<axis>`, or `physics:mass` / `physics:centerOfMass` / `physics:approximation` opinions out of `base.usda`, `instances.usda`, `robot.usda`, or the root `<robot>.usda` layer and into `payloads/Physics/physics.usda` (for example `UniversalRobots/ur30` `base_link` mass, `FrankaPanda` and `I2RT/yam` collider/mass overrides on `instances.usda`, and `PhysicsJointStateAPI` on `robot.usda`).
  - When `PhysicsCollisionAPI` / `PhysicsMeshCollisionAPI` must be applied to meshes inside an instanceable link reference (`I2RT/yam`), set `instanceable = false` on the link `over` inside `payloads/Physics/physics.usda` and apply the collider schemas there rather than in `payloads/instances.usda`.
- For robot identity failures, hand off to `simready-foundation-conform-fet-021-isaac`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP000_Core.Isaac.0-2-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
