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
- Protect unrelated local work. Before editing shared repository files (spec
  markdown, requirement/feature JSON, profile TOML, validators, skills, or docs),
  check `git status` and the working tree for unrelated in-progress changes, and
  scope your edits to the requested task. Never revert, overwrite, discard, stash,
  or commit a user's uncommitted or unrelated changes. If your change must touch
  files that already carry pending unrelated edits, surface that and confirm
  before proceeding rather than clobbering them. This is the shared-file
  counterpart to working on staged asset output.
- Keep secrets out of the repository and evidence. Treat any user-provided tokens,
  credentials, API keys, connection strings, or other secrets as sensitive: never
  write them into files, source, logs, validation or evaluation reports, commit
  messages, or bug/Jira/Confluence attachments, and do not echo them back in full.
  Read secrets from environment variables or an existing credential store, prefer
  short-lived handles over copying the value, and redact secrets from any output
  you preserve. If a task appears to require persisting a secret, stop and confirm
  a safe mechanism instead of committing it.
- Prefer native OpenUSD patterns (schemas, composition arcs, relationships,
  metadata) over inventing custom properties, as detailed in the OpenUSD section
  below.
- Derive physical and provenance values from the actual asset. Never fabricate a
  mass, extent, thumbnail, grasp line, or other value just to force a pass. If a
  value genuinely cannot be derived, author everything else you can and report
  the single remaining blocker precisely.
- Published feature and profile versions are immutable. Adopt new behavior by
  adding a new version, not by editing a shipped one.
- The grasp line (`FET005_Grasp`) is visual-semantic and requires a
  vision-capable agent. A non-vision agent reports `blocked` for the grasp
  requirement instead of guessing; every other repair should still proceed.
- After a repair, rerun the narrowest useful validation gate to prove the change,
 and preserve the resulting reports with the staged output.
- A conformance, CAD-to-SimReady, or asset-preparation workflow is complete only
 after the asset validates against a full named, versioned profile. Report the
 profile name and version and the executed-versus-total requirement counts.
 A run driven by a hand-picked subset of rules instead of a profile is
 `partial - not submission-ready`: label it that way, name the full profile the
 asset still owes, and never present it as conformance. Per-feature gate reruns
 prove a single repair; they do not substitute for the full-profile pass the
 workflow must establish before handoff.

Only stop and ask the user when the decision is genuinely theirs: ambiguous asset
intent, a destructive or irreversible operation, a scope change beyond the
requested feature gate, or conflicting requirements you cannot resolve from the
docs. For a well-understood USD repair, make the edit and then validate it.

## Master-Level OpenUSD Competence for Conform Work

Running any `simready-foundation-conform-*` skill is expert USD authoring. Before
you edit an asset, hold the relevant part of the OpenUSD / Pixar USD spec in
working memory and reason from it. Do not pattern-match on a validator message or
copy a shape from another asset without understanding why the runtime needs it.

Operate at master level across the areas a repair touches:

- Composition: sublayers, references, payloads, inherits, specializes, variant
  sets, and the LIVRPS strength ordering. Know how value resolution and list
  editing (`prepend`, `append`, `explicit`, `delete`) behave, and which arc and
  which layer a given opinion must land on so it wins where the runtime reads it.
- Prim structure: the `def`, `over`, and `class` specifiers, activation,
  native instancing and prototypes, model hierarchy and `kind`, geometry
  `purpose`, and when to use a relationship rather than an attribute.
- Stage metadata: `defaultPrim`, `metersPerUnit`, `kilogramsPerUnit`, `upAxis`,
  and `timeCodesPerSecond`, and how units and up-axis change the numeric values
  you author.
- Schemas: `UsdGeom` (xformable hierarchy, extents, normals, winding, geom
  subsets), `UsdShade` (materials, bindings, interface inputs), and `UsdPhysics`
  (rigid bodies, colliders, mass and inertia, joints, articulations, drives).

Translate each requirement into the exact native USD edit on the correct prim,
arc, and layer; derive values from the asset's real geometry and composition;
then reopen the composed stage and confirm the opinion resolves as intended
before you claim the gate passes. If the spec genuinely does not cover a case,
consult the skill's `SKILL.md` source of truth and the authoritative USD
documentation rather than guessing, and never fabricate data to satisfy a
validator token.

## Response Style

Answer in as few words as the question allows. This is a requirement, not a
preference.

- Lead with the direct answer. A question answerable in one sentence gets one
  sentence.
- When asked to explain, explain only. Do not also edit, revert, or fix
  anything. A question is not a work order, and a policy statement is not a
  work order. Propose the change and wait.
- Never repair drift, style, or unrelated bugs the current task did not cause.
  Report them in one line, or not at all.
- Do not restate the question, recap what you just did, or list the searches you
  ran.
- Skip headers and tables for short answers. Use them only when the answer is
  genuinely a multi-part enumeration.
- Cite the file, line, or requirement ID instead of quoting its contents back.
- No preamble, no apologies, no self-assessment, no unsolicited offers of
  further work.

Brevity never overrides accuracy. Keep the correction, the blocker, and the
"this does not exist in the repo" finding even when it costs a sentence.

## Documentation Voice

Requirement docs, feature docs, profile docs, skills, validator messages, and
sample comments describe the contract as it stands. They are not a record of how
it got there.

- State the rule positively. Describe what the asset must author and why the
 runtime needs it. Do not argue against a framing the doc no longer uses.
- Never explain a prior mistake. If a requirement was once worded wrongly, the
 corrected doc reads as though it always said the right thing. The chat or merge
 request carries that history; the spec does not.
- The exception is a genuine version boundary or a fixed bug. A new feature
 version may say what changed from the previous version, and a bug-fix note may
 name the broken behavior, because a consumer needs both to migrate.
- An invalid example stands on its own. Show the wrong data and name the rule it
 breaks; do not label it as the case that motivated the rule.
- Do not write "not restated here", "rather than requiring it", "this is a
 deliberate reversal", or "there is no X equivalent" as scaffolding around a
 rule. Say which requirement owns the value and move on.
