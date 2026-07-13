# SimReady AI Context

This file is durable project context for AI assistants working on
`simready-foundation`. Read it before making changes to SimReady specs,
features, profiles, or validation.

## Core Mental Model

SimReady Foundations is a framework for defining what "Sim Ready" means for
OpenUSD assets. The main documentation and spec content lives under:

`nv_core/sr_specs/docs`

The framework is built from four connected concepts:

- **Requirements** are atomic, testable rules with stable IDs, such as
  `UN.006`, `VG.014`, `RB.001`, or `DJ.011`.
- **Capabilities** group related requirements by domain, such as Core,
  Visualization, Physics Bodies, Isaac Sim, Hierarchy, Non-Visual Sensors, and
  Semantic Labels.
- **Features** are runtime/use-case contracts. A feature is usually defined by
  what an asset must do in a runtime, such as being minimal/placeable/visual,
  graspable by a robotic gripper, physically simulated, articulated, or usable
  in Isaac Sim.
- **Profiles** are named, versioned bundles of features for asset classes or
  target environments, such as Sim Ready props, PhysX props, Isaac-ready props,
  or robot bodies.

Validation ties these together. Each feature should have validation tests or a
clear validation strategy that proves an asset actually implements the required
behavior.

## Workflow From Guides

`nv_core/sr_specs/docs/guides/guides.md` is the entrypoint for the practical
workflow. It links the four guide areas that should shape spec work:

- **Features** (`guides/features/features.md`): a feature is a versioned bundle
  of requirement IDs plus documentation. A feature change normally requires a
  markdown file, a JSON manifest, requirement links, samples where useful, a
  validation strategy, and an entry in `docs/features/features.md`.
- **Profiles** (`guides/profiles/profiles.md`): a profile is a named, versioned
  list of exact feature versions in `docs/profiles/profiles.toml`. Existing
  profile versions are immutable. To adopt new feature behavior, add a new
  profile version and update the related profile markdown/index docs.
- **Feature adapters** (`guides/feature_adapters/feature_adapters.md`): adapters
  mutate assets from one feature/profile contract to another. Create or update
  adapters only when the conversion requires USD data changes, and make sure
  every feature difference between source and target profiles has a direct
  adapter path.
- **Runtime testing** (`guides/runtime_testing/runtime_testing.md`): runtime
  tests provide behavioral proof beyond static validators. The pipeline is
  `batch_maker` to generate jobs, `job_runner` to execute them, and
  `report_generator` to create JSON/HTML reports. Prefer `workspace
  runtime_tests` inside Kit. Generated job JSON should not be hand-edited.

Feature expansion has a specific meaning in these guides: a technology-specific
feature can replace a base requirement when the technology supports a valid
pattern that the base rule would reject. In that case, the tech feature should
carry an explicit full requirement list with the replaced base requirement
removed and the technology-specific requirement added; profiles choose which
feature applies.

## First-Read Path for AI Agents

When an AI agent is new to this repository or returning after a context reset,
use this read order before changing specs, profiles, validators, or skills:

1. `AGENTS.md` - durable repo context and current workflow rules.
2. `nv_core/sr_specs/docs/guides/guides.md` - guide index.
3. `nv_core/sr_specs/docs/guides/features/features.md` - feature structure,
   versioning, dependencies, and feature expansion.
4. `nv_core/sr_specs/docs/guides/profiles/profiles.md` - profile structure,
   `profiles.toml`, profile versioning, and feature bundles.
5. `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md` - how
   assets are mutated between feature/profile contracts.
6. `nv_core/sr_specs/docs/guides/runtime_testing/runtime_testing.md` - runtime
   validation entrypoint and links to job runner details.
7. The specific profile, feature, requirement, and validator files touched by
   the task.

Treat `nv_core/sr_specs/docs/profiles/profiles.toml` as the machine-readable
profile source of truth. Profile markdown is an authoring guide and must stay
in sync with `profiles.toml`, but validators consume the TOML feature list.

## Prop-Robotics Profile Workflow

The prop robotics profiles are the main current workflow targets:

- `Prop-Robotics-Neutral`: OpenUSD-neutral prop assets for robotics pipelines.
  The base profile validates Core, Minimal, rigid-body physics, grasp physics,
  and materials. Single-rigid-body props satisfy prop physics through
  `FET003_BASE_NEUTRAL`; `FET004_BASE_NEUTRAL` is separate multibody work and
  should be validated only for props intentionally authored with multiple rigid
  bodies and joints.
