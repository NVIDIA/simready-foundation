# Release notes

Release history for the SimReady Foundation. Public releases use a
`major.minor` product version. Repository branches and Python distributions
prefix that version with the release year, so Foundation 7.1 is published as
`2026.07.1` from the `release-2026.07.1` branch. This release version is
separate from the semantic versions assigned to individual features and
profiles. The current repository version is recorded in `VERSION.md`.

Major and minor Foundation releases are not backward-compatible with older
Foundation releases. Use documentation, tier content, and tool versions that
support the same Foundation release. Assets, profile selections, custom tiers,
and validation stamps created for an older release must be migrated as needed
and validated again before they are treated as conformant to a newer release.

Entries are newest first.

<!--
Template for a new release entry. Copy the block between the markers, fill in
the version and date, and drop any section that has no entries. Keep
"Breaking changes" and "Deprecated" even when they are empty: state NONE
rather than omitting them, so readers never have to guess whether the section
was considered.

## YYYY.MM.patch — Month YYYY

One-paragraph summary of what this release is about.

### Breaking changes
NONE

### Added

### Changed

### Deprecated
NONE

### Removed

### Fixed
-->

---

## 2026.07.1 — August 2026

Tiered distribution and multiphysics release. The specification is now
distributed as installable tier packages, so `simready-validate` discovers
requirements, features, and profiles from installed wheels instead of
filesystem paths. One SimReady prop can carry isolated PhysX, Newton, and
MuJoCo physics payloads through USD runtime variants, with matching features,
validators, samples, and authoring docs. This release supersedes 2026.07.0,
which was not shipped; its content is included here.

```{important}
Foundation 7.1 is not backward-compatible with earlier Foundation major or
minor releases. Do not mix 7.1 requirements, features, profiles, or tier
packages with content from 7.0 or earlier. Existing assets and custom tiers
must be migrated as needed and revalidated against a 7.1 profile; validation
results or stamps from an older Foundation release do not establish 7.1
conformance.
```

### Foundation 7.1 libraries

Use the following independently versioned libraries with Foundation 7.1:

| Library | Compatible version | Purpose |
|---|---|---|
| `simready-foundation-tier-core` | `2026.7.1` | Foundation 7.1 requirements, features, profiles, validators, and bundled runtime tests. |
| `simready-validate` | `>=2026.7.0.dev1` | Static validation CLI and Python API. |
| `simready-benchmark[kit]` | `>=2026.6.6` | Runtime and behavioral testing in Kit or Isaac Sim; installed by the core tier's `benchmark` extra. |
| `simready-package` | `>=2026.6.0a1` | Package creation and pre/post validation; use the `publish` extra for WRAPP publishing. |

For a complete validation and Benchmark environment:

```bash
pip install "simready-foundation-tier-core[benchmark]==2026.7.1" "simready-validate>=2026.7.0.dev1"
```

Add `simready-package>=2026.6.0a1` for packaging, or
`simready-package[publish]>=2026.6.0a1` when WRAPP publishing is required.
Supporting packages such as `usd-validation-nvidia>=1.20.0`,
`usd-core>=23.5`, and `numpy` are resolved transitively.

### Breaking changes

* `simready-foundation-tier-isaac` is no longer published. Its Isaac Sim
  capabilities, features, and profiles are now part of
  `simready-foundation-tier-core`. Run
  `pip uninstall simready-foundation-tier-isaac` before upgrading: leaving both
  in one environment registers the Isaac requirement IDs twice.
* Foundation runtime tests now ship inside `simready-foundation-tier-core`
  rather than as standalone distributions. Uninstall
  `simready-benchmark-kit-suite` and `simready-foundation-runtime-tests-kit`
  before upgrading an existing Benchmark environment; both can own files in the
  same top-level package now bundled by the core tier.

### Added

#### Tiered distribution
* Tier packaging: the specification ships as `simready-foundation-tier-core`,
  a Python package owning the Core, Hierarchy, Visualization, Physics Bodies,
  Isaac Sim, Non-Visual Sensors, Semantic Labels, Dataset Taxonomies, and
  Packaging capabilities along with their profiles.
* Tier discovery through the `usd_validation_nvidia` and `simready.tier` entry
  points, so `simready-validate` loads content from installed wheels. The
  `--rules-path`, `--features-path`, and `--profiles-path` flags are no longer
  needed once a tier is installed.
* Benchmark runtime tests bundled with their owning tier and advertised through
  `runtime_tests_path` on the tier descriptor, so tests and specification
  catalogs cannot drift. Validator-only installs stay lightweight; the
  `[benchmark]` extra installs the Benchmark engine dependencies.
* Guide: SimReady Foundation Tiers (`guides/tiers.md`), plus tier ownership
  surfaced across the capability, feature, and profile documentation.

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

#### Semantic labels and dataset taxonomies
* Semantic Labels capability (`SL.001`–`SL.003`, `MAT.001`, `TIME.001`) in the
  core tier, covering label schema, material labels, and time-sampled labels.
* Dataset Taxonomies capability with validators for the ADE20K, Cityscapes,
  COCO, SUN RGB-D, and Pascal VOC taxonomies (`ADE.001`, `CITY.001`,
  `COCO.001`, `SUN.001`, `VOC.001`).
* Sample assets updated to comply with the Semantic Labels specification.

#### Robotics
* `FET_025_ROS` (ROS-Ready): Isaac ROS bridge-node presence for robot assets,
  offered as an optional feature on `Robot-Body@2.2.0`.
* Standalone Isaac asset transformer, plus Isaac composition features.
* Complete FET022 driven-joint runtime testing on Newton.
* Restored the `FET_028` gripper stack that was dropped during the
  foundations 1.1 sync.

#### Metadata
* `SR.003` nested provenance metadata extended with `asset_license`, `qcode`
  (Wikidata Q-Code), `rigid_body_count`, `asset_extents` (float3 meters, XYZ),
  and `mass` (kilograms), delivered as `FET_033_STANDARD@0.3.0` and bundled
  into the robot and prop profiles.

### Changed
* Prop physics authoring guides document optional runtime variant scaffolding
  and per-solver payload expectations.
* Neutral base authoring guidance tightened so solver-only values (for example
  PhysX SDF approximation) stay inside runtime payloads.
* Recombined the separate validation tiers into the single core tier.
* Prop profiles updated to reference the new feature set.
* Benchmark reference documentation aligned with the registered runtime tests.
* Fixed KitMaker publishing and added the tier-core project ID.

### Deprecated
NONE

### Removed
* `simready-foundation-tier-isaac`, superseded by `simready-foundation-tier-core`.
* The standalone `simready-benchmark-kit-suite` and
  `simready-foundation-runtime-tests-kit` distributions, replaced by the
  runtime tests bundled with the core tier.

### Fixed
* `NP.008` false positives on UDIM texture paths, and UDIM path handling in the
  core validators (OMPE-104937).
* Driven-joint validators for prismatic PhysX mimic couplings.
* `RB.011` tier validation logic.
* Registered the `dataset_taxonomies` validators in the core tier.
* Docs build now completes with all Sphinx warnings cleared.
* Sample-content validation isolated into two branch passes and now fails on
  logged errors (OMPE-103628).
* GitLab security builds and CI jobs.

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
* Published `simready-benchmark` library documentation.
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