- Repair skills are procedures, so they may say "if the asset authors X, replace
 it with Y". That is forward-looking instruction, not commentary.

## Core Mental Model

SimReady Foundations is a framework for defining what "Sim Ready" means for
OpenUSD assets. The main documentation and spec content lives under:

`nv_core/sr_specs/docs`

The framework is built from four connected concepts:

- **Requirements** are atomic, testable rules with stable IDs, such as
  `UN.006`, `VG.014`, `RB.001`, or `DJ.011`.
- **Capabilities** are `CAP`-prefixed static groups of related requirements,
  such as Core, Visualization, Physics Bodies, Hierarchy, Non-Visual Sensors,
  and Semantic Labels. Profiles may select capabilities directly.
- **Features** are runtime-tested contracts identified only by a dotted
  `<name>[.<runtime>].<version>` ID, for example
  `FET004_Multibody.PhysX.0-4-0`. Runtime-tested FETs have runtime tests,
  additional requirements, and adapters. A testless source remains a FET when
  tested derived FETs point to it; any other static-only contract is a
  capability.
- **Profiles** are named, versioned selectors over features and capabilities.
  Selectors may use wildcards and either kind of selection may be optional.

Validation ties these together. Runtime-tested features have executable tests;
source FETs inherit their feature status from tested derived contracts.

## Workflow From Guides

`nv_core/sr_specs/docs/guides/guides.md` is the entrypoint for the practical
workflow. It links the four guide areas that should shape spec work:

- **Features** (`guides/features/features.md`): a feature belongs to a
  runtime-tested family and its dotted ID contains name, runtime, and version.
  Runtime FETs declare requirements, tests, and adapters; a testless source FET
  is retained when tested derived FETs name it. Other requirement-only bundles
  are capabilities.
- **Profiles** (`guides/profiles/profiles.md`): a profile is a named, versioned
  list of feature and capability selectors in a tier-owned TOML file under its
  owning tier's `profiles/` directory. Feature selectors may use
  name/runtime/version wildcards and both selector kinds may be optional. New
  profiles use one TOML per profile; the taxonomy and packaging catalogs group
  related legacy profiles and are exceptions rather than the pattern. Existing
  profile versions are immutable. To adopt new feature behavior, add a new
  profile version and update the related profile markdown and shared profile
  index.
- **Feature adapters** (`guides/feature_adapters/feature_adapters.md`): adapters
  mutate assets from one feature/profile contract to another. Create or update
  adapters only when the conversion requires USD data changes, and make sure
  every feature difference between source and target profiles has a direct
  adapter path.
- **Runtime testing** (`guides/evaluate/evaluate.md`): runtime tests provide
  behavioral proof beyond static validators. `simready-evaluate` discovers the
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
- **`simready-evaluate`** - runtime/behavioral testing. Provides the
  `simready-evaluate` CLI that plans, runs, stamps, and reports the bundled FET
  test suite.
- **`simready-package`** - asset packaging. Provides the `simready-package` CLI
  and the `simready.package` Python module (`Packager`, `PackageSpec`,
  `package()`). It runs a pre-validate -> build -> post-validate pipeline and
  writes a `com.nvidia.simready.packaging.json` package definition. WRAPP
  publishing needs the `publish` extra
  (`pip install "simready-package[publish]"`). The repo-local
  `simready-foundation-create-package` skill documents this workflow.

Install only the libraries the requested task needs, and reuse a suitable
existing environment rather than building a new one. Each task installs the one
driver library plus the tier wheel that supplies the profiles, features, and
rules. Base tier core supports Python 3.11–3.13; Python 3.12 is recommended
because it is the only interpreter the optional Isaac extra installs on.

- Static validation only:

  ```bash
  pip install simready-validate simready-foundation-tier-core
  ```

- Runtime testing only:

  ```bash
  pip install simready-evaluate simready-foundation-tier-core
  ```

- Packaging only (add the `publish` extra for WRAPP):

  ```bash
  pip install simready-package simready-foundation-tier-core
  ```

Install the full toolchain together only when a single task genuinely spans
validation, runtime testing, and packaging:

```bash
pip install \
  simready-validate simready-evaluate simready-package simready-foundation-tier-core
```

Add extra tiers only when the selected profile or feature needs their contracts:
`simready-foundation-tier-newton` for Newton gates, and
`simready-foundation-tier-isaac` for the Isaac static-optimization
(`Asset-Optimization`) gates; validate those gates with Core and the extra tier
both installed. For Isaac transformation and schema tooling, use Python 3.12 and
install `pip install "simready-foundation-tier-core[isaac]"` from PyPI.

Add flags only when needed:

- `--upgrade` if a library is already installed locally and you want the latest
  published version.
- `--force-reinstall` if the same version is already in the pip cache and needs
  to be refreshed (reinstall over an identical cached version).

A typical validation call, once the tier is installed:

```bash
simready-validate --profile Robotics-Prop --version 3.2.0 path/to/asset.usd
```

These libraries ship their own agent skills. Treat them as first-class, on par
with the repo-local `simready-foundation-*` skills, and prefer them for
validation, evaluating, and packaging work:

- Before validating, evaluating, or packaging an asset by hand, check whether
  skills provided by `simready-validate` / `simready-evaluate` /
  `simready-package` are available to you (in your active skill set, or bundled
  with the installed packages). To locate a library's bundled skills, use its own
  discovery command where available - for example `simready-evaluate
  --skills-path` prints the absolute path to that framework's bundled skills
  directory. If skills are available, read and follow their `SKILL.md` as the
  procedural source of truth instead of improvising raw CLI invocations.
- Keep the roles distinct. The repo-local `simready-foundation-*` skills author
  and update Foundation specs (requirements, capabilities, features, profiles,
  validators, adapters) and conform assets to individual feature gates. The
  external library skills drive the validate, evaluation, and packaging tooling
  that proves an asset meets a profile.
