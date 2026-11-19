# Changelist

Release history for the SimReady Foundation. Versions use the
`YYYY.MM.patch` scheme and correspond to the `release-<version>` branches.
The current version is recorded in `VERSION.md`.

Entries are newest first.

---

## 2026.10.0 — October 2026

Newton is now required for robot profiles. This release also adds asset
variation, material coverage, object affordance, and Isaac optimization
contracts.

### Added

#### Newton required for robot profiles
* `Robot-Body@4.0.0` and `Robot-Gripper@4.0.0` require
  `FET003_RigidBody.Newton.0-1-0`, `FET004_Multibody.Newton.0-1-0`,
  `FET022_DrivenJoints.Newton.0-1-0`, `CAP000_Core.Newton.0-2-0`, and
  `CAP024_BaseArticulation.Newton.0-1-0`. Install the Newton tier alongside
  Core to validate an asset against either profile.
* Newton contracts stay optional in `Robotics-Prop@5.0.0`.

#### Asset variation
* `FET013_MultiRepresentationVisual.0-1-0`, `FET014_MeshVariant.0-1-0`,
  `FET015_CollisionVariant.0-1-0`, and `FET016_AppearanceVariant.0-1-0`.
  Each groups existing alternates into a variant set and carries
  `AV.001`–`AV.010`.

#### Materials
* `FET006_Materials.0-3-0`, `FET006_Materials.MDL.0-3-0`, and
  `FET006_Materials.Openpbr.0-2-0`.
* `FET009_MaterialCoverage.0-1-0` checks that rendered geometry is bound to a
  material.
* `Material@1.0.0`, a Core tier profile for library materials.

#### Object affordances
* `CAP039_ObjectAffordances.0-1-0` defines a fixed set of affordance labels
  (`AFF.001`, `AFF.002`). No profile selects it yet.

#### Isaac asset optimization
* `CAP102_RigidBodyCollapse.Isaac.0-1-0`,
  `CAP103_VisualMeshMerge.Isaac.0-1-0`, and
  `CAP104_RenderCollisionSeparation.Isaac.0-1-0`, carrying `OPT.001`–`OPT.003`.
* `Asset-Optimization@1.0.0`, an Isaac tier profile that selects all three. It
  applies to props and robots, whatever their main profile.

#### Runtime variant Core contracts
* `CAP000_Core.PhysX.0-2-0`, `CAP000_Core.Newton.0-2-0`,
  `CAP000_Core.MuJoCo.0-2-0`, and `CAP000_Core.Isaac.0-2-0`.

#### Authoring guides
* Sensor profile guides for camera, IMU, joint, and lidar.

### Changed

* `Assembly` and `Robot-Assembly` are renumbered to `0.1.0`. Both were
  introduced on the `2026.09.0` branch, so no previously published profile
  version changed.

---

## 2026.09.0 — September 2026

Tier-split documentation assembly and canonical contract route migration.

### Changed

#### Documentation routes and compatibility redirects
* Documentation sources are assembled from per-tier packages (`nv_core/tiers/`)
  and the shared overlay (`nv_core/sr_specs/docs/shared/`) into
  `nv_core/sr_specs/_build/docs-src` via `nv_core/tiers/_tooling/assemble_docs.py`.
