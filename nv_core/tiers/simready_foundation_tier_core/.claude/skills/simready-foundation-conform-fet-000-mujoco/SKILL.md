---
name: simready-foundation-conform-fet-000-mujoco
description: "Use for repairing exact CAP000_Core.MuJoCo SimReady conformance: the MuJoCo physics runtime variant scaffolding (MuJoCo variant set, runnables/physics/mujoco payload, and SimReady variant metadata). Use when a profile, validation report, or user request names CAP000_Core.MuJoCo; default `CAP000_Core.MuJoCo.0-2-0` (use `CAP000_Core.MuJoCo.0-1-0` when a profile pins it). Foundations 1 ID: FET_000_MUJOCO."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
    - core
---

# SimReady Conform CAP000_Core.MuJoCo

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

Use this exact capability skill when the selected profile, validation report, or user request names `CAP000_Core.MuJoCo`. It repairs or stages the MuJoCo physics runtime variant contract on top of neutral Core, without drifting into another runtime contract.

`CAP000_Core.MuJoCo` adds the MuJoCo runtime variant scaffolding to an asset that already satisfies neutral Core. It does not author MuJoCo rigid-body/collider physics itself; that belongs to `CAP003_RigidBody.MuJoCo` and related features. This skill only makes the `MuJoCo` variant set, its `runnables/physics/mujoco` payload, and its SimReady variant metadata correct.

Default to `CAP000_Core.MuJoCo.0-2-0` when the user asks for this capability without a version. Use `CAP000_Core.MuJoCo.0-1-0` when the profile, validation report, or user explicitly pins it. The two versions carry the same `RV.*` requirements; `0-2-0` depends on neutral `CAP000_Core.0-2-0` (which omits `NP.006` and `SR.001`) while `0-1-0` depends on neutral `CAP000_Core.0-1-0`. If the report names a different `CAP000_Core.<Runtime>` capability (`CAP000_Core.PhysX`, `CAP000_Core.Newton`), switch to that contract's matching skill before editing.

To conform an asset to a profile like `Robotics-Prop@3.1.0` that lists all three optional runtime variants, run all three `CAP000_Core.*` runtime skills so each of `PhysX`, `Newton`, and `MuJoCo` ends up with **both** a variant set on the default prim **and** a `SimReady_Metadata.Variants.Physics` entry. Never leave a `runnables/physics/<stem>.usd` payload on disk without its matching variant set and metadata — an orphaned payload fails `RV.007`/`RV.008`/`RV.009` for its runtime.

This skill is not the final validator and should not silently mutate source assets. It stages a repaired USD-family asset under the requested output directory, applies deterministic fixes only where safe, and stops when a validation gate still fails or a manual decision is required.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.MuJoCo.0-2-0.json` (latest)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.MuJoCo.0-1-0.json` (preserved)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.MuJoCo.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.0-2-0.json` (dependency; `CAP000_Core.0-1-0.json` for the `0-1-0` line)
- Requirement docs for the failing IDs under `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/`:
  - `mujoco-variant-set.md` (RV.007)
  - `mujoco-runtime-payload.md` (RV.008)
  - `mujoco-variant-metadata.md` (RV.009)
  - `runtime-variant-section-purity.md` (RV.010)
  - `runtime-physics-isolation.md` (RV.011)
- For the cross-runtime isolation policy that RV.010/RV.011 enforce, read
  `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/runtime-physics-isolation-matrix.md`.
- For the MuJoCo payload body (mesh collision authoring), read
  `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_rigid_bodies/requirements/mujoco-mesh-collision-api.md`
  and `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP003_RigidBody.MuJoCo.md`.

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs.

This skill is **self-contained**: the deterministic guidance and worked example below are sufficient to author a conforming `MuJoCo` runtime variant from scratch. You do not need to open an existing 3.1.0 asset and copy its structure — do so only to cross-check, and only against a sample known to pass.

Sample-asset caveats (do not copy structure blindly):

- Author from the requirement docs and the worked example below, not by copying an existing asset. Sample assets drift, and a stale or pre-contract sample will lead you astray. If you do cross-check, only trust a sample you have **just** confirmed passes the full target profile (RV.001–011 **and** AA.001, not the RV-only harness) — never treat any specific asset as a canonical template.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP000_Core.MuJoCo.0-2-0` | CAP000_Core.0-2-0 | `RV.007`, `RV.008`, `RV.009`, `RV.010`, `RV.011` |
| `CAP000_Core.MuJoCo.0-1-0` | CAP000_Core.0-1-0 | `RV.007`, `RV.008`, `RV.009`, `RV.010`, `RV.011` |