- `Prop-Robotics-Physx`: PhysX prop assets. This profile uses PhysX rigid-body
  and multibody feature variants, including PhysX collider and joint behavior.
- `Prop-Robotics-Isaac`: Isaac Sim composition plus PhysX prop physics. This
  profile adds Isaac composition requirements on top of the prop physics and
  grasp expectations.

When reasoning about a prop profile, inspect these files together:

- `nv_core/sr_specs/docs/profiles/profiles.toml`
- `nv_core/sr_specs/docs/profiles/prop-robotics-neutral.md`
- `nv_core/sr_specs/docs/profiles/prop-robotics-physx.md`
- `nv_core/sr_specs/docs/profiles/prop-robotics-isaac.md`
- `nv_core/sr_specs/docs/features/feature-dependency-graph.md`
- The selected feature JSON manifests under `nv_core/sr_specs/docs/features/`

Run conformance work one feature gate at a time. The normal prop repair order is:

```text
validate selected profile
-> simready-foundation-conform-fet-000-core
-> simready-foundation-conform-fet-001-minimal
-> simready-foundation-conform-fet-003-rigid-body-physics
-> simready-foundation-conform-fet-004-simulate-multi-body-physics (only when the selected profile or asset intent requires multibody physics)
-> simready-foundation-conform-fet-005-simulate-grasp-physics
-> simready-foundation-conform-fet-006-materials
-> validate selected profile again
```

For FET004 multibody work, use `simready-foundation-conform-fet-004-simulate-multi-body-physics`
after the FET003 rigid-body gate and before grasp/material work. This skill must
not create geometry to pass the multibody feature; it may only use existing USD
geometry/part hierarchy and repair physics schemas, joints, articulations, and
relationships. For single-rigid-body props, FET004 is not applicable unless the
user or selected profile explicitly requires a multibody assembly.

When a selected profile or user request explicitly includes FET007 non-visual
sensor materials, run `simready-foundation-conform-fet-007-nonvisual-materials` after `simready-foundation-conform-fet-006-materials`. FET007 is not
currently part of the default prop robotics profile list.

For Robot-Body-Runnable or Robot-Body-Isaac workflows, use `simready-foundation-conform-fet-021-robot-core`
for the robot core gate after the multibody physics gate is in shape and before
driven-joint, articulation, or Isaac-composition follow-up work.

Use `simready-foundation-conform-fet-024-base-articulation` for the base articulation gate once the robot body/joint
topology is in shape. The neutral variant checks the single articulation root;
the PhysX variant also needs PhysX collision-clearance evidence for
non-adjacent links.

When an Isaac robot workflow explicitly includes FET023 robot material
organization, use `simready-foundation-conform-fet-023-robot-materials` after visual material conformance and before
final Robot-Body validation. FET023 is not currently part of the default
Robot-Body profiles.

Stop at the first failing feature gate unless the user explicitly asks for a
broader best-effort pass. Count a feature skill as successful when its selected
feature passes, even if the full profile still fails on a later or unrelated
feature.

Current repo-local skills live under the agent-agnostic skill tree:

```text
skills/<skill-name>/SKILL.md
```

`.agents/skills`, `.codex/skills`, and `.claude/skills` are compatibility
links to `../skills`. When updating a SimReady skill, edit the `skills` source
of truth, including bundled `references/`, `assets/`, `evals/`, and
`assets/openai.yaml` metadata. Deterministic helper scripts are bundled under
`assets/scripts/` in this repository so the external `nv-base` skill validator
does not treat tool helpers as top-level skill structure.

| Skill | Purpose |
|---|---|
| `simready-foundation-conform-fet-000-core` | Repair Core metadata, naming/path, asset layout, unresolved path, and undefined prim failures. |
| `simready-foundation-conform-fet-001-minimal` | Repair Minimal/Base Neutral stage metadata, units, hierarchy, geometry, and mesh-quality failures. |
| `simready-foundation-conform-fet-003-rigid-body-physics` | Repair rigid-body and collider conformance for Neutral or PhysX FET003 variants. |
| `simready-foundation-conform-fet-004-simulate-multi-body-physics` | Repair multibody rigid-body, joint, and articulation conformance without creating new geometry. |
| `simready-foundation-conform-fet-005-simulate-grasp-physics` | Author or repair vision-guided grasp vector lines and related FET005 grasp physics issues. |
| `simready-foundation-conform-fet-006-materials` | Repair material bindings, USDPreview/MDL shader schema, texture path, size, and color-space issues for FET006 variants. |
| `simready-foundation-conform-fet-007-nonvisual-materials` | Repair non-visual sensor material attributes on bound materials for FET007. |
| `simready-foundation-conform-fet-021-robot-core` | Repair Robot Core runnable or Isaac robot metadata, schema, naming, thumbnails, and root-joint pinning. |
| `simready-foundation-conform-fet-023-robot-materials` | Repair robot material organization by flattening materials under the top-level Looks scope. |
| `simready-foundation-conform-fet-024-base-articulation` | Repair base articulation root placement and PhysX non-adjacent collision clearance issues. |