* Published `2026.06.0` feature routes under `features/` were split by runtime
  into canonical `FET_<family>_<runtime>` routes in `2026.08.0` and into dotted
  Foundations 2 contract routes (`features/FET*` and `capabilities/CAP*`).
  `assemble_docs.py` emits compatibility redirect pages at the historical
  `features/FET_*` docnames so existing links and bookmarks continue to resolve:
  * `features/FET_000-base_neutral-0.1.0-core` -> `features/FET_000_STANDARD` (`capabilities/CAP000_Core`)
  * `features/FET_001-minimal` -> `features/FET_001_STANDARD` (`features/FET001_MinimalPlaceableVisual`)
  * `features/FET_002-posable_bodies` -> `features/FET_002_STANDARD` (`capabilities/CAP002_PosableBodies`)
  * `features/FET_003-rigid_body_physics` -> `features/FET_003_STANDARD`, `features/FET_003_PHYSX`, `features/FET_003_NEWTON`, `features/FET_003_MUJOCO` (`features/FET003_RigidBody`)
  * `features/FET_004-simulate_multi_body_physics` -> `features/FET_004_STANDARD`, `features/FET_004_PHYSX`, `features/FET_004_NEWTON`, `features/FET_004_MUJOCO`, `features/FET_004_ROBOT_PHYSX`, `features/FET_004_ROBOT_NEWTON`, `features/FET_004_ROBOT_MUJOCO` (`features/FET004_Multibody`)
  * `features/FET_005-simulate_grasp_physics` -> `features/FET_005_STANDARD` (`features/FET005_Grasp`)
  * `features/FET_006-materials` -> `features/FET_006_STANDARD`, `features/FET_006_MDL`, `features/FET_006_OPENPBR` (`features/FET006_Materials`)
  * `features/FET_007-nonvisual_materials` -> `features/FET_007_STANDARD` (`capabilities/CAP007_NonVisualMaterials`)
  * `features/FET_011-semantic_labels` -> `features/FET_011_STANDARD`, `features/FET_011_RTX` (`features/FET011_SemanticLabels`)
  * `features/FET_021-robot_core` -> `features/FET_021_ISAAC` (`capabilities/CAP021_RobotCore.Isaac`)
  * `features/FET_022-driven_joints` -> `features/FET_022_STANDARD`, `features/FET_022_PHYSX`, `features/FET_022_NEWTON`, `features/FET_022_MUJOCO`, `features/FET_022_ISAAC` (`features/FET022_DrivenJoints`)
  * `features/FET_023-robot_materials` -> `features/FET_023_ISAAC` (`capabilities/CAP023_RobotMaterials.Isaac`)
  * `features/FET_024-base_articulation` -> `features/FET_024_STANDARD`, `features/FET_024_PHYSX`, `features/FET_024_NEWTON`, `features/FET_024_MUJOCO` (`capabilities/CAP024_BaseArticulation`)
  * `features/FET_030-packaging_core` -> `features/FET_030_STANDARD` (`capabilities/CAP030_PackagingCore`)
  * `features/FET_031-package_self_contained` -> `features/FET_031_STANDARD` (`capabilities/CAP031_SelfContainedPackage`)
  * `features/FET_032-packaging_introspection` -> `features/FET_032_STANDARD` (`capabilities/CAP032_PackagingIntrospection`)
  * `features/FET_033-simready_packaging` -> `features/FET_033_STANDARD` (`capabilities/CAP033_SimReadyPackage`)
  * `features/FET_100-isaacsim-0.1.0-composition` -> `features/FET_100_ISAAC` (`capabilities/CAP100_IsaacComposition.Isaac`)

---

## 2026.07.0 — July 2026

Multiphysics Foundations release. One SimReady prop can carry isolated PhysX,
Newton, and MuJoCo physics payloads through USD runtime variants, with matching
features, validators, samples, and authoring docs.

### Added

#### Multiple physics solvers (runtime variants)
* Runtime Variants capability (`RV.001`–`RV.011`): per-runtime variant sets,
  payload locations under `runnables/physics/`, variant metadata, section
  purity, and composed-stage isolation.
* Runtime Physics Isolation Matrix documenting allow / forbid policy per
  selected solver (PhysX, Newton, MuJoCo, or neutral).
* Core runtime scaffolding features: `FET_000_PHYSX`, `FET_000_NEWTON`,
  `FET_000_MUJOCO`.
* Rigid-body and multibody runtime features: `FET_003_*` / `FET_004_*` for
  PhysX, Newton, and MuJoCo, including Newton collider, mass, material, and
  drive schemas.
* Optional runtime-variant feature bundles on `Robotics-Prop@3.1.0` and
  `Prop-Robotics-Physx@2.2.0` (and related neutral/physx profile versions).
* Feature `runtime` field so `simready-validate` enables the matching physics
  variant before checking solver-specific rules.
* Reference samples with PhysX + Newton + MuJoCo payloads:
  `obs_orange_a02` (unibody) and `obs_electricians_large_tool_box_a01`
  (multibody).
* Guide: Multiple Physics Solvers (`guides/multiphysics_solvers.md`).

### Changed
* Prop physics authoring guides document optional runtime variant scaffolding
  and per-solver payload expectations.
* Neutral base authoring guidance tightened so solver-only values (for example
  PhysX SDF approximation) stay inside runtime payloads.