## Inputs

| Input | Requirement |
|---|---|
| `usd_asset` | Required USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` / `profile_version` | Validation target, if supplied. |
| `validation_report` | Preferred JSON/markdown report from the failing gate. |
| `mujoco_overrides` | Optional source of the MuJoCo runtime override data (schemas/attributes) to place in the payload; required to fully author `mujoco.usd` content. |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version.
2. Ensure the matching neutral Core gate (`CAP000_Core.0-2-0`, or `CAP000_Core.0-1-0` when the pinned version selects it) is in shape first; if Core fails, hand off to `simready-foundation-conform-fet-000-standard` before this skill.
3. Load the `CAP000_Core.MuJoCo` manifest, the capability markdown, and the RV.007-RV.009 + RV.010/RV.011 requirement docs (plus the isolation matrix).
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only `RV.007`, `RV.008`, `RV.009`, `RV.010`, and `RV.011` (see Feature Guidance). Do not touch PhysX/Newton variants or rigid-body physics.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate.
7. Summarize the selected version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

Repair each MuJoCo runtime variant requirement deterministically where safe:

- `RV.007` (variant set): On the stage `defaultPrim`, add a `MuJoCo` variant set with `Disabled` and `Enabled` options and author the default selection as `Disabled`. Keep the `Disabled` variant free of runtime payloads.
- `RV.008` (payload): From the `Enabled` variant, `prepend payload = @./runnables/physics/mujoco.usd@` (or `.usda`). The payload must live **inside the asset root** — the directory that holds the root layer — so keep `runnables/physics/` as a subfolder beside the root layer and anchor the arc with `./`. Do **not** place `runnables/` beside or above the asset root and reference it with `@../runnables/physics/mujoco.usd@`: a `../` payload that resolves above the asset root fails **AA.001** (atomic-asset anchored paths) and precludes `FET001_MinimalPlaceableVisual`, even though the RV.008 payload check alone still passes — so the RV-only local harness will not catch it. Create the `runnables/physics/mujoco.usd` layer as an `over` layer with the same `defaultPrim`. `.usd` and `.usda` are interchangeable; author `.usda` when a binary USDC cannot be compiled.
- `RV.009` (metadata): Add `customLayerData.SimReady_Metadata.Variants.Physics.MuJoCo = {prim = <defaultPrim path>, variantSetName = "MuJoCo", activateOption = "Enabled"}`. The `Variants` dict must live **inside** `SimReady_Metadata`, not as a sibling top-level `customLayerData.Variants` key.
- `RV.010` (variant-section purity): Keep the variant sections pure. The `Enabled` option must contain **only** the `prepend payload` arc — no inline `over`/`def` child prims, no authored properties, no other composition arcs. The `Disabled` option must be **completely empty**. Inline variant opinions outrank payloads in USD strength ordering (LIVRPS), so any override authored in a variant section leaks into the composed result of the *other* runtimes. All runtime data belongs in the `runnables/physics/mujoco.usd` payload, never in the root variant edit.
- `RV.011` (composed-stage isolation): The composed MuJoCo stage (MuJoCo `Enabled`, others `Disabled`) must carry only neutral `UsdPhysics`/`physics:*` data plus MuJoCo data (`Mjc*` schemas, `mjc:*` attributes). The inherited Newton collision base (`NewtonCollisionAPI`, `newton:contactGap`/`newton:contactMargin`) via `MjcCollisionAPI` and the inherited Newton mimic base (`NewtonMimicAPI`, `newton:mimicJoint`, `newton:mimicEnabled`, `newton:mimicCoef0`, `newton:mimicCoef1`) via `MjcEqualityJointAPI` are the only Newton schemas/attributes allowed; do not author any other `Newton*`/`newton:*`. Do not author PhysX (`Physx*`/`physx*:`) data. On a `MjcCollisionAPI` mesh, `physics:approximation` must be `convexHull` (MUJOCO.COL.002) — never `sdf` or `convexDecomposition`. RV.010/RV.011 are composition-wide checks: if a sibling runtime's section is impure or its payload leaks a foreign schema, report it rather than silently editing another runtime's contract.
- **Neutral-base precondition (RV.011 / MUJOCO.COL.002).** MuJoCo requires `physics:approximation = "convexHull"` on the collider, and the `mujoco.usd` `over` sets it. For that `over` to win, the neutral base collider must **not** author `physics:approximation` as a local (non-variant) opinion. A local base opinion outranks the payload arc in USD strength ordering (LIVRPS: Local > … > Payload), so a base `convexDecomposition`/`sdf` masks the required `convexHull` and fails MUJOCO.COL.002 under the MuJoCo selection (and leaks into the other runtimes). If the neutral base authors `physics:approximation`, clear that local opinion so each runnable owns its own value (PhysX `sdf`, MuJoCo `convexHull`, Newton `convexHull`). See the "Value-level attribute rules" in the isolation matrix.
- **Migrating a runtime-authored base (RV.011).** If the asset arrives with a different runtime authored directly on the neutral base — common when a prop was previously conformed to a single-runtime PhysX profile — the base collider carries that runtime's API schemas (e.g. `PhysxCollisionAPI`, `PhysxSDFMeshCollisionAPI`) alongside `PhysicsMeshCollisionAPI` and a local `physics:approximation`. Move that runtime data into its own runnable payload and reduce the neutral base collider to neutral `UsdPhysics` only (`PhysicsCollisionAPI` + `PhysicsMassAPI`), with the mesh-collision schema and approximation living in the per-runtime payloads. Otherwise the neutral (all-`Disabled`) composition still carries foreign runtime schemas and fails RV.011.

### MuJoCo payload body for a single-mesh prop

For a simple prop whose collision is a single existing mesh, the `mujoco.usd` payload body is a deterministic mesh-collision delta. Apply on the collision mesh `over`:

- `prepend apiSchemas = ["MjcCollisionAPI", "PhysicsMeshCollisionAPI", "MjcMeshCollisionAPI"]`
- `uniform token physics:approximation = "convexHull"` (required when `PhysicsMeshCollisionAPI` + `MjcCollisionAPI` are combined)
- `uniform int mjc:group = 2`
- `uniform token mjc:inertia = "convex"` (one of `legacy`, `convex`, `exact`, `shell`)
- `uniform int mjc:maxhullvert = -1` (>= -1; -1 means no limit)

Do not create geometry; only add schemas/attributes to the mesh(es) that already exist in the neutral base.

Block and report instead of guessing when:

- The asset needs MuJoCo joints, actuators, or scene/material tuning, or per-link collider decisions that are not the uniform delta below. Author the variant/payload scaffolding and hand that body work off to `CAP003_RigidBody.MuJoCo`/`CAP004_Multibody.MuJoCo`/`CAP022_DrivenJoints.MuJoCo` or the supplied `mujoco_overrides`. A plain multibody prop whose colliders all take the same delta is in scope — see "Multibody / multi-collider assemblies" below.
- The collision geometry or intended collider mesh is ambiguous.
- The asset has no `defaultPrim`, or the intended owning prim is ambiguous.

Keep joint/articulation/actuator MuJoCo physics work in `CAP003_RigidBody.MuJoCo`/`CAP004_Multibody.MuJoCo`; this skill owns the runtime variant scaffolding plus the collision delta — one collider mesh for a single-mesh prop, or every collider mesh for a multibody assembly (below).

### Multibody / multi-collider assemblies

When the neutral base is a multibody assembly — several rigid-body parts sharing one articulation (e.g. a toolbox with a hinged lid, handle, and locks) — the `mujoco.usd` payload is the same collision delta applied to **every** collider:

- Apply the mesh-collision `over` above (`MjcCollisionAPI`, `PhysicsMeshCollisionAPI`, `MjcMeshCollisionAPI` + `physics:approximation = "convexHull"` + `mjc:group`/`mjc:inertia`/`mjc:maxhullvert`) to **each** collider mesh in the assembly.
- Keep the payload collider-only: never re-author joints, articulation, actuators, or rigid bodies in `mujoco.usd` — that topology lives once on the neutral base.

Neutral-base preconditions for a multibody assembly (owned by `FET004_Multibody`/`CAP004_Multibody.MuJoCo`, repair there — not here):

- **Every** collider mesh must have its local `physics:approximation` cleared, so each runnable owns its own value (the `convexHull` above must win from the payload — MUJOCO.COL.002).
- The base carries the runtime-agnostic multibody topology (rigid bodies + `UsdPhysics` joints) and exactly one `PhysicsArticulationRootAPI`. If the topology or articulation root is missing, hand off to `FET004_Multibody`/`CAP004_Multibody.MuJoCo` before wiring the MuJoCo variant.

## Worked Example

See `references/mujoco-variant-example.md` for a complete four-edit worked
example (payload layer inside the asset root, nested
`SimReady_Metadata.Variants.Physics` entry, variant set, and the enabled
payload arc) for a single-mesh prop.

## Validation

The RV.007-RV.009 + RV.010/RV.011 checks live in `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/validation.py` and are generated into `simready.foundation.tier_core.requirements` as `RV_001`-`RV_011`. To run them locally:

1. Build the core tier wheel, which is what generates the `RV_001`-`RV_011` enums from the capability markdown: `repo.bat build_tiers` (writes `nv_core/tiers/simready_foundation_tier_core/_build/dist/simready_foundation_tier_core-*.whl`).
2. Create a Python 3.12 venv: `repo.bat uv venv --python 3.12 .venv_val`.
3. Install USD, the validator deps, and the tier wheel into it: `repo.bat uv pip install --python .venv_val usd-core usd-validation-nvidia numpy nv_core/tiers/simready_foundation_tier_core/_build/dist/simready_foundation_tier_core-*.whl`.
4. Invoke the venv Python directly (not `uv run`, which spawns its own venv) against a small harness that imports `simready.foundation.tier_core.rules_and_reqs.core.runtime_variants.validation`, calls `ResetCaches()` then `CheckStage(stage)` on each checker, and reads results via `checker.GetIssues()`. Installing the wheel puts the generated enums on the path, so no `PYTHONPATH` setup is needed.

Confirm the MuJoCo trio (`RV_007`/`RV_008`/`RV_009`) plus the isolation rules (`RV_010`/`RV_011`) pass on the `Disabled`-default stage. RV.011 recomposes each declared variant selection, so also spot-check that enabling MuJoCo composes only MuJoCo + neutral physics with `physics:approximation = "convexHull"`. If the environment cannot be bootstrapped, fall back to inspecting the staged USD for the variant set, anchored payload, nested `SimReady_Metadata.Variants.Physics.MuJoCo` entry, pure variant sections, and a MuJoCo-only payload, and report validation as inspection-only.

## Limitations

- Do not silently mutate the source asset; work on the requested staged output.
- Do not author PhysX or Newton variants in this skill.
- Keep runtime data out of the root variant sections (RV.010) and keep the MuJoCo payload free of PhysX schemas/attributes; use `physics:approximation = "convexHull"`, never `sdf`/`convexDecomposition` (RV.011).
- Do not create geometry; the single-mesh collision delta only annotates existing meshes.
- Beyond the deterministic single-mesh convexHull delta, do not invent MuJoCo runtime physics values (joints, actuators, scene/material tuning) that require domain knowledge; scaffold and hand off to `CAP003_RigidBody.MuJoCo`/`CAP004_Multibody.MuJoCo`/`CAP022_DrivenJoints.MuJoCo`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP000_Core.MuJoCo.0-2-0`. |
| `input` | Source asset or package inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass (subset of RV.007-RV.009, RV.010, RV.011). |
| `requirements_blocked` | Requirement IDs needing MuJoCo override data or user input. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or evidence needed. |
