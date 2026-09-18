---
name: simready-foundation-conform-fet-000-physx
description: "Use for repairing exact FET_000_PHYSX SimReady conformance: the PhysX physics runtime variant scaffolding (PhysX variant set, runnables/physics/physx payload, and SimReady variant metadata). Use when a profile, validation report, or user request names FET_000_PHYSX; default to version `0.1.0`."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - physx
    - core
---

# SimReady Conform FET_000_PHYSX

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_000_PHYSX`. It repairs or stages the PhysX physics runtime variant contract on top of neutral Core, without drifting into another runtime contract.

`FET_000_PHYSX` adds the PhysX runtime variant scaffolding to an asset that already satisfies neutral Core (`FET_000_STANDARD@0.1.0`). It does not author PhysX rigid-body/collider physics itself; that belongs to `FET_003_PHYSX` and related features. This skill only makes the `PhysX` variant set, its `runnables/physics/physx` payload, and its SimReady variant metadata correct.

Default to `FET_000_PHYSX@0.1.0` when the user asks for this feature without a version. If the report names a different `FET_000_<RUNTIME>` feature (`FET_000_NEWTON`, `FET_000_MUJOCO`), switch to that feature's matching skill before editing.

To conform an asset to a profile like `Robotics-Prop@3.1.0` that lists all three optional runtime variants, run all three `FET_000_*` runtime skills so each of `PhysX`, `Newton`, and `MuJoCo` ends up with **both** a variant set on the default prim **and** a `SimReady_Metadata.Variants.Physics` entry. Never leave a `runnables/physics/<stem>.usd` payload on disk without its matching variant set and metadata — an orphaned payload fails `RV.007`/`RV.008`/`RV.009` for its runtime.

This skill is not the final validator and should not silently mutate source assets. It stages a repaired USD-family asset under the requested output directory, applies deterministic fixes only where safe, and stops when a validation gate still fails or a manual decision is required.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_PHYSX-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_PHYSX.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_000_STANDARD-0.1.0.json` (dependency)
- Requirement docs for the failing IDs under `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/runtime_variants/requirements/`:
  - `physx-variant-set.md` (RV.001)
  - `physx-runtime-payload.md` (RV.002)
  - `physx-variant-metadata.md` (RV.003)
  - `runtime-variant-section-purity.md` (RV.010)
  - `runtime-physics-isolation.md` (RV.011)
- For the cross-runtime isolation policy that RV.010/RV.011 enforce, read
  `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/runtime_variants/runtime-physics-isolation-matrix.md`.
- For the PhysX payload body (mesh collision authoring), read
  `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/physics_bodies/physics_rigid_bodies/requirements/physx-collider-mesh.md`
  and `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_PHYSX.md`.

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs.

This skill is **self-contained**: the deterministic guidance and worked example below are sufficient to author a conforming `PhysX` runtime variant from scratch. You do not need to open an existing 3.1.0 asset and copy its structure — do so only to cross-check, and only against a sample known to pass.

Sample-asset caveats (do not copy structure blindly):

- Author from the requirement docs and the worked example below, not by copying an existing asset. Sample assets drift, and a stale or pre-contract sample will lead you astray. If you do cross-check, only trust a sample you have **just** confirmed passes the full target profile (RV.001–011 **and** AA.001, not the RV-only harness) — never treat any specific asset as a canonical template.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_000_STANDARD@0.1.0 | `RV.001`, `RV.002`, `RV.003`, `RV.010`, `RV.011` |

## Inputs

| Input | Requirement |
|---|---|
| `usd_asset` | Required USD-family asset to repair. |
| `output_root` | Required or inferred folder for staged assets and reports. |
| `simready_profile` / `profile_version` | Validation target, if supplied. |
| `validation_report` | Preferred JSON/markdown report from the failing gate. |
| `physx_overrides` | Optional source of the PhysX runtime override data (schemas/attributes) to place in the payload; required to fully author `physx.usd` content. |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version.
2. Ensure the neutral Core gate (`FET_000_STANDARD@0.1.0`) is in shape first; if Core fails, hand off to `simready-foundation-conform-fet-000-standard` before this skill.
3. Load the `FET_000_PHYSX` manifest, the feature markdown, and the RV.001-RV.003 + RV.010/RV.011 requirement docs (plus the isolation matrix).
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only `RV.001`, `RV.002`, `RV.003`, `RV.010`, and `RV.011` (see Feature Guidance). Do not touch Newton/MuJoCo variants or rigid-body physics.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate.
7. Summarize the selected version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