- If a needed external library or its skills are not installed, install the
  library (or ask the user to) rather than reimplementing its validation,
  evaluating, or packaging logic inside this repository.

## Authoring SimReady Assets in Blender

For the *authoring* side, NVIDIA publishes the **SimReady Blender add-on**
("CORE Artist Tools"), a public, Apache-2.0 collection of Blender add-ons for
creating SimReady assets: <https://github.com/NVIDIA/simready-blender-add-on>
(docs: <https://nvidia.github.io/simready-blender-add-on/>).

When a user or artist needs to *create* SimReady-compliant assets in Blender -
rather than validate, evaluation, package, or conform an existing USD - point them
to this add-on. It is installed inside Blender, not via `pip`, and it ships no
agent skills: build the package with
`python CORE_SysUtils/package/make_core_zip.py` (or download the latest release),
then install the resulting `SimReady_Blender_CORE_<version>.zip` from Blender's
`Edit > Preferences > Install`. It targets Blender 5.1.

The add-on is complementary to the conform/validate/evaluation/package workflows:
it helps an artist author SimReady-ready geometry, materials, and metadata at the
DCC stage, and the Foundation skills and external libraries then validate, repair,
evaluation, and package the exported USD.

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
6. `nv_core/sr_specs/docs/guides/evaluate/evaluate.md` - runtime validation
   entrypoint and links to planning, execution, reports, and test-family details.
7. The specific profile, feature, requirement, and validator files touched by
   the task.

Treat the profile TOML files under
`nv_core/tiers/*/simready/foundation/tier_*/profiles/` as the machine-readable
profile source of truth. Each profile version selects features and capabilities
by dotted ID or wildcard selector. The Core tier currently ships 16 profiles
from `robotics_prop.toml`, `robot_body.toml`, `robot_gripper.toml`,
`assembly.toml`, `robot_assembly.toml`, `nurec.toml`, `material.toml`,
`open_taxonomy_profiles.toml`, and `package_profiles.toml`; there is no single aggregate `profiles.toml`, and the
validator loads every configured tier profile directory. Profile markdown is an
authoring guide and must stay in sync with the profile TOML files, but
validators consume the TOML selector lists.

Each tier's `features/`, `capabilities/`, and `profiles/` directories hold its
Foundations 2 catalog. Every manifest records its Foundations 1 identity under
`legacy_identity`, and the tier's `catalog-map.json` maps each Foundations 1
`(id, version)` pair to its dotted ID. Use Foundations 1 IDs such as
`FET_003_PHYSX` only to read historical reports, asset stamps, or external
contracts. After adding or renaming a contract page, run
`nv_core/tiers/_tooling/migrate_foundations2_catalog.py --write-hubs` to
regenerate the shared `features.md` and `capabilities.md` hubs; never hand-edit
those hubs. The script's other modes performed the one-time Foundations 1
relocation.

## Foundations 2 Contract

- A feature's `id` is its only identity field and has two or three dotted
  segments: `<name>[.<runtime>].<version>`. Do not duplicate `name`, `runtime`, or
  `version` beside it in new manifests.
- The version segment is an opaque contract token. Preserve leading zeroes and
  do not assume semantic-version ordering.
- Runtime-tested FETs declare tests, additional requirements, and adapters. A
  testless FET must be `source=true` and be named by at least one tested derived
  FET. Any other testless published contract projects to a `CAP` ID.
- `source_feature` records classification/provenance and does not inherit
  source requirements. Use `dependencies` when the source contract must also
  validate.
- Feature and capability selectors have one to three segments. Two-segment
  selectors match a runtime or a neutral version; a bare name selects every
  runtime and version. `FET004.*` selects the `FET004` family across runtimes and
  versions, and `FET004.PhysX.*` narrows that family to PhysX. Capability IDs
  and selectors use the identical scheme with a `CAP` prefix, and a
  runtime-neutral capability omits the runtime segment.
- Resolve selectors against the available catalog before validation. Sort and
  deduplicate matches deterministically; a required match wins when the same
  item is also selected optionally.
- An unmatched required selector is an error. An unmatched optional selector
  is permitted and records no validation obligation.
- Validation targets are caller supplied. Validate the same asset against each
  requested `(profile, version)` independently; do not infer one exclusive
  profile from asset metadata.
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/contracts.py`
  is the reference parser and resolver for this contract.

## Robotics-Prop Profile Workflow

`Robotics-Prop` is the current prop workflow target. `robotics_prop.toml` is the
source of truth for which features and capabilities each version selects; read it
and the shared profile index for exact selectors rather than trusting a copy here.
In outline: the `3.x` line builds up Core, minimal visual, rigid body, grasp, and
material contracts, then adds runtime variants, required packaging
(`CAP031`/`CAP033`), semantic labels, and optional Isaac composition; `4.0.0` is
the Foundations 8.0 release (required `FET006_Materials`, optional OpenPBR,
MDL, and display color); `5.0.0` is the consolidated Foundations 10.0 contract,
adding required Object Forward and material coverage with the FET006 versions
that leave `VM.MAT.001` out.

At `FET003_RigidBody.PhysX.0-4-0` and `FET004_Multibody.PhysX.0-4-0`,
rigid-body work stays in the FET003 family and multibody joint work stays in
the FET004 family. Single-rigid-body props satisfy prop physics through
`FET003_RigidBody`; `FET004_Multibody` is separate multibody
work and should be validated only for props intentionally authored with
multiple rigid bodies and joints.

When reasoning about a prop profile, inspect these files together:

- the per-profile TOML in its owning tier's `profiles/` directory
- `nv_core/sr_specs/docs/shared/profiles/profiles.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/robotics-prop.md`
- `nv_core/sr_specs/docs/shared/features/feature-dependency-graph.md`
- the selected feature and capability JSON manifests in the core tier
  `features/` and `capabilities/` directories

Run conformance work one feature gate at a time. The normal prop repair order is:

```text
validate selected profile
-> simready-foundation-conform-fet-000-standard
-> simready-foundation-conform-fet-001-standard
-> selected exact FET003 skill (simready-foundation-conform-fet-003-standard, simready-foundation-conform-fet-003-physx, or simready-foundation-conform-fet-003-newton)
-> selected exact FET004 skill (only when the selected profile or asset intent requires multibody physics)
-> simready-foundation-conform-fet-005-standard
-> simready-foundation-conform-fet-006-standard or simready-foundation-conform-fet-006-mdl
-> simready-foundation-conform-fet-031-standard (only when the profile selects CAP033_SimReadyPackage)
-> simready-foundation-conform-fet-033-standard (only when the profile selects CAP033_SimReadyPackage)
-> validate selected profile again
```

For FET004 multibody work, use the selected exact FET004 skill
after the FET003 rigid-body gate and before grasp/material work. This skill must
not create geometry to pass the multibody feature; it may only use existing USD
geometry/part hierarchy and repair physics schemas, joints, articulations, and
relationships. For single-rigid-body props, FET004 is not applicable unless the
user or selected profile explicitly requires a multibody assembly.

When a selected profile or user request explicitly includes
`CAP007_NonVisualMaterials` non-visual sensor materials, run
`simready-foundation-conform-fet-007-standard` after the selected exact FET006
material skill. `CAP007_NonVisualMaterials` is optional in the
`Robotics-Prop` profile.

Run the SimReady packaging gates only when the selected profile selects
`CAP033_SimReadyPackage` (check the profile TOML). Run them after material
conformance and in dependency order: `simready-foundation-conform-fet-031-standard`
(self-contained package source, `AA.001`) first, then
`simready-foundation-conform-fet-033-standard`, which depends on it and covers the
thumbnail (`SR.002`) and provenance metadata. Provenance is `SR.003` (nested
root-layer `SimReady_Metadata`) at `CAP033` version `0-3-0` and `SR.004` (the
union of root-layer `customLayerData` and an optional same-directory
`<usd_stem>.json` sidecar, with no field authored in both) at `0-4-0`; `SR.001`
preserves the earlier root-layer-only Core identity contract. The `SR.003` and
`SR.004` requirement docs and the fet-033 skill own the exact field set (including
`qcode`, `rigid_body_count`, `asset_extents`, and `mass`, which a `Material`-rooted
asset zeroes). Derive the physical fields from the actual asset rather than
fabricating them, and report a blocker if a value cannot be derived.

For `Robot-Body` or `Robot-Gripper` workflows, use
`simready-foundation-conform-fet-000-isaac` (`CAP000_Core.Isaac`) for Isaac
packaging when selected, then `simready-foundation-conform-fet-021-isaac`
(`CAP021_RobotCore.Isaac`) for the robot identity gate after the multibody
physics gate is in shape and before driven-joint, articulation, or
Isaac-composition follow-up work.

New robot profile versions should prefer `CAP021_RobotCore.Isaac.0-3-0` for
robot identity and `CAP000_Core.Isaac.0-1-0` for Isaac packaging, thumbnail,
and physics-layer requirements.

`FET004_Multibody.RobotPhysX` is deprecated and has no current in-repository
profile consumer. It is retained only for compatibility with historical or
external contracts. Never add it to a new profile version. New PhysX profile
versions must use `FET003_RigidBody.PhysX.0-4-0` plus
`FET004_Multibody.PhysX.0-4-0`.

Use the exact base-articulation skill once the robot body/joint topology is in
shape: `simready-foundation-conform-fet-024-standard`,
`simready-foundation-conform-fet-024-physx`, or
`simready-foundation-conform-fet-024-newton`. The OpenUSD capability
(`CAP024_BaseArticulation`) checks the single articulation root; the
PhysX capability also needs PhysX collision-clearance evidence for non-adjacent
links; the Newton capability checks Newton articulation-root configuration.

`CAP023_RobotMaterials.Isaac` is deprecated. `Robot-Body` versions `2.0.0` through
`3.1.0` select it as optional and `4.0.0` leaves it out; do not add it to new profile
versions. For an asset validated against one of those versions,
`simready-foundation-conform-fet-023-isaac` repairs it for compatibility and leaves
materials inside instanced parts where they are.

When `Robot-Body` version `2.2.0` or later selects optional
`CAP025_RosBridge.Ros.0-1-0`, run `simready-foundation-conform-fet-025-ros`
after Isaac composition and before the final profile validation. Do not
auto-author a ROS graph without the intended publishers/subscribers.

## Robot Profile Workflow

Consolidated robot profiles start at version `2.0.0`:

- `Robot-Body` starts at version `2.0.0` (`robot_body.toml`): required
  minimal-visual and rigid-body contracts, with multibody, driven-joint,
  articulation, and the PhysX/Isaac runtime contracts optional. Later versions
  add the runtime variants, required packaging (`CAP031`/`CAP033`), an optional
  ROS bridge (`CAP025_RosBridge.Ros`), the `SR.004` provenance union, the
  Foundations 8.0 material set (`3.0.0`), Object Forward (`3.1.0`), and material
  coverage; `4.0.0` also drops `CAP023_RobotMaterials.Isaac`.
- `Robot-Gripper` starts at version `2.0.0` (`robot_gripper.toml`): the same base
  set with `CAP021_RobotCore.Isaac` and optional gripper contracts
  (`FET028_Gripper.*`, `CAP028_Gripper.MuJoCo`), tracking `Robot-Body` for the
  packaging, provenance, Foundations 8.0 material, and material-coverage changes.

Profile TOML selectors use dotted IDs whose version segment is the published
semantic version with hyphens (`0.4.0` becomes `0-4-0`). An earlier experiment
with bare integer versions such as `FET004_Multibody.PhysX.1` was reverted;
never reintroduce them. Inspect `robot_body.toml` and `robot_gripper.toml` for
exact selectors.

Stop at the first failing feature gate unless the user explicitly asks for a
broader best-effort pass. Count a feature skill as successful when its selected
feature passes, even if the full profile still fails on a later or unrelated
feature.

## Assembly Profile Workflow

`Assembly` version `0.1.0` (`assembly.toml`) validates a stage that composes
two or more published assets and declares how their mate sites are paired. It is
not robot-specific: an arm with a gripper and a stack of interlocking pallets
are both assemblies. Child assets are validated against their own profiles
(`Robot-Body`, `Robot-Gripper`, `Robotics-Prop`, or `Assembly`). The assembly
profile selects `CAP026_Mates.0-1-0` to validate their mate sites; the
existing child profile versions do not select that capability.

`Robot-Assembly` version `0.1.0` (`robot_assembly.toml`) is the robot form of
the same contract: it requires `CAP029_ConnectionJoint.0-1-0` and
`CAP024_BaseArticulation.0-1-0`, so every connection is jointed and exactly one
articulation root survives on the composed stage; `FET022_DrivenJoints.0-2-0` is
optional. Runtime variants are validated on each child asset against its own
profile, not on the composed stage.

Assemblies nest. The default prim is `kind = "assembly"`, and each child asset
root is `component` or `assembly` with a contiguous model hierarchy (`CN.012`).
A nested assembly's connections occupy the sites they pair (`CN.007`); its
unpaired sites stay available. A part that contains a joint joins only through a
`jointed` connection (`CN.011`).

`simready:mate:realization` on each connection is the scope selector. It takes
`compound` (one shared mate body, composition holds the pairing, no joint) or
`jointed` (two distinct mate bodies, an authored `UsdPhysicsFixedJoint` holds
the pairing). An assembly may mix both on one stage.

A mate body is the nearest ancestor with an *enabled* `PhysicsRigidBodyAPI`
(`MC.003`), so a compound assembly demotes each part with
`physics:rigidBodyEnabled = false` rather than deleting the schema, and carries
the enabled rigid body plus the summed `physics:mass` on an assembly-local
compound body under the default prim (`CN.011`). Never author the aggregate on
a referenced part root or on the default prim, and never fabricate it: sum it
from the composed parts, stopping at the first mass-authoring prim on each
branch. The aggregate may be omitted only when every part's mass sits on its
colliders, which the runtime sums onto the compound body by itself; mass on a
demoted part root is inert and still requires the aggregate. In a mixed assembly
each group of compound connections gets its own compound body.

The assembly repair order is:

```text
validate Assembly or Robot-Assembly profile
-> simready-foundation-conform-fet-026-standard (on each child asset, if sites are missing)
-> simready-foundation-conform-fet-027-standard
-> simready-foundation-conform-fet-029-standard (only when a connection is jointed)
-> selected exact FET_029 runtime skill (simready-foundation-conform-fet-029-physx, -newton, or -mujoco; Assembly only)
-> simready-foundation-conform-fet-024-standard (Robot-Assembly)
-> validate the selected profile again
```

An assembly built entirely from `compound` connections stops after
`CAP027_Connections`; the `CAP029_ConnectionJoint.*` capabilities are optional and do not apply to it.

The connection joint is **authored**, not runtime-inferred. `CN.009` requires
the joint prim plus `rel simready:mate:joint` on the connection pointing at it,
so a consumer resolves the joint by lookup instead of searching for a matching
body pair. `CN.009` also requires explicit `physics:breakForce` and
`physics:breakTorque`. Both are `UsdPhysicsJoint` attributes that every
`UsdPhysics` runtime reads, so attach strength belongs to the Standard gate and
the `CAP029_ConnectionJoint.*` runtime variants cover only their own namespaces. This keeps the
assembly rigid in a runtime that does not read
`simready:mate:`, and it satisfies `RB.012` for nested rigid bodies so an
assembly can be nested inside another assembly. A SimReady-aware runtime still
owns the joint: it follows the relationship and sets
`physics:jointEnabled = false`, retunes, or deletes the prim. Do not author
custom attributes to describe that lifecycle.

Author one neutral `UsdPhysicsFixedJoint` in the assembly physics layer so
`simready:mate:joint` resolves with runtime payloads unloaded. The `CAP029_ConnectionJoint.*`
runtime variants overlay attributes onto that same prim, typically from a
`runnables/physics/{physx,newton,mujoco}` layer; never create a second joint per
runtime.

A connection between two articulated mate bodies **fuses** the two articulations
into one. The connection joint is part of that articulation, so
`physics:excludeFromArticulation` stays false or unset, and the assembly gives up
the plug asset's `PhysicsArticulationRootAPI` so exactly one root survives on
the composed stage (`CN.PHYSX.001`, `CN.NEWTON.001`). That is a separate edit from
deactivating the plug's world pin, and often a different prim: an asset may
carry the root on its enclosing prim or on its internal fixed root joint.
`physics:excludeFromArticulation = true` belongs to a mechanism that closes a
loop inside one asset, such as a four-bar linkage (`DJ.011`).

Static validators for `MC.*` and `CN.*` are implemented in
`rules_and_reqs/assembly/mates/validation.py` and
`rules_and_reqs/assembly/connections/validation.py`, share traversal helpers in
`rules_and_reqs/assembly/utils.py`, and are registered in
`rules_and_reqs/__init__.py`, so validating against `Assembly@0.1.0` exercises all
22 rules. The mate-body walk (`MC.003`) reads the enabled state rather than the
applied schema, and the pruned mass sum is shared by `CN.005` and `CN.011`.

Current repo-local skills live under the agent-agnostic skill tree:

```text
skills/<skill-name>/SKILL.md
```

`.agents/skills`, `.codex/skills`, and `.claude/skills` are compatibility
links to `../skills`. When updating a SimReady skill, edit the `skills` source
of truth, including bundled `references/`, `assets/`, `evals/`, and
`assets/openai.yaml` metadata. Deterministic helper scripts are bundled under
`assets/scripts/` in this repository so the external Skill Evaluator (`skillevaluator`)
does not treat tool helpers as top-level skill structure.

| Skill | Purpose |
|---|---|
| `simready-foundation-conform-fet-000-standard` | Repair exact `CAP000_Core` Core conformance. |
| `simready-foundation-conform-fet-000-physx` | Repair exact `CAP000_Core.PhysX` PhysX runtime variant scaffolding (variant set, `runnables/physics/physx` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-newton` | Repair exact `CAP000_Core.Newton` Newton runtime variant scaffolding (variant set, `runnables/physics/newton` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-mujoco` | Repair exact `CAP000_Core.MuJoCo` MuJoCo runtime variant scaffolding (variant set, `runnables/physics/mujoco` payload, SimReady variant metadata). |
| `simready-foundation-conform-fet-000-isaac` | Repair exact `CAP000_Core.Isaac` Isaac packaging Core conformance (clean folder, thumbnail, physics source-layer placement). |
| `simready-foundation-conform-fet-001-standard` | Repair exact `FET001_MinimalPlaceableVisual` Minimal/OpenUSD asset conformance. |
| `simready-foundation-conform-fet-002-standard` | Repair exact `CAP002_PosableBodies` conformance. |
| `simready-foundation-conform-fet-003-mujoco` | Repair exact `CAP003_RigidBody.MuJoCo` rigid-body conformance. |
| `simready-foundation-conform-fet-003-newton` | Repair exact `FET003_RigidBody.Newton` rigid-body conformance. |
| `simready-foundation-conform-fet-003-physx` | Repair exact `FET003_RigidBody.PhysX` rigid-body conformance. |
| `simready-foundation-conform-fet-003-standard` | Repair exact `FET003_RigidBody` rigid-body conformance. |
| `simready-foundation-conform-fet-004-mujoco` | Repair exact `CAP004_Multibody.MuJoCo` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-newton` | Repair exact `FET004_Multibody.Newton` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-physx` | Repair exact `FET004_Multibody.PhysX` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-004-robot-mujoco` | Repair exact `CAP004_Multibody.RobotMuJoCo` robot MuJoCo multibody conformance. |
| `simready-foundation-conform-fet-004-robot-newton` | Repair exact `FET004_Multibody.RobotNewton` robot Newton multibody conformance. |
| `simready-foundation-conform-fet-004-robot-physx` | Repair deprecated `FET004_Multibody.RobotPhysX` conformance for compatibility with historical or external contracts only. |
| `simready-foundation-conform-fet-004-standard` | Repair exact `FET004_Multibody` multibody conformance without creating geometry. |
| `simready-foundation-conform-fet-005-standard` | Repair exact `FET005_Grasp` vision-guided grasp conformance. |
| `simready-foundation-conform-fet-006-mdl` | Repair exact `FET006_Materials.MDL` MDL material conformance. |
| `simready-foundation-conform-fet-006-openpbr` | Repair exact `FET006_Materials.Openpbr` OpenPBR (MaterialX) material conformance. |
| `simready-foundation-conform-fet-006-standard` | Repair exact `FET006_Materials` USDPreviewSurface material conformance, including `VM.MAT.001` through version 0-2-0. |
| `simready-foundation-conform-fet-007-standard` | Repair exact `CAP007_NonVisualMaterials` non-visual sensor material conformance. |
| `simready-foundation-conform-fet-008-object-forward` | Author exact `FET008_ObjectForward` Object Forward (`AF.001`) from a caller-provided vector or visual evidence. |
| `simready-foundation-conform-fet-009-standard` | Repair exact `FET009_MaterialCoverage` rendered material coverage by binding uncovered geometry to the asset's own materials. |
| `simready-foundation-conform-fet-010-standard` | Repair exact `FET010_DisplayColor` display-color (`primvars:displayColor`) conformance (`DISP.001`, `DISP.002`). |
| `simready-foundation-conform-fet-011-standard` | Repair exact `FET011_SemanticLabels` semantic-label conformance. |
| `simready-foundation-conform-fet-013-standard` | Repair exact `FET013_MultiRepresentationVisual` Representation variant-set conformance (`AV.001`-`AV.010`). |
| `simready-foundation-conform-fet-014-standard` | Repair exact `FET014_MeshVariant` visual-only mesh-variant conformance (`AV.001`-`AV.010`). |
| `simready-foundation-conform-fet-015-standard` | Repair exact `FET015_CollisionVariant` collision variant-set conformance (`AV.001`-`AV.010`). |
| `simready-foundation-conform-fet-016-standard` | Repair exact `FET016_AppearanceVariant` appearance variant-set conformance (`AV.001`-`AV.010`). |
| `simready-foundation-conform-fet-021-isaac` | Repair exact `CAP021_RobotCore.Isaac` Isaac robot-core identity conformance. |
| `simready-foundation-conform-fet-022-isaac` | Repair exact `FET022_DrivenJoints.Isaac` driven-joint conformance. |
| `simready-foundation-conform-fet-022-mujoco` | Repair exact `CAP022_DrivenJoints.MuJoCo` driven-joint conformance. |
| `simready-foundation-conform-fet-022-newton` | Repair exact `FET022_DrivenJoints.Newton` driven-joint conformance. |
| `simready-foundation-conform-fet-022-physx` | Repair exact `FET022_DrivenJoints.PhysX` driven-joint conformance. |
| `simready-foundation-conform-fet-022-standard` | Repair exact `FET022_DrivenJoints` driven-joint conformance. |
| `simready-foundation-conform-fet-023-isaac` | Repair deprecated `CAP023_RobotMaterials.Isaac` robot material organization for compatibility with `Robot-Body` `2.0.0` through `3.1.0` only. |
| `simready-foundation-conform-fet-024-mujoco` | Repair exact `CAP024_BaseArticulation.MuJoCo` base-articulation conformance. |
| `simready-foundation-conform-fet-024-newton` | Repair exact `CAP024_BaseArticulation.Newton` base-articulation conformance. |
| `simready-foundation-conform-fet-024-physx` | Repair exact `CAP024_BaseArticulation.PhysX` base-articulation conformance. |
| `simready-foundation-conform-fet-024-standard` | Repair exact `CAP024_BaseArticulation` base-articulation conformance. |
| `simready-foundation-conform-fet-025-ros` | Repair exact `CAP025_RosBridge.Ros` Isaac ROS-Ready bridge-node conformance. |
| `simready-foundation-conform-fet-026-standard` | Repair exact `CAP026_Mates` mate-site conformance. |
| `simready-foundation-conform-fet-027-standard` | Repair exact `CAP027_Connections` assembly-connection conformance (declaration plus the compound shape). |
| `simready-foundation-conform-fet-028-isaac` | Repair exact `FET028_Gripper.Isaac` Isaac gripper-site conformance. |
| `simready-foundation-conform-fet-028-mujoco` | Repair exact `CAP028_Gripper.MuJoCo` MuJoCo gripper-site conformance. |
| `simready-foundation-conform-fet-028-standard` | Repair exact `FET028_Gripper` gripper-site conformance. |
| `simready-foundation-conform-fet-029-standard` | Repair exact `CAP029_ConnectionJoint` connection multibody-physics conformance (authored fixed joint, break thresholds, payload rating). |
| `simready-foundation-conform-fet-029-physx` | Repair exact `CAP029_ConnectionJoint.PhysX` PhysX connection-joint conformance. |
| `simready-foundation-conform-fet-029-newton` | Repair exact `CAP029_ConnectionJoint.Newton` Newton connection-joint conformance. |
| `simready-foundation-conform-fet-029-mujoco` | Repair exact `CAP029_ConnectionJoint.MuJoCo` MuJoCo connection-joint conformance. |
| `simready-foundation-conform-fet-030-standard` | Repair exact `CAP030_PackagingCore` packaging core conformance. |
| `simready-foundation-conform-fet-031-standard` | Repair exact `CAP031_SelfContainedPackage` self-contained package source conformance. |
| `simready-foundation-conform-fet-032-standard` | Repair exact `CAP032_PackagingIntrospection` packaging introspection/BOM conformance. |
| `simready-foundation-conform-fet-033-standard` | Repair exact `CAP033_SimReadyPackage` Metadata conformance (thumbnail + nested `SR.003` or USD/sidecar `SR.004`). |
| `simready-foundation-conform-fet-100-isaac` | Repair exact `CAP100_IsaacComposition.Isaac` Isaac composition conformance. |
| `simready-foundation-conform-cap-102-isaac` | Repair exact `CAP102_RigidBodyCollapse.Isaac` conformance by safely collapsing eligible fixed-joint bodies without changing simulation behavior (tier_isaac). |
| `simready-foundation-conform-cap-103-isaac` | Repair exact `CAP103_VisualMeshMerge.Isaac` visual-mesh-merge conformance without changing rendering or collision behavior (tier_isaac). |
| `simready-foundation-conform-cap-104-isaac` | Repair exact `CAP104_RenderCollisionSeparation.Isaac` render-collision-separation conformance without changing active collider behavior (tier_isaac). |
| `simready-foundation-conform-cap-105-isaac` | Remove MaterialX render contexts while keeping or creating USD Preview Surface shading (tier_isaac). |

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
| `simready-foundation-add-feature-adapter` | Add a direct asset mutation path between exact feature/profile versions under `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules`. |
| `simready-foundation-update-feature-adapter` | Repair or extend existing feature adapters while preserving published upgrade paths. |
| `simready-foundation-add-runtime-test` | Add runtime testing coverage, runner expectations, commands, and evidence for features/profiles that need behavioral proof. |
| `simready-foundation-validate-foundation-change` | Audit a SimReady change across requirement docs, validators, feature manifests, profiles, adapters, runtime tests, and skill layout. |
| `simready-foundation-upgrade-legacy-tier` | Define a new tier, expand an existing tier, or upgrade a legacy/AIF/DSX tier to Foundations 2 while preserving published compatibility. |

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
line and should tell the user to rerun `FET005_Grasp` repair with vision enabled. Use
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
9. Create a new immutable feature ID or profile version for contract changes.

Feature IDs are immutable once published or selected by a profile. When
updating an existing feature, create a new markdown file and JSON manifest with
a new version segment in the dotted ID. Do not silently mutate the old feature
documentation or JSON unless the user explicitly asks for an editorial fix to
an unpublished/draft feature.

The old feature ID should remain available so existing profiles continue to
resolve their original contract. Profiles can adopt the new ID using either an
exact selector or an intentional wildcard selector.

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
- installed `simready.tier` descriptors - the default source for requirements,
  features, profiles, CIP adapters, and evaluation metadata. Non-empty
  `project_config.toml` paths are explicit source-development overrides.
- `nv_core/tiers/*/simready/foundation/tier_*/rules_and_reqs/` - capability docs,
  requirement pages, and Python validators.
- `nv_core/tiers/*/simready/foundation/tier_*/features/` and `capabilities/` -
  tier-owned dotted FET and CAP docs and JSON manifests.
- `nv_core/tiers/*/simready/foundation/tier_*/profiles/` - tier-owned profile
  TOMLs and authoring guides. New profiles use one TOML each; the legacy
  `open_taxonomy_profiles.toml` and `package_profiles.toml` catalogs group
  related profiles. There is no single consolidated `profiles.toml`.
- `nv_core/tiers/*/simready/foundation/tier_*/catalog-map.json` - the
  Foundations 1 to Foundations 2 ID map for the tier's contracts.
- `nv_core/tiers/_tooling/migrate_foundations2_catalog.py` - the Foundations 1
  catalog migration tool; `--write-hubs` regenerates the shared feature and
  capability hub pages.
- `nv_core/sr_specs/docs/shared/` - cross-tier section hubs (rules_and_reqs,
  features, profiles) and the feature dependency graph. Per-tier badge includes
  live under each tier's `rules_and_reqs/_includes/`.
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
  profile/feature mutation adapters under `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules`.
- `nv_core/sr_specs/docs/guides/evaluate/evaluate.md` - Evaluate runtime
  test entrypoint and links to pipeline, execution, report, and test guides.

## Validation Expectations

Validation should align with requirement IDs and feature manifests:

- Requirement docs should describe the rule, why it matters, examples, and how
  to comply.
- Validators should register against the matching requirement IDs.
- Capability definitions use `CAP`-prefixed IDs and own reusable static
  requirement bundles.
- Feature JSON should use the dotted FET ID as its sole identity. A runtime
  FET includes non-empty runtime tests, additional requirements, and adapters.
  A testless FET is valid only as `source=true` with tested derived FETs;
  otherwise it must be modeled as a capability.
- Feature docs should explain the runtime use case and group requirements by
  capability.
- Profiles should resolve their feature and capability selectors consistently,
  including wildcard and optional semantics.
- Existing feature IDs should remain immutable. New behavior or changed
  requirements should be represented by a new feature markdown file and JSON
  manifest with a new dotted ID version segment.

Use failures for objective contract violations. Use warnings for best-practice
guidance, portability concerns, or checks that may have legitimate exceptions.
Call out manual review when a requirement is subjective, such as "logical"
hierarchy or pivot placement.

## Current Repository Notes

Parts of the repository are still in progress. Verified as of 2026-08-18:

- Capability status badges in `rules_and_reqs/_includes/badges/` cover 22
  capabilities: 12 Development, 8 Draft, and only 2 Complete (geometry,
  hierarchy). Treat Draft capabilities as unstable.
- Not every documented requirement has an executable validator. Of the 169
  requirement docs, most are referenced by a validator; the rest are
  documentation only, mostly geometry authoring guidance (for example
  `VG.003`-`VG.006`, `VG.009`-`VG.011`, `VG.013`, `VG.015`-`VG.022`, `VG.024`,
  `VG.RTX.001`) plus a few such as `AA.OV.001`, `JT.ART.001`, `PKG.CONF.002`,
  `RB.008`, and `HI.007`, which is an intentional numbering placeholder.
- The Core tier's 16 profiles all have authoring markdown except `Package`,
  `Package-NoBOM`, and `Package-Candidate`, which are documented only in the
  shared profile index.
- Feature adapters in `nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules`
  and `nv_core/cip_specs/asset_handler_modules` register exact dotted
  Foundations 2 endpoints.
- The Foundations 1 catalog has been migrated in place: static contracts became
  CAP-prefixed capabilities, contracts with exact runtime-test mappings became
  dotted FETs, and profiles moved to selector lists. Assets, reports, and
  external contracts can still carry Foundations 1 IDs; resolve them through
  `catalog-map.json` rather than reintroducing them.
- Some requirement pages, especially newer robot-oriented ones, do not yet use
  the same metadata table style as the older requirement pages.
- The Kit `workspace validate`, `workspace upgrade`, and
  `workspace runtime_tests` commands appear in guides and skills, but no
  implementation or full flag syntax exists in this repository. Use
  `simready-validate`, `simready-package`, and `simready-evaluate` for
  standalone work.
- Tier core targets `requires-python = ">=3.11,<3.14"`
  (`nv_core/tiers/simready_foundation_tier_core/pyproject.toml`). The optional
  `[isaac]` extra requires a Python 3.12 virtual environment and installs its
  public Isaac dependencies from PyPI.
- Newton-solver physics content lives in the separate
  `simready-foundation-tier-newton` package
  (`nv_core/tiers/simready_foundation_tier_newton`), not in tier core. It owns
  the `NEWTON.*` requirements + validators (base_articulation, driven_joints,
  materials, rigid_bodies), four Newton features, and two Newton capabilities. It is
  **validation/base-package independent of tier core**: no base dependency or
  cross-tier validation-code import (shared validator helpers are duplicated in
  `.../tier_newton/rules_and_reqs/_common.py`). The optional Newton `evaluate`
  extra uses locally owned `placement_compat` and
  `articulation_phases.error_utils` helpers. No Core runtime-test module is
  imported now; the neutral overlay API remains available for future declared reuse.
  Newton procedures/backend code remain locally owned; Core never depends on
  or imports the Newton suite. Its contracts reference core
  requirement/capability IDs as content, resolved from the merged registry when
  both tiers are installed, so validate Newton gates with both tiers present.
  The Newton runtime-variant scaffolding (`RV.004`-`RV.006`) and cross-runtime
  purity (`RV.010`-`RV.011`) stay in the core `runtime_variants` capability. The
  Robot-Body and Robot-Gripper `4.0.0` require the Newton rigid-body, multibody,
  driven-joint, Core, and articulation contracts. Earlier robot versions and
  the prop profiles select Newton optionally.
- Isaac static-optimization content lives in the separate
  `simready-foundation-tier-isaac` package
  (`nv_core/tiers/simready_foundation_tier_isaac`), not in tier core. It owns
  four Isaac capabilities (`CAP102_RigidBodyCollapse.Isaac`,
  `CAP103_VisualMeshMerge.Isaac`, `CAP104_RenderCollisionSeparation.Isaac`,
  `CAP105_MaterialXRemoval.Isaac`) with requirements `OPT.001`-`OPT.004`.
  `Asset-Optimization@1.0.0` selects the first three; `1.1.0` adds MaterialX
  removal. The tier provides four asset-handler adapters
  (`fixed_joint_rigid_body_merge`, `rigid_body_visual_mesh_merge`,
  `remove_inactive_render_collision_schemas`, `remove_materialx_shaders`) and
  the `simready-foundation-conform-cap-10{2,3,4,5}-isaac` skills listed above. It
  depends on Core only for the shared catalog and validation infrastructure;
  validate `Asset-Optimization` gates with both Core and Isaac tiers installed.
  Its own `README.md` is the tier's authoring source of truth.

Do not assume the docs are complete just because a file exists. Keep markdown,
JSON manifests, TOML profiles, and validation code synchronized when making
changes.