---

## 2026.06.0 — June 2026

The runtime, packaging, and robotics content release. Adds a behavioral
benchmark test suite, formal asset packaging standards, robot runtime
coverage, and a large set of spec, profile, and validator refinements on top
of the 2026.04.x packaging milestone.

### Added

#### Runtime testing & benchmark suite
* SimReady benchmark kit suite (`simready-benchmark-kit-suite`), a built-in
  runtime test suite that provides behavioral proof for features beyond static
  validators.
* Faithful runtime robot tests: closed-loop joints, IK solver, and
  gravity-on articulation behavior.
* Per-test reference docset for the runtime testing guides.
* Published SimReady test library documentation.
* `batch_maker` now consumes the `simready_search` PyPI package for job
  generation.

#### Asset packaging
* Asset Packaging Standards implementation and packaging capability.
* `simready-package` sample workflow, with a thumbnail-presence check added to
  the package sample.
* Published SimReady package library documentation and packaging
  workflow doc, incorporating product review feedback.

#### Features & requirements
* FET028 gripper runtime test pack (close, lift, shake, drop). The
  non-functional close-lift variant was dropped before release.
* FET022 joint-rooted articulation support, spec-canonical discovery, and more
  actionable diagnostics.
* `optional` tag support for multibody features in prop-specific profiles, so
  single-rigid-body props are not failed on multibody requirements.
* `com.nvidia.simready` metadata namespace.
* `VM.TEX.002` material-texture color-space requirement (albedo color space).

#### Documentation & governance
* Onboarding, acceptance, and development workflow guides.
* Spec scorecard restructure with reworked workflows, tables, and validation
  links, plus prioritized stories and governance docs.
* GitHub docs URL wired into `project_config.toml`.

### Changed
* Split the aggregate `profiles.toml` into nine per-profile TOML files under
  `profiles/`.
* Renamed the kit test suite module/dist to `simready-benchmark-kit-suite`.
* Updated the sample package to consume `simready-package`, following
  asset-validator and `usd-profiles` package updates.
* Updated USD asset validator dependencies; added a `numpy` requirement,
  `requirements.txt`, and venv setup instructions.
* Added SimReady Foundation entrypoint plugin support to the Asset Validator.
* Added a `sample_content` validation test job to the CI pipeline.
* Fixed capability requirement enum ownership.

### Fixed
* `NP.003`/`NP.005` naming/path conflict resolved and folder-layout enforcement
  corrected (bug 6243124).
* `HI.001` root-count check now excludes the Omniverse `/Render` scope.
* Sub-threshold pivot offsets now report as `SKIPPED` rather than an advisory
  warning.
* `physx_to_isaacsim`: fixed textures-folder casing mismatch in USD references.
* Fixed duplicate collider produced after the Isaac transform.
* UR10 profile and validation fixes; asset transformer update.
* Security hardening: removed benign local-path references and applied
  additional security fixes.

### Removed
* Deprecated requirement `RB.006`.
* Removed the generated `config.json` from source control.

---

## 2026.04.1 — May 2026

Patch release on top of 2026.04.0.

### Added
* Bundled conformance and authoring skills.

### Changed
* UR10 profile fixes.

### Removed
* Removed in-progress testing docs that were not ready to ship.

---

## 2026.04.0 — April 2026

The distribution milestone: SimReady validation became installable and
runnable outside the docs repository, as both a Python package and a Kit
extension.

### Added
* `simready-validate` Python package with a `python -m simready.validate`
  CLI entry point.
* Public PyPI wheel publishing via KitMaker (`deploy-python-public`), delivering
  the custom `omni.capabilities` / `simready.validate.requirements` alongside
  the package.
* SimReady Foundations Validators Kit extension.
* Initial robot specifications and related content developed from Isaac.
* Onboarding documentation and `simready-validate` usage guidance.

### Changed
* Cleanup of package dependencies and rules.
* Feature generation fixed for automatic codegen.
* Updated search library usage.
* Added SonarQube exclusions.

### Fixed
* Guarded all `PhysxSchema` usages against `None`.
* Fixed import regressions causing `ModuleNotFoundError` in PyPI-only
  environments.
* Fixed inherited material binding on an xform affecting thumbnail lighting
  rigs.