Repair each PhysX runtime variant requirement deterministically where safe:

- `RV.001` (variant set): On the stage `defaultPrim`, add a `PhysX` variant set with `Disabled` and `Enabled` options and author the default selection as `Disabled`. Keep the `Disabled` variant free of runtime payloads.
- `RV.002` (payload): From the `Enabled` variant, `prepend payload = @./runnables/physics/physx.usd@` (or `.usda`). The payload must live **inside the asset root** — the directory that holds the root layer — so keep `runnables/physics/` as a subfolder beside the root layer and anchor the arc with `./`. Do **not** place `runnables/` beside or above the asset root and reference it with `@../runnables/physics/physx.usd@`: a `../` payload that resolves above the asset root fails **AA.001** (atomic-asset anchored paths) and precludes `FET_001_STANDARD`, even though the RV.002 payload check alone still passes — so the RV-only local harness will not catch it. Create the `runnables/physics/physx.usd` layer as an `over` layer with the same `defaultPrim`. `.usd` and `.usda` are interchangeable; author `.usda` when a binary USDC cannot be compiled.
- `RV.003` (metadata): Add `customLayerData.SimReady_Metadata.Variants.Physics.PhysX = {prim = <defaultPrim path>, variantSetName = "PhysX", activateOption = "Enabled"}`. The `Variants` dict must live **inside** `SimReady_Metadata`, not as a sibling top-level `customLayerData.Variants` key.
- `RV.010` (variant-section purity): Keep the variant sections pure. The `Enabled` option must contain **only** the `prepend payload` arc — no inline `over`/`def` child prims, no authored properties, no other composition arcs. The `Disabled` option must be **completely empty**. Inline variant opinions outrank payloads in USD strength ordering (LIVRPS), so any override authored in a variant section leaks into the composed result of the *other* runtimes. All runtime data belongs in the `runnables/physics/physx.usd` payload, never in the root variant edit.
- `RV.011` (composed-stage isolation): The composed PhysX stage (PhysX `Enabled`, others `Disabled`) must carry only neutral `UsdPhysics`/`physics:*` data plus PhysX data (`Physx*` schemas, `physx*:` attributes). Do not author Newton (`Newton*`/`newton:*`) or MuJoCo (`Mjc*`/`mjc:*`) schemas/attributes in `physx.usd`. `physics:approximation` may use any valid PhysX token (e.g. `sdf` paired with `PhysxSDFMeshCollisionAPI`). RV.010/RV.011 are composition-wide checks: if a sibling runtime's section is impure or its payload leaks a foreign schema, report it rather than silently editing another runtime's contract.
- **Neutral-base precondition (RV.011).** For the `physx.usd` `over` to actually set `physics:approximation = "sdf"`, the neutral base collider must **not** author `physics:approximation` as a local (non-variant) opinion. A local base opinion outranks the payload arc in USD strength ordering (LIVRPS: Local > … > Payload), so a base value both masks the runtime value and leaks into every runtime composition — e.g. a base `convexDecomposition` surfaces as an inert-leak warning under Newton, and a base `sdf` fails the neutral base. If the neutral base authors `physics:approximation`, clear that local opinion so each runnable owns its own value (PhysX `sdf`, MuJoCo `convexHull`, Newton none). See the "Value-level attribute rules" in the isolation matrix.
- **Migrating a runtime-authored base (RV.011).** If the asset arrives with PhysX authored directly on the neutral base — common when a prop was previously conformed to a single-runtime PhysX profile — the base collider also carries the PhysX API schemas (`PhysxCollisionAPI`, `PhysxSDFMeshCollisionAPI`) alongside `PhysicsMeshCollisionAPI` and the local `physics:approximation`. Move that runtime data into `physx.usd` and reduce the neutral base collider to neutral `UsdPhysics` only (`PhysicsCollisionAPI` + `PhysicsMassAPI`), with the mesh-collision schema and approximation living in the runnable payload. Otherwise the neutral (all-`Disabled`) composition still carries `Physx*` schemas and fails RV.011.