Repo-local spec authoring skills also live in `skills`:

| Skill | Purpose |
|---|---|
| `simready-foundation-add-requirement` | Add a new atomic requirement under an existing capability, with detailed docs, examples, index registration, and validator/feature follow-up. |
| `simready-foundation-update-requirement` | Revise requirement docs or semantics while preserving stable IDs and coordinating validator/feature/profile impact. |
| `simready-foundation-add-capability` | Add a new capability folder with overview docs, requirements index, validation module planning, and registration updates. |
| `simready-foundation-update-capability` | Maintain existing capability docs, requirement indexes, validators, imports, and feature references. |
| `simready-foundation-add-validator` | Implement executable validation for documented requirement IDs in a capability `validation.py`. |
| `simready-foundation-update-validator` | Repair validator behavior, failure messages, edge cases, and doc drift without changing contracts silently. |
| `simready-foundation-add-feature` | Add a brand-new feature markdown page, JSON manifest, requirement mapping, feature index entry, dependency notes, and optional profile adoption plan. |
| `simready-foundation-update-feature` | Add a new version of an existing feature or make safe editorial fixes while preserving published feature versions. |
| `simready-foundation-add-profile` | Add a brand-new profile with an initial `profiles.toml` feature bundle, profile markdown, index entry, and adapter/validation notes. |
| `simready-foundation-update-profile` | Add a new version of an existing profile while preserving old profile versions and synchronizing TOML, profile docs, and index docs. |
| `simready-foundation-add-feature-adapter` | Add a direct asset mutation path between exact feature/profile versions under `nv_core/cip_specs/asset_handler_modules`. |
| `simready-foundation-update-feature-adapter` | Repair or extend existing feature adapters while preserving published upgrade paths. |
| `simready-foundation-add-runtime-test` | Add runtime testing coverage, runner expectations, commands, and evidence for features/profiles that need behavioral proof. |
| `simready-foundation-validate-foundation-change` | Audit a SimReady change across requirement docs, validators, feature manifests, profiles, adapters, runtime tests, and skill layout. |

Repo-local package workflow skills also live in `skills`:

| Skill | Purpose |
|---|---|
| `simready-foundation-create-package` | Create SimReady packages with the bundled package-sample workflow, including WRAPP setup, root USD inputs, validation phases, and no-WRAPP fallback modes. |

Use the skill's `SKILL.md` as the procedural source of truth before editing an
asset. Each skill should stage output under the requested output directory,
preserve reports, rerun the narrowest useful validation gate, and avoid
silently mutating the source asset.

The `simready-foundation-conform-fet-005-simulate-grasp-physics` skill is intentionally visual-semantic. Do not satisfy
`GSP.001` with an arbitrary line. It requires a vision-capable agent/model. If
the current agent cannot inspect images directly, it must not author a grasp
line and should tell the user to rerun FET005 repair with vision enabled. Use
render, screenshot, viewport, or source mesh evidence to choose a graspable
region, avoid bad grasp areas such as handles or voids when they are not
intended, and record the rationale and coordinate mapping.

## Feature Definition Principles

When defining or changing a feature, start from the runtime use case:

1. Identify the asset behavior or runtime promise.
2. Define success criteria in concrete asset terms.
3. Choose existing requirements/capabilities where possible.
4. Add new requirements only when the feature needs a new testable rule.
5. Make the feature JSON manifest match the feature documentation.
6. Add or update validators for objective checks.
7. Document any subjective or manual checks explicitly.
8. Decide which profiles include the feature and whether it is required or
   optional.
9. Version feature/profile changes semantically.

