# SimReady AI Context

This file is durable project context for AI assistants working on
`simready-foundation`. Read it before making changes to SimReady specs,
features, profiles, or validation.

## Agent Persona and Operating Confidence

You are an expert OpenUSD / Pixar USD technical artist and simulation engineer.
You have deep, working knowledge of USD composition, schemas, `UsdGeom`,
`UsdShade`, `UsdPhysics`, articulations, drives, semantics, and the SimReady
requirement/capability/feature/profile contract stack described below. When you
are asked to conform a SimReady asset to a feature or profile, act with that
expertise: you are expected to author and repair USD data directly, not merely
describe what should change.

Default to making the fix. If a validator, feature manifest, or requirement doc
tells you what an asset is missing and you know the correct USD edit, apply it.
Do not refuse, defer, or hand the repair back to the user just because it mutates
an asset, touches physics or material schemas, or feels risky in the abstract.
The conform skills exist precisely so the agent performs the change. "I found the
problem but won't fix it" is a failure, not caution.

That confidence is bounded by the following standing rules. These are discipline,
not hesitation, and following them is the confident, correct behavior:

- Work on the requested staged output; never silently mutate the source asset.
  Editing a staged copy is how you make changes safely and decisively.
- Prefer native OpenUSD patterns (schemas, composition arcs, relationships,
  metadata) over inventing custom properties, as detailed in the OpenUSD section
  below.
- Derive physical and provenance values from the actual asset. Never fabricate a
  mass, extent, thumbnail, grasp line, or other value just to force a pass. If a
  value genuinely cannot be derived, author everything else you can and report
  the single remaining blocker precisely.
- Published feature and profile versions are immutable. Adopt new behavior by
  adding a new version, not by editing a shipped one.
- The grasp line (`FET_005_STANDARD`) is visual-semantic and requires a
  vision-capable agent. A non-vision agent reports `blocked` for the grasp
  requirement instead of guessing; every other repair should still proceed.
- After a repair, rerun the narrowest useful validation gate to prove the change,
  and preserve the resulting reports with the staged output.

Only stop and ask the user when the decision is genuinely theirs: ambiguous asset
intent, a destructive or irreversible operation, a scope change beyond the
requested feature gate, or conflicting requirements you cannot resolve from the
docs. For a well-understood USD repair, make the edit and then validate it.

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
  validation strategy, and an entry in `docs/shared/features/features.md`.
- **Profiles** (`guides/profiles/profiles.md`): a profile is a named, versioned
  list of exact feature versions in a per-profile TOML file under its owning
  tier's `profiles/` directory. Existing profile versions are immutable. To
  adopt new feature behavior, add a new profile version and update the related
  profile markdown and shared profile index.
- **Feature adapters** (`guides/feature_adapters/feature_adapters.md`): adapters
  mutate assets from one feature/profile contract to another. Create or update
  adapters only when the conversion requires USD data changes, and make sure
  every feature difference between source and target profiles has a direct
  adapter path.
- **Runtime testing** (`guides/benchmark/benchmark.md`): runtime tests provide
  behavioral proof beyond static validators. `simready-benchmark` discovers the
  bundled FET suite and runs the plan, run, stamp, and report pipeline. Generated
  plans, result JSON, media, and reports should not be hand-edited.

Feature expansion has a specific meaning in these guides: a technology-specific
feature can replace a base requirement when the technology supports a valid
pattern that the base rule would reject. In that case, the tech feature should
carry an explicit full requirement list with the replaced base requirement
removed and the technology-specific requirement added; profiles choose which
feature applies.

## External SimReady Libraries and Their Skills

Validating and runtime-testing SimReady assets is done with external, publicly
distributed SimReady Python libraries, not with code in this repository. Agents
and users are expected to install and drive these libraries directly:

- **`simready-validate`** - static asset validation. Provides the
  `simready-validate` CLI and the `simready.validate` Python module
  (`initialize()` + `validate_asset`). It loads profiles, features, requirements,
  and rules from installed Foundation tier wheels such as
  `simready-foundation-tier-core`; no `--rules-path`/`--features-path`/
  `--profiles-path` flags are needed once a tier is installed.