### PhysX payload body for a single-mesh prop

For a simple prop whose collision is a single existing mesh, the `physx.usd` payload body is a deterministic mesh-collision delta. Apply on the collision mesh `over`:

- `prepend apiSchemas = ["PhysxCollisionAPI", "PhysxSDFMeshCollisionAPI", "PhysicsMeshCollisionAPI"]`
- `custom token physics:approximation = "sdf"` (SDF mesh collision, PhysX's accurate collider approximation for a static/kinematic prop mesh)

Do not create geometry; only add schemas/attributes to the mesh(es) that already exist in the neutral base.

Block and report instead of guessing when:

- The asset needs PhysX joints, drives, or scene/material tuning, or per-link collider approximation decisions that are not the uniform delta below (e.g. some links convex, others SDF). Author the variant/payload scaffolding and hand that body work off to `FET_003_PHYSX`/`FET_004_PHYSX`/`FET_022_PHYSX` or the supplied `physx_overrides`. A plain multibody prop whose colliders all take the same delta is in scope — see "Multibody / multi-collider assemblies" below.
- The collision geometry or intended collider mesh is ambiguous.
- The asset has no `defaultPrim`, or the intended owning prim is ambiguous.

Keep joint/articulation/drive PhysX physics work in `FET_003_PHYSX`/`FET_004_PHYSX`; this skill owns the runtime variant scaffolding plus the collision delta — one collider mesh for a single-mesh prop, or every collider mesh for a multibody assembly (below).

### Multibody / multi-collider assemblies

When the neutral base is a multibody assembly — several rigid-body parts sharing one articulation (e.g. a toolbox with a hinged lid, handle, and locks) — the `physx.usd` payload is the same collision delta applied to **every** collider:

- Apply the mesh-collision `over` above (`PhysxCollisionAPI`, `PhysxSDFMeshCollisionAPI`, `PhysicsMeshCollisionAPI` + `physics:approximation = "sdf"`) to **each** collider mesh in the assembly.
- Keep the payload collider-only: never re-author joints, drives, articulation, or rigid bodies in `physx.usd` — that topology lives once on the neutral base.

Neutral-base preconditions for a multibody assembly (owned by `FET_004_STANDARD`/`FET_004_PHYSX`, repair there — not here):

- **Every** collider mesh must have its local `physics:approximation` cleared, so each runnable owns its own value (the `sdf` above must win from the payload).
- The base carries the runtime-agnostic multibody topology (rigid bodies + `UsdPhysics` joints) and exactly one `PhysicsArticulationRootAPI`. If the topology or articulation root is missing, hand off to `FET_004_STANDARD`/`FET_004_PHYSX` before wiring the PhysX variant.

## Worked Example: single-mesh prop

Add the `PhysX` variant to a single-mesh prop in four edits (illustrated with a `RootNode`-rooted prop; substitute your asset's `defaultPrim` and collider mesh path). This is authored from the requirement docs — it does not depend on any existing asset.

1. Create the payload layer `runnables/physics/physx.usd` **inside the asset root**, in a `runnables/physics/` subfolder beside the root layer (e.g. `simready_usd/runnables/physics/physx.usd`), with the same `defaultPrim` as the root asset. Do not place `runnables/` outside the asset root — the `./`-anchored payload below must resolve within it (AA.001). Standardize on binary `.usd`; author the equivalent `.usda` below and export it to `.usd` (e.g. `Sdf.Layer.FindOrOpen("physx.usda").Export("physx.usd")`), or keep `.usda` if a binary cannot be compiled:

```usd
#usda 1.0
(
    defaultPrim = "RootNode"
    doc = """PhysX overrides for sm_obs_orange_a02_01.usda"""
)

over "RootNode"
{
    over "Geometry"
    {
        over "obs_orange_01_obj_01"
        {
            over "obs_orange_01_mesh_01" (
                prepend apiSchemas = ["PhysxCollisionAPI", "PhysxSDFMeshCollisionAPI", "PhysicsMeshCollisionAPI"]
            )
            {
                custom token physics:approximation = "sdf"
            }
        }
    }
}
```

2. In the root asset layer, add the `PhysX` entry to `customLayerData.SimReady_Metadata.Variants.Physics` (alongside any `Newton`/`MuJoCo` entries). The `Variants` dict lives **inside** `SimReady_Metadata`, never as a sibling top-level `customLayerData.Variants` key:

```usd
"PhysX" = {
    string prim = "/RootNode"
    string variantSetName = "PhysX"
    string activateOption = "Enabled"
}
```

3. On `RootNode`, add `"PhysX"` to `prepend variantSets` and add its default selection to `variants` (`string PhysX = "Disabled"`).

4. Add the `variantSet "PhysX"` block with a payload-free `Disabled` option and an `Enabled` option that prepends the payload:

```usd
variantSet "PhysX" = {
    "Disabled" {
    }
    "Enabled" (
        prepend payload = @./runnables/physics/physx.usd@
    ) {
    }
}
```

Note that the `Enabled` option holds only the payload arc and the `Disabled` option is empty (RV.010), and the payload authors only PhysX + neutral data (RV.011).

## Validation

The RV.001-RV.003 + RV.010/RV.011 checks live in `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/runtime_variants/validation.py` and are generated into `simready.foundation.tier_core.requirements` as `RV_001`-`RV_011`. To run them locally:

1. Build the core tier wheel, which is what generates the `RV_001`-`RV_011` enums from the capability markdown: `repo.bat build_tiers` (writes `nv_core/tiers/simready_foundation_tier_core/_build/dist/simready_foundation_tier_core-*.whl`).
2. Create a Python 3.12 venv: `repo.bat uv venv --python 3.12 .venv_val`.
3. Install USD, the validator deps, and the tier wheel into it: `repo.bat uv pip install --python .venv_val usd-core usd-validation-nvidia numpy nv_core/tiers/simready_foundation_tier_core/_build/dist/simready_foundation_tier_core-*.whl`.
4. Invoke the venv Python directly (not `uv run`, which spawns its own venv) against a small harness that imports `simready.foundation.tier_core.capabilities.core.runtime_variants.validation`, calls `ResetCaches()` then `CheckStage(stage)` on each checker, and reads results via `checker.GetIssues()`. Installing the wheel puts the generated enums on the path, so no `PYTHONPATH` setup is needed.

Confirm the PhysX trio (`RV_001`/`RV_002`/`RV_003`) plus the isolation rules (`RV_010`/`RV_011`) pass on the `Disabled`-default stage. RV.011 recomposes each declared variant selection, so also spot-check that enabling PhysX composes only PhysX + neutral physics. If the environment cannot be bootstrapped, fall back to inspecting the staged USD for the variant set, anchored payload, nested `SimReady_Metadata.Variants.Physics.PhysX` entry, pure variant sections, and a PhysX-only payload, and report validation as inspection-only.

## Limitations

- Do not silently mutate the source asset; work on the requested staged output.
- Do not author Newton or MuJoCo variants in this skill.
- Keep runtime data out of the root variant sections (RV.010) and keep the payload free of Newton/MuJoCo schemas/attributes (RV.011).
- Do not create geometry; the single-mesh collision delta only annotates existing meshes.
- Beyond the deterministic single-mesh SDF delta, do not invent PhysX runtime physics values (joints, drives, scene/material tuning) that require domain knowledge; scaffold and hand off to `FET_003_PHYSX`/`FET_004_PHYSX`/`FET_022_PHYSX`.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_000_PHYSX@0.1.0`. |
| `input` | Source asset or package inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass (subset of RV.001-RV.003, RV.010, RV.011). |
| `requirements_blocked` | Requirement IDs needing PhysX override data or user input. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or evidence needed. |
