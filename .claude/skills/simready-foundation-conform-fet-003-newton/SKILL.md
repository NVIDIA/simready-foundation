---
name: simready-foundation-conform-fet-003-newton
description: "Use for repairing exact FET_003_NEWTON SimReady conformance for rigid body physics (newton) conformance. Use when a profile, validation report, or user request names FET_003_NEWTON; default to version `0.1.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
---

# SimReady Conform FET_003_NEWTON

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_003_NEWTON`. It repairs or stages rigid body physics (newton) conformance without drifting into another runtime contract.

Default to `FET_003_NEWTON@0.1.0` when the user asks for this feature without a version. Use an older integer version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_NEWTON-0.1.0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_003_NEWTON.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | None | `RB.COL.001`, `RB.COL.002`, `RB.COL.003`, `RB.COL.004`, `RB.001`, `RB.003`, `RB.005`, `RB.007`, `RB.009`, `RB.010`, `NEWTON.COL.001`, `NEWTON.COL.002`, `NEWTON.MAS.001`, `NEWTON.MAT.001` |

## Feature Adapter

When the input already conforms to the neutral base feature, prefer the deterministic feature adapter to author the runtime-specific data first (via the `workspace upgrade` command; see `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`), then repair only the residual requirements below.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_newton` | `rigid_body_neutral_to_prop_newton` | `FET_003_STANDARD@0.1.0` -> `FET_003_NEWTON@0.1.0` | Mesh extents; `NewtonCollisionAPI` + `NewtonMeshCollisionAPI` on existing colliders; `newton:contactGap = 0`; `NewtonMaterialAPI` + default friction tuning on bound physics materials. Satisfies `NEWTON.COL.001`/`NEWTON.COL.002`/`NEWTON.MAT.001`. |

- The adapter runs on a staged output stage and never creates geometry; it only annotates existing colliders.
- It authors `NewtonMeshCollisionAPI` (not `NewtonSDFCollisionAPI`). If the collider needs SDF-backed collision, or the base `RB.*` rigid-body data is missing, repair that manually per the Workflow below. Strict Newton isolation: do not author `Mjc*`/`Physx*` data or `physics:approximation = "sdf"`.

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_003_NEWTON` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_003_NEWTON` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_003_NEWTON` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- **`NewtonCollisionAPI`** carries the shared contact tuning: `newton:contactMargin`
  (default `0`, outward surface inflation) and `newton:contactGap` (default `-inf` = engine
  default; the samples author `0`). Both must be non-negative when authored.
- **`NewtonMeshCollisionAPI`** is the ordinary mesh path (it inherits `NewtonCollisionAPI`).
  Newton reads the inherited `physics:approximation`; keep it at the intended value
  (`convexHull`, `convexDecomposition`, ...). `newton:maxHullVertices` (default `-1` = exact
  hull, minimum `-1`) only matters when `physics:approximation = "convexHull"`.
- **`NewtonSDFCollisionAPI`** is the SDF/hydroelastic path. It is mutually exclusive with
  `NewtonMeshCollisionAPI` on the same prim. When SDF tuning is authored, keep contact
  distances/padding non-negative, `newton:sdfMaxResolution` a positive multiple of 8,
  `newton:sdfTextureFormat` one of `uint8`/`uint16`/`float32`, and
  `newton:sdfNarrowBandInner < newton:sdfNarrowBandOuter`. Do not guess SDF tuning values
  when source data or policy is missing.
- **Hydroelastic contact** (`newton:hydroelasticEnabled`, bool; `newton:hydroelasticStiffness`,
  positive) is Newton-only (no PhysX equivalent to port). `newton:hydroelasticStiffness` alone
  does not enable it. When `newton:hydroelasticEnabled = true`, author an SDF source
  (`newton:sdfMaxResolution` or `newton:sdfTargetVoxelSize`) on the same prim — Newton requires
  one at parse time unless the mesh carries an attached `mesh.sdf` (a missing source is a warning,
  not a hard failure).
- **`NewtonMassAPI`** (`NEWTON.MAS.001`) is optional and applies on an `Xformable` (rigid body
  or collision `Gprim`), extending `PhysicsMassAPI`. Author it only to override neutral mass
  resolution: `newton:inertia` must be empty (no opinion) or exactly 6 finite elements
  `[Ixx, Iyy, Izz, Ixy, Ixz, Iyz]` with non-negative diagonal; `newton:massModel` is `solid` or
  `shell`; `newton:shellThickness` (default `-inf` = solver chooses) must be finite and `> 0` when
  authored, and only matters under the `shell` model. Do not invent inertia values — derive them
  from source data or leave the attribute empty.
- **`NewtonMaterialAPI`** (`NEWTON.MAT.001`) applies on the `UsdShade.Material` bound to the
  collider via `material:binding:physics`, extending `PhysicsMaterialAPI`. Aligned with the
  `UsdPhysicsMaterialAPI` convention (`PMT.001`), validation checks **placement only**: the
  schema must sit on a `UsdShade.Material` that also carries `PhysicsMaterialAPI`. The Newton
  tuning attributes (`newton:torsionalFriction` default `0.005`, `newton:rollingFriction`
  default `0.0001`, and the `newton:contact*` attributes, default `-inf` = engine default) are
  trusted, not value-checked — author them as needed, or leave the contact attributes at the
  `-inf` sentinel (equivalent to omitting them).
- Strict Newton isolation (RV.011): do not author `Mjc*` / `Physx*` schemas or attributes,
  and do not set `physics:approximation = "sdf"` (use `NewtonSDFCollisionAPI` instead).

## Samples

- `sample_content/common_assets/props_general/obs_orange_a02/runnables/physics/newton.usd` -
  single-mesh prop collider with `NewtonMeshCollisionAPI`, `physics:approximation = "convexHull"`,
  `newton:maxHullVertices = -1`, and `newton:contactGap = 0`; and the bound physics material
  with `NewtonMaterialAPI` authoring all six Newton material attributes at their defaults.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_003_NEWTON@0.1.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