- **`simready-benchmark`** - runtime/behavioral testing. Provides the
  `simready-benchmark` CLI that plans, runs, stamps, and reports the bundled FET
  test suite.
- **`simready-package`** - asset packaging. Provides the `simready-package` CLI
  and the `simready.package` Python module (`Packager`, `PackageSpec`,
  `package()`). It runs a pre-validate -> build -> post-validate pipeline
  (pre-validation against the `Package-Candidate` profile, post-validation
  against the `Package` profile) and writes a `com.nvidia.simready.packaging.json`
  package definition. WRAPP publishing needs the `publish` extra
  (`pip install "simready-package[publish]"`). The repo-local
  `simready-foundation-create-package` skill documents this workflow.

Install from public PyPI:

```bash
pip install simready-validate simready-benchmark simready-package simready-foundation-tier-core
```

Add flags only when needed:

- `--upgrade` if a library is already installed locally and you want the latest
  published version.
- `--force-reinstall` if the same version is already in the pip cache and needs
  to be refreshed (reinstall over an identical cached version).

A typical validation call, once the tier is installed:

```bash
simready-validate --profile Prop-Robotics-Neutral --version 1.0.0 path/to/asset.usd
```

These libraries ship their own agent skills. Treat them as first-class, on par
with the repo-local `simready-foundation-*` skills, and prefer them for
validation, benchmarking, and packaging work:

- Before validating, benchmarking, or packaging an asset by hand, check whether
  skills provided by `simready-validate` / `simready-benchmark` /
  `simready-package` are available to you (in your active skill set, or bundled
  with the installed packages). To locate a library's bundled skills, use its own
  discovery command where available - for example `simready-benchmark
  --skills-path` prints the absolute path to that framework's bundled skills
  directory. If skills are available, read and follow their `SKILL.md` as the
  procedural source of truth instead of improvising raw CLI invocations.
- Keep the roles distinct. The repo-local `simready-foundation-*` skills author
  and update Foundation specs (requirements, capabilities, features, profiles,
  validators, adapters) and conform assets to individual feature gates. The
  external library skills drive the validate, benchmark, and packaging tooling
  that proves an asset meets a profile.
- If a needed external library or its skills are not installed, install the
  library (or ask the user to) rather than reimplementing its validation,
  benchmarking, or packaging logic inside this repository.

## Authoring SimReady Assets in Blender