Feature versions are immutable once published or used by a profile. When
updating an existing feature, create a new markdown file and a new JSON manifest
for the updated feature version, then bump the version number. Do not silently
mutate the old feature documentation or JSON in place unless the user explicitly
asks for an editorial fix to an unpublished/draft feature.

The old feature version should remain available so existing profiles and assets
continue to resolve their original contract. Profiles can then opt into the new
feature by referencing the new feature version.

Examples:

- A "Graspable" feature means a Sim Ready prop can be grabbed by a robotic
  gripper. The feature should define the authored data, physics/material
  requirements, and validation checks that make that runtime behavior credible.
- A "Robot Core" feature means the robot asset has the schema, file layout,
  naming, thumbnail, and physics-layer separation needed by the robot runtime.

## OpenUSD / Pixar USD Best Practices

Prefer standard OpenUSD concepts before introducing custom metadata or custom
schemas. Custom SimReady metadata is appropriate only when USD does not already
represent the concept cleanly.

Use native USD patterns for:

- `defaultPrim` and a clear asset root.
- Stable prim paths and consistent prim/file naming.
- Stage units such as `metersPerUnit`, `kilogramsPerUnit`, `upAxis`, and
  `timeCodesPerSecond` when relevant.
- `UsdGeom` meshes, purposes, extents, normals, winding, topology, and
  xformable hierarchy.
- `UsdShade` materials and material bindings.
- `UsdPhysics` rigid bodies, colliders, joints, mass, articulations, and drives.
- `assetInfo`, model hierarchy, relationships, variants, references, payloads,
  and layer composition.
- Relative or anchored asset paths for portability.
- Separation of interface, payload, visual, material, and physics layers when a
  runtime profile requires it, especially Isaac Sim and robot assets.

Avoid inventing custom properties for information that USD already models with
schemas, metadata, relationships, or composition arcs.

## Important Files

- `nv_core/sr_specs/docs/index.md` - top-level docs model.
- `nv_core/sr_specs/docs/config.json` - paths for requirements, features, and
  profiles.
- `nv_core/sr_specs/docs/capabilities/` - capability docs, requirement pages,
  and Python validators.
- `nv_core/sr_specs/docs/features/` - feature docs and JSON manifests.
- `nv_core/sr_specs/docs/profiles/profiles.toml` - profile-to-feature bundles.
- `nv_core/sr_specs/docs/profiles/*.md` - authoring guides for profiles.
- `nv_core/sr_specs/docs/specifications/` - formal specification documents.
- `nv_core/sr_specs/docs/guides/guides.md` - entrypoint for feature, profile,
  feature-adapter, and runtime-testing workflows.
- `nv_core/sr_specs/docs/guides/features/features.md` - feature creation,
  versioning, dependencies, and expansion workflow.
- `nv_core/sr_specs/docs/guides/profiles/profiles.md` - profile creation,
  profile versioning, and profile-to-feature bundles.
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md` -
  profile/feature mutation adapters under `nv_core/cip_specs/asset_handler_modules`.
- `nv_core/sr_specs/docs/guides/runtime_testing/runtime_testing.md` -
  runtime test pipeline entrypoint and nested runtime testing guides.

## Validation Expectations

Validation should align with requirement IDs and feature manifests:

- Requirement docs should describe the rule, why it matters, examples, and how
  to comply.
- Validators should register against the matching requirement IDs.
- Feature JSON should include the exact requirement IDs needed by that feature.
- Feature docs should explain the runtime use case and group requirements by
  capability.
- Profiles should reference feature IDs and versions consistently.
- Existing feature versions should remain immutable. New behavior or changed
  requirements should be represented by a new feature markdown file, a new
  feature JSON manifest, and a bumped semantic version.

Use failures for objective contract violations. Use warnings for best-practice
guidance, portability concerns, or checks that may have legitimate exceptions.
Call out manual review when a requirement is subjective, such as "logical"
hierarchy or pivot placement.

## Current Repository Notes

Some parts of the docs appear to be drafts or in-progress:

- Several capability statuses are Draft or Development.
- Some feature pages include `TBD`, TODOs, or placeholder sections.
- Some filenames contain typos such as `phyics`.
- Some requirement pages, especially newer robot-oriented ones, do not yet use
  the same metadata table style as the older requirement pages.
- `capabilities/__init__.py` contains duplicate imports.

Do not assume the docs are complete just because a file exists. Keep markdown,
JSON manifests, TOML profiles, and validation code synchronized when making
changes.