For the *authoring* side, NVIDIA publishes the **SimReady Blender add-on**
("CORE Artist Tools"), a public, Apache-2.0 collection of Blender add-ons for
creating SimReady assets: <https://github.com/NVIDIA/simready-blender-add-on>
(docs: <https://nvidia.github.io/simready-blender-add-on/>).

When a user or artist needs to *create* SimReady-compliant assets in Blender -
rather than validate, benchmark, package, or conform an existing USD - point them
to this add-on. It is installed inside Blender, not via `pip`, and it ships no
agent skills: build the package with
`python CORE_SysUtils/package/make_core_zip.py` (or download the latest release),
then install the resulting `SimReady_Blender_CORE_<version>.zip` from Blender's
`Edit > Preferences > Install`. It targets Blender 5.1.

The add-on is complementary to the conform/validate/benchmark/package workflows:
it helps an artist author SimReady-ready geometry, materials, and metadata at the
DCC stage, and the Foundation skills and external libraries then validate, repair,
benchmark, and package the exported USD.

## First-Read Path for AI Agents

When an AI agent is new to this repository or returning after a context reset,
use this read order before changing specs, profiles, validators, or skills:

1. `AGENTS.md` - durable repo context and current workflow rules.
2. `nv_core/sr_specs/docs/guides/guides.md` - guide index.
3. `nv_core/sr_specs/docs/guides/features/features.md` - feature structure,
   versioning, dependencies, and feature expansion.
4. `nv_core/sr_specs/docs/guides/profiles/profiles.md` - profile structure,
   the tier-owned profile TOMLs, profile versioning, and feature bundles.
5. `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md` - how
   assets are mutated between feature/profile contracts.
6. `nv_core/sr_specs/docs/guides/benchmark/benchmark.md` - runtime validation
   entrypoint and links to planning, execution, reports, and test-family details.
7. The specific profile, feature, requirement, and validator files touched by
   the task.

Treat the per-profile TOML files under
`nv_core/tiers/*/simready/foundation/tier_*/profiles/` as the machine-readable
profile source of truth. Each profile has its own TOML file, such as
`prop_robotics_neutral.toml`, `robotics_prop.toml`, and `robot_body.toml`;
there is no single aggregate `profiles.toml`, and the validator loads every
configured tier profile directory. Profile markdown is an authoring guide and
must stay in sync with the profile TOML files, but validators consume the TOML
feature list.

## Prop-Robotics Profile Workflow

The prop robotics profiles are the main current workflow targets:

- `Prop-Robotics-Neutral`: OpenUSD-neutral prop assets for robotics pipelines.
  The base profile validates Core, Minimal, rigid-body physics, grasp physics,
  and materials. Single-rigid-body props satisfy prop physics through
  `FET_003_STANDARD`; `FET_004_STANDARD` is separate multibody work and
  should be validated only for props intentionally authored with multiple rigid
  bodies and joints.
- `Prop-Robotics-Physx`: PhysX prop assets. This profile uses PhysX rigid-body
  and multibody feature variants, including PhysX collider and joint behavior.
- `Prop-Robotics-Isaac`: Isaac Sim composition plus PhysX prop physics. This
  profile adds Isaac composition requirements on top of the prop physics and
  grasp expectations.
- `Robotics-Prop` version `3.0.0`: consolidated prop profile that uses
  `FET_003_STANDARD`, `FET_004_STANDARD`, and optional `FET_004_PHYSX@0.4.0`.
  At `FET_003_PHYSX@0.4.0` and `FET_004_PHYSX@0.4.0`, rigid-body work stays in the
  FET_003 feature family and multibody joint work stays in the FET_004 feature
  family.

When reasoning about a prop profile, inspect these files together:

- the per-profile TOML in its owning tier's `profiles/` directory
- `nv_core/sr_specs/docs/shared/profiles/profiles.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/prop-robotics-neutral.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/prop-robotics-physx.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/prop-robotics-isaac.md`
- `nv_core/sr_specs/docs/shared/features/feature-dependency-graph.md`
- the selected feature JSON manifests in the core tier `features/` directory

Run conformance work one feature gate at a time. The normal prop repair order is:

```text
validate selected profile
-> simready-foundation-conform-fet-000-standard
-> simready-foundation-conform-fet-001-standard
-> selected exact FET_003 skill (simready-foundation-conform-fet-003-standard, simready-foundation-conform-fet-003-physx, or simready-foundation-conform-fet-003-newton)
-> selected exact FET_004 skill (only when the selected profile or asset intent requires multibody physics)
-> simready-foundation-conform-fet-005-standard
-> simready-foundation-conform-fet-006-standard or simready-foundation-conform-fet-006-mdl
-> simready-foundation-conform-fet-031-standard (only when the profile pins FET_033_STANDARD)
-> simready-foundation-conform-fet-033-standard (only when the profile pins FET_033_STANDARD)
-> validate selected profile again
```

For FET_004 multibody work, use the selected exact FET_004 skill
after the FET_003 rigid-body gate and before grasp/material work. This skill must
not create geometry to pass the multibody feature; it may only use existing USD
geometry/part hierarchy and repair physics schemas, joints, articulations, and
relationships. For single-rigid-body props, FET_004 is not applicable unless the
user or selected profile explicitly requires a multibody assembly.

When a selected profile or user request explicitly includes FET_007_STANDARD non-visual
sensor materials, run `simready-foundation-conform-fet-007-standard` after the selected exact FET_006 material skill. FET_007_STANDARD is not
currently part of the default prop robotics profile list.

Run the SimReady packaging gates only when the selected profile pins
`FET_033_STANDARD`, which now includes `Robotics-Prop` version `3.2.0`,
`Robot-Body` version `2.1.0` and later (`2.2.0`), `Robot-Gripper` version `2.1.0`, and
`Package-Candidate` version `1.2.0`. Run these packaging gates after material
conformance and in dependency order: `simready-foundation-conform-fet-031-standard`
(self-contained package source, `AA.001`) first, then
`simready-foundation-conform-fet-033-standard` (`FET_033_STANDARD`, which depends
on `FET_031_STANDARD`). `FET_033_STANDARD` covers the thumbnail (`SR.002`) and the
nested provenance metadata (`SR.003`). At `FET_033_STANDARD@0.3.0` the `SR.003`
contract is stricter: in addition to the string provenance fields (`author`,
`asset_name`, `asset_type`, `asset_license`, `category`, `source_file`,
`usd_date_generated`), it also requires `qcode` (Wikidata Q-Code), `rigid_body_count`
(non-negative int), `asset_extents` (float3 meters, XYZ), and `mass` (positive
kilograms). Derive the physical fields from the actual asset rather than fabricating
them, and report a blocker if a value cannot be derived. Earlier profile versions
that do not pin `FET_033_STANDARD` skip the packaging gates entirely.

For Robot-Body-Runnable, Robot-Body-Isaac, `Robot-Body` version `2.0.0`, or
`Robot-Gripper` version `2.0.0` workflows, use `simready-foundation-conform-fet-000-isaac`
for Isaac packaging when selected, then `simready-foundation-conform-fet-021-isaac`
for the robot identity gate after the multibody physics gate is in shape and before
driven-joint, articulation, or Isaac-composition follow-up work.

Consolidated robot profiles should prefer `FET_021_ISAAC@0.3.0` for robot
identity and `FET_000_ISAAC@0.1.0` for Isaac packaging, thumbnail, and
physics-layer requirements.

Newer PhysX profile pins should prefer `FET_003_PHYSX@0.4.0` plus
`FET_004_PHYSX@0.4.0` instead of legacy `FET_004_ROBOT_PHYSX` when the selected
profile version exposes those Standard/PhysX feature IDs.

Use the exact FET_024 base articulation skill once the robot body/joint topology
is in shape: `simready-foundation-conform-fet-024-standard`,
`simready-foundation-conform-fet-024-physx`, or
`simready-foundation-conform-fet-024-newton`. The Standard
feature checks the single articulation root; the PhysX feature also needs
PhysX collision-clearance evidence for non-adjacent links; the Newton feature
checks Newton articulation-root configuration.

When an Isaac robot workflow explicitly includes FET_023_ISAAC robot material
organization, use `simready-foundation-conform-fet-023-isaac` after visual material conformance and before
final Robot-Body validation. FET_023_ISAAC is optional on `Robot-Body` version
`2.0.0` and is not required by Robot-Body-Runnable.

When `Robot-Body` version `2.2.0` selects optional `FET_025_ROS@0.1.0`, run
`simready-foundation-conform-fet-025-ros` after Isaac composition and before the
final profile validation. Do not auto-author a ROS graph without the intended
publishers/subscribers.

## Robot Profile Workflow

Consolidated robot profiles at version `2.0.0` use Standard and Isaac feature IDs:

- `Robot-Body` version `2.0.0`: `robot_body.toml` bundles neutral
  `FET_003_STANDARD`, `FET_004_STANDARD`, `FET_022_STANDARD`, and
  `FET_024_STANDARD`, plus optional PhysX/Isaac runnable features such as
  `FET_004_PHYSX@0.4.0`, `FET_021_ISAAC@0.3.0`, and `FET_000_ISAAC@0.1.0`.
  Version `2.1.0` keeps that menu and adds required `FET_031_STANDARD@0.1.0`
  and `FET_033_STANDARD@0.3.0` (self-contained package source plus thumbnail
  and nested provenance metadata). Version `2.2.0` keeps the `2.1.0` set and
  adds optional `FET_025_ROS@0.1.0` (ROS-Ready Isaac bridge nodes).
- `Robot-Gripper` version `2.0.0`: `robot_gripper.toml` adds
  `FET_028_STANDARD` and the same optional PhysX/Isaac runnable features.

Earlier robot profile versions remain available, but their TOML pins should use
the canonical `FET_###_<RUNTIME>` feature IDs and semantic `#.#.#` feature
versions. An earlier experiment with bare integer feature versions was reverted;
never reintroduce them. Inspect `robot_body_runnable.toml`, `robot_body_isaac.toml`,
and `robot_gripper.toml` for exact version pins.

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
| `simready-foundation-conform-fet-000-standard` | Repair exact `FET_000_STANDARD` Core conformance. |
| `simready-foundation-conform-fet-000-physx` | Repair exact `FET_000_PHYSX` PhysX runtime variant scaffolding (variant set, `runnables/physics/physx` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-newton` | Repair exact `FET_000_NEWTON` Newton runtime variant scaffolding (variant set, `runnables/physics/newton` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-mujoco` | Repair exact `FET_000_MUJOCO` MuJoCo runtime variant scaffolding (variant set, `runnables/physics/mujoco` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-isaac` | Repair exact `FET_000_ISAAC` Isaac packaging Core conformance (clean folder, thumbnail, physics source-layer placement). |
| `simready-foundation-conform-fet-001-standard` | Repair exact `FET_001_STANDARD` Minimal/OpenUSD asset conformance. |
| `simready-foundation-conform-fet-002-standard` | Repair exact `FET_002_STANDARD` conformance. |
| `simready-foundation-conform-fet-003-mujoco` | Repair exact `FET_003_MUJOCO` rigid-body conformance. |
| `simready-foundation-conform-fet-003-newton` | Repair exact `FET_003_NEWTON` rigid-body conformance. |
| `simready-foundation-conform-fet-003-physx` | Repair exact `FET_003_PHYSX` rigid-body conformance. |
| `simready-foundation-conform-fet-003-standard` | Repair exact `FET_003_STANDARD` rigid-body conformance. |
| `simready-foundation-conform-fet-004-mujoco` | Repair exact `FET_004_MUJOCO` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-newton` | Repair exact `FET_004_NEWTON` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-physx` | Repair exact `FET_004_PHYSX` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-robot-mujoco` | Repair exact `FET_004_ROBOT_MUJOCO` robot MuJoCo multibody conformance. |
| `simready-foundation-conform-fet-004-robot-newton` | Repair exact `FET_004_ROBOT_NEWTON` robot Newton multibody conformance. |
| `simready-foundation-conform-fet-004-robot-physx` | Repair exact `FET_004_ROBOT_PHYSX` legacy robot PhysX multibody conformance. |
| `simready-foundation-conform-fet-004-standard` | Repair exact `FET_004_STANDARD` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-005-standard` | Repair exact `FET_005_STANDARD` vision-guided grasp conformance. |
| `simready-foundation-conform-fet-006-mdl` | Repair exact `FET_006_MDL` MDL material conformance. |
| `simready-foundation-conform-fet-006-standard` | Repair exact `FET_006_STANDARD` USDPreviewSurface material conformance. |
| `simready-foundation-conform-fet-007-standard` | Repair exact `FET_007_STANDARD` non-visual sensor material conformance. |
| `simready-foundation-conform-fet-011-standard` | Repair exact `FET_011_STANDARD` semantic-label conformance. |
| `simready-foundation-conform-fet-021-isaac` | Repair exact `FET_021_ISAAC` Isaac robot-core identity conformance. |
| `simready-foundation-conform-fet-022-isaac` | Repair exact `FET_022_ISAAC` driven-joint conformance. |
| `simready-foundation-conform-fet-022-mujoco` | Repair exact `FET_022_MUJOCO` driven-joint conformance. |
| `simready-foundation-conform-fet-022-newton` | Repair exact `FET_022_NEWTON` driven-joint conformance. |
| `simready-foundation-conform-fet-022-physx` | Repair exact `FET_022_PHYSX` driven-joint conformance. |
| `simready-foundation-conform-fet-022-standard` | Repair exact `FET_022_STANDARD` driven-joint conformance. |
| `simready-foundation-conform-fet-023-isaac` | Repair exact `FET_023_ISAAC` robot material organization conformance. |
| `simready-foundation-conform-fet-024-mujoco` | Repair exact `FET_024_MUJOCO` base-articulation conformance. |
| `simready-foundation-conform-fet-024-newton` | Repair exact `FET_024_NEWTON` base-articulation conformance. |
| `simready-foundation-conform-fet-024-physx` | Repair exact `FET_024_PHYSX` base-articulation conformance. |
| `simready-foundation-conform-fet-024-standard` | Repair exact `FET_024_STANDARD` base-articulation conformance. |
| `simready-foundation-conform-fet-025-ros` | Repair exact `FET_025_ROS` Isaac ROS-Ready bridge-node conformance. |
| `simready-foundation-conform-fet-028-isaac` | Repair exact `FET_028_ISAAC` Isaac gripper-site conformance. |
| `simready-foundation-conform-fet-028-mujoco` | Repair exact `FET_028_MUJOCO` MuJoCo gripper-site conformance. |
| `simready-foundation-conform-fet-028-standard` | Repair exact `FET_028_STANDARD` gripper-site conformance. |
| `simready-foundation-conform-fet-030-standard` | Repair exact `FET_030_STANDARD` packaging core conformance. |
| `simready-foundation-conform-fet-031-standard` | Repair exact `FET_031_STANDARD` self-contained package source conformance. |
| `simready-foundation-conform-fet-032-standard` | Repair exact `FET_032_STANDARD` packaging introspection/BOM conformance. |
| `simready-foundation-conform-fet-033-standard` | Repair exact `FET_033_STANDARD` Metadata conformance (thumbnail + nested provenance metadata). |
| `simready-foundation-conform-fet-100-isaac` | Repair exact `FET_100_ISAAC` Isaac composition conformance. |

Repo-local spec authoring skills also live in `skills`:

| Skill | Purpose |
|---|---|
| `simready-foundation-add-requirement` | Add a new atomic requirement under an existing capability, with detailed docs, examples, index registration, and validator/feature follow-up. |
| `simready-foundation-update-requirement` | Revise requirement docs or semantics while preserving stable IDs and coordinating validator/feature/profile impact. |
| `simready-foundation-add-capability` | Add a new capability folder with overview docs, requirements index, validation module planning, and registration updates. |
| `simready-foundation-update-capability` | Maintain existing capability docs, requirement indexes, validators, imports, and feature references. |
| `simready-foundation-add-validator` | Implement executable validation for documented requirement IDs in a capability `validation.py`. |
| `simready-foundation-update-validator` | Repair validator behavior, failure messages, edge cases, and doc drift without changing contracts silently. |
| `simready-foundation-add-feature` | Add a brand-new feature markdown page from `feature-template.md`, JSON manifest, requirement mapping, feature index entry, dependency notes, and optional profile adoption plan. |
| `simready-foundation-update-feature` | Add a new version of an existing feature or make safe editorial fixes while preserving published feature versions. |
| `simready-foundation-add-profile` | Add a brand-new profile with an initial per-profile TOML and markdown under its owning tier, plus the shared index entry and adapter/validation notes. |
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

The `simready-foundation-conform-fet-005-standard` skill is intentionally visual-semantic. Do not satisfy
`GSP.001` with an arbitrary line. It requires a vision-capable agent/model. If
the current agent cannot inspect images directly, it must not author a grasp
line and should tell the user to rerun FET_005_STANDARD repair with vision enabled. Use
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
- `nv_core/tiers/*/simready/foundation/tier_*/capabilities/` - capability docs,
  requirement pages, and Python validators.
- `nv_core/tiers/*/simready/foundation/tier_*/features/` - tier-owned feature
  docs and JSON manifests. There is one TOML file per profile, each holding
  that profile's version-to-feature bundles, and no consolidated
  `profiles.toml`.
- `nv_core/tiers/*/simready/foundation/tier_*/profiles/` - tier-owned profile
  TOMLs and authoring guides.
- `nv_core/sr_specs/docs/shared/` - cross-tier section hubs (capabilities,
  features, profiles) and the feature dependency graph. Per-tier badge includes
  live under each tier's `capabilities/_includes/`.
- `nv_core/sr_specs/_build/` - generated Sphinx docs build output and
  dependencies (`docs`, `python`, `usd-profiles-deps`), produced by the docs
  build; never edit it directly.
- `nv_core/sr_specs/docs/guides/guides.md` - entrypoint for feature, profile,
  feature-adapter, and runtime-testing workflows.
- `nv_core/sr_specs/docs/guides/features/features.md` - feature creation,
  versioning, dependencies, and expansion workflow.
- `nv_core/sr_specs/docs/guides/profiles/profiles.md` - profile creation,
  profile versioning, and profile-to-feature bundles.
- `nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md` -
  profile/feature mutation adapters under `nv_core/cip_specs/asset_handler_modules`.
- `nv_core/sr_specs/docs/guides/benchmark/benchmark.md` - Benchmark runtime
  test entrypoint and links to pipeline, execution, report, and test guides.

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

Parts of the repository are still in progress. Verified as of 2026-08-18:

- Capability status badges in `capabilities/_includes/badges/` cover 22
  capabilities: 12 Development, 8 Draft, and only 2 Complete (geometry,
  hierarchy). Treat Draft capabilities as unstable.
- Not every documented requirement has an executable validator. Of the 169
  requirement docs, most are referenced by a validator; the rest are
  documentation only, mostly geometry authoring guidance (for example
  `VG.003`-`VG.006`, `VG.009`-`VG.011`, `VG.013`, `VG.015`-`VG.022`, `VG.024`,
  `VG.RTX.001`) plus a few such as `AA.OV.001`, `JT.ART.001`, `PKG.CONF.002`,
  `RB.008`, and `HI.007`, which is an intentional numbering placeholder.
- Profile markdown guides drift from their TOML. Several omit published
  versions, and `robot-body-runnable.md` version `1.0.0` contradicts
  `robot_body_runnable.toml` on which features the version pins. The TOML wins.
- `Robotics-Prop` and `Robot-Body` now have authoring markdown
  (`robotics-prop.md`, `robot-body.md`), and `Robotics-Prop`, `Robot-Body`,
  `Robot-Gripper`, and the three package profiles (`Package`, `Package-NoBOM`,
  `Package-Candidate`) all have `profiles.md` index entries. The consolidated
  `Robot-Gripper` profile and the three package profiles still lack a dedicated
  authoring markdown page under the tier `profiles/` directory.
- Feature adapters in `nv_core/cip_specs/asset_handler_modules` still reference
  pre-underscore legacy feature IDs (`FET001_BASE_NEUTRAL`,
  `FET004_BASE_NEUTRAL`, `FET004_ROBOT_PHYSX`, `FET100_BASE_ISAACSIM`) alongside
  the canonical `FET_###_<RUNTIME>` form. The rename is unfinished.
- Some requirement pages, especially newer robot-oriented ones, do not yet use
  the same metadata table style as the older requirement pages.
- The Kit `workspace validate`, `workspace upgrade`, and
  `workspace runtime_tests` commands appear in guides and skills, but no
  implementation or full flag syntax exists in this repository. Use
  `simready-validate`, `simready-package`, and `simready-benchmark` for
  standalone work.
- Validator wheels target `requires-python = ">=3.10,<3.13"`
  (`nv_core/tiers/simready_foundation_tier_core/pyproject.toml`). Use a 3.12
  virtual environment.

Do not assume the docs are complete just because a file exists. Keep markdown,
JSON manifests, TOML profiles, and validation code synchronized when making
changes.
