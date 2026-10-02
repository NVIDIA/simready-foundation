# Release notes

Release history for the SimReady Foundation. Public releases use a
`major.minor` product version. Repository branches and Python distributions
prefix that version with the release year, so Foundation 8.0 is published as
`2026.08.0` from the `release-2026.08.0` branch. This release version is
separate from the semantic versions assigned to individual features and
profiles. The current repository version is recorded in `VERSION.md`.

Foundation 8.0 requires the 8.0 releases of the SimReady libraries
(`simready-validate`, `simready-benchmark`, `simready-package`, etc.).
Foundation 8.0 does not work with older library releases.

The 8.0 SimReady libraries (`simready-validate`, `simready-benchmark`,
`simready-package`, etc.) are backward-compatible with earlier Foundation
releases, including 6.0 and 7.1.

Use documentation, tier content, and profile versions for the Foundation
release you are targeting. When adopting a newer Foundation profile, migrate
assets and custom tiers as needed and validate them against that profile;
earlier validation results or stamps do not establish conformance to it.

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

## 2026.08.0 — September 2026

Visual materials, sensors, and AI Factory release. Foundation 8.0 adds the
OpenPBR and display color material contracts, a Sensors tier covering IMU,
joint, camera, and LiDAR sensors, and an AIF tier for AI Factory data center
equipment. Asset provenance moves from nested USD metadata to a USD and
sidecar union, and the legacy split prop and robot profiles are consolidated
into `Robotics-Prop`, `Robot-Body`, and `Robot-Gripper`.

```{important}
Foundation 8.0 requires the 8.0 releases of the SimReady libraries
(`simready-validate`, `simready-benchmark`, `simready-package`, etc.).
Foundation 8.0 does not work with older library releases.

The 8.0 SimReady libraries (`simready-validate`, `simready-benchmark`,
`simready-package`, etc.) are backward-compatible with earlier Foundation
releases, including 6.0 and 7.1.
```

### Foundation 8.0 libraries

Foundation 8.0 ships as three tier packages, used together with the
corresponding 8.0 SimReady tools:

| Library | Purpose |
|---|---|
| `simready-foundation-tier-core` | The baseline requirements, features, profiles, validators, and bundled runtime tests. Required. |
| `simready-foundation-tier-sensors` | Physics sensor, RTX LiDAR, and camera render-product contracts. Add it for sensor-bearing assets. |
| `simready-foundation-tier-aif` | AI Factory equipment contracts. Add it for CDU, CRAH, UPS, and compute-rack assets. |
| `simready-validate` | Static validation CLI and Python API. |
| `simready-benchmark` | Runtime and behavioral testing in Kit or Isaac Sim. Arrives through a tier's `benchmark` extra; you do not normally install it directly. |
| `simready-package` | Package creation and pre/post validation. Use the `publish` extra for WRAPP publishing. |

The tier wheels for a given Foundation release share one version line, so
install the tiers you need in a single command and let pip resolve a matching
set rather than pinning them separately:

```bash
pip install "simready-foundation-tier-core[benchmark]" simready-validate
```

Add `simready-foundation-tier-sensors` or `simready-foundation-tier-aif` to
that same command when the asset needs them. Supporting packages such as
`usd-validation-nvidia`, `MaterialX`, `pillow`, `usd-core`, and `numpy` are
resolved transitively.

The published version of each package is listed on its PyPI project page. Pin
exact versions there if your environment requires reproducible installs, and
keep the three tier wheels on the same version when you do.

### Breaking changes

* The split prop and robot profiles are removed in favor of the consolidated
  profiles. Re-stamp affected assets and validate again; a stamp naming a
  removed profile no longer resolves. The runtime-specific behavior these
  profiles carried is now selected through optional PhysX, Newton, MuJoCo, and
  Isaac feature bundles on the consolidated profile versions, rather than by
  choosing a separate profile.
* A UsdPreviewSurface material is now mandatory on the 8.0 profile versions.
  `FET_006_STANDARD` was optional through `Robotics-Prop@3.3.0`; at
  `Robotics-Prop@4.0.0`, `Robot-Body@3.0.0`, and `Robot-Gripper@3.0.0` it is
  required, at version `0.2.0`. An asset that passes the previous profile
  version without a UsdPreviewSurface material will fail the 8.0 version.
  Author one, or pin the earlier profile version. OpenPBR, MDL, and display
  color remain optional alongside it.
* `FET_000_STANDARD@0.2.0` drops `NP.006` (conformance metadata location) and
  `SR.001` (SimReady metadata whitelist) from the Core feature. Both moved to
  the packaging and metadata features. Custom-tier owners who relied on Core to
  supply them must add `FET_031_STANDARD` and `FET_033_STANDARD` to the
  affected profile versions in their profile TOML. Asset authors are not
  affected as long as they use an 8.0 profile version, which pins both.

Profile migration map:

| Removed profile | Use instead |
|---|---|
| `Prop-Robotics-Neutral`, `Prop-Robotics-Physx`, `Prop-Robotics-Isaac` | `Robotics-Prop` |
| `Robot-Body-Neutral`, `Robot-Body-Isaac`, `Robot-Body-Runnable` | `Robot-Body` |

### Added

#### Tier distribution
* `simready-foundation-tier-sensors`, a Sensors tier owning the physics
  sensor, RTX LiDAR, and render-product capabilities, their four profiles,
  validators, and bundled runtime tests.
* `simready-foundation-tier-aif`, an AI Factory tier owning equipment class
  metadata, connection points, thermal cooling, and electrical contracts for
  CDU, CRAH, UPS, and compute-rack assets.
* Shared tier documentation covering the Core, AIF, and Sensors tiers
  (`shared/tiers/`).

#### Visual materials
* `FET_006_OPENPBR@0.1.0`: the OpenPBR material contract, with the final
  surface authored as an OpenPBR shading network on `outputs:mtlx:surface`
  (`VM.PBR.001`–`VM.PBR.003`, `VM.TEX.004`). OpenPBR is the recommended target
  for new SimReady assets; MDL remains permitted for existing content.
  `VM.PBR.001` is phased-permissive, so an MDL surface still passes during
  migration.
* `FET_006_STANDARD@0.2.0` and `FET_006_MDL@0.2.0`: expanded UsdPreviewSurface
  and MDL contracts covering bind scope, final-surface presence, PBR parameter
  ranges, and per-family texture color space.
* `FET_010_STANDARD@0.1.0`: display color on renderable geometry
  (`DISP.001`–`DISP.003`), with a new Display Color capability and validator.
* Guide: Visual Materials (`guides/visual_materials/visual_materials.md`),
  covering OpenPBR and display color authoring, validation, and rendering.

#### Sensors
* `FET_034_ISAAC@0.1.0` (IMU sensor rigid-body attachment, `PS.001`) and
  `FET_037_ISAAC@0.1.0` (joint sensor on the articulation root, `PS.002`).
* `FET_035_RTX@0.1.0`: camera render products and AOVs (`RP.001`–`RP.006`),
  including codec validation and BLOSC compression for semantic AOVs.
* `FET_036_RTX@0.1.0`: RTX LiDAR (`LI.001`–`LI.004`), covering the OmniLidar
  schema, emitter-state array consistency, the scan-rate floor, and
  solid-state ray counts.
* Four sensor profiles at `1.0.0` — `Sensor-IMU`, `Sensor-Joint`,
  `Sensor-Camera`, and `Sensor-LiDAR` — each stamped alongside an asset's
  primary profile, with authoring guides.
* Runtime tests: `imu_sensor_data`, `joint_sensor_data`,
  `render_product_output`, `semantic_aov_output`, and `lidar_point_cloud`.

#### AI Factory equipment
* `FET200_AIF` (equipment metadata, `AM.001`–`AM.007`), `FET201_AIF`
  (connection points), `FET202_AIF` (thermal cooling), and `FET203_AIF`
  (electrical), with `FET201`–`FET203` at both `0.1.0` and `0.2.0`.
* `AIF-Entity` profile at `0.1.0` and `0.2.0`. A single profile covers all
  equipment classes; `aif:core:assetClass` selects the class-specific checks.
* Reference assets for four equipment classes under `sample_content/aif/`.

#### Metadata and packaging
* `SR.004`: provenance read from the union of root-layer `customLayerData` and
  an optional same-directory `<usd_stem>.json` sidecar, delivered as
  `FET_033_STANDARD@0.4.0`. A field must not be authored in both locations.
* `Package-Candidate@1.3.0` adopts `FET_033_STANDARD@0.4.0`.

#### Profiles
* 8.0 releases of the consolidated profiles: `Robotics-Prop@4.0.0`,
  `Robot-Body@3.0.0`, and `Robot-Gripper@3.0.0`, each requiring
  `FET_006_STANDARD@0.2.0` with optional OpenPBR, MDL, and display color.
* Intermediate versions `Robotics-Prop@3.3.0`, `Robot-Body@2.3.0`, and
  `Robot-Gripper@2.2.0` adopt `FET_033_STANDARD@0.4.0`.
* `Robot-Body@2.3.0` and `@3.0.0` offer the full optional runtime menu for all
  three solvers — core scaffolding, rigid body, multibody, driven joints, and
  articulation for PhysX, Newton, and MuJoCo — rather than PhysX alone.

#### Conformance skills
* `simready-foundation-conform-fet-006-openpbr` and
  `simready-foundation-conform-fet-010-standard`.

### Changed
* The reference prop library is re-authored to payload-based composition, with
  per-solver instance layers and refreshed light, dark, and transparent
  thumbnails.
* Geometry and units validators delegate to `usd-validation-nvidia` rather
  than duplicating the checks locally. The affected requirements are now
  referenced through their `com.nvidia.usd.*` names.
* The monolithic texture color-space requirement is replaced by per-family
  requirements for UsdPreviewSurface, OpenPBR, and MDL
  (`VM.TEX.003`–`VM.TEX.005`).
* Built-in Kit MDL modules such as OmniPBR are exempt from the rule requiring
  MDL sources to be packaged with the asset, matching Isaac asset transformer
  behavior.

### Deprecated
NONE

### Removed
* The six split prop and robot profiles listed under Breaking changes.
* The `atomic_asset` executable validator. Its requirements are now checked by
  `usd-validation-nvidia`; the capability documentation remains.
* Per-asset `metadata.json` sidecars and `web/*.glb` exports from the migrated
  reference props, replaced by the USD-native provenance and thumbnail layout.

### Fixed
* Physics drop placement is size-safe for the `FET_003` ground and slope drop
  runtime tests.
* Cross-engine runtime-test reliability for gripper, articulation, and
  placement tests.
* Stale Isaac references removed from the sample manifest.
* Material and thumbnail fixes for the lamp and workbench tool props.
* The sensor runtime tests ship with the Sensors tier (OMPE-112896), and their
  execution was corrected (OMPE-113171, OMPE-113178, OMPE-113181).
* `FET_005` grasp setup now resolves rigid bodies outside identifier scopes,
  and Newton failure reporting is corrected.
* Generated artifacts and unreferenced DCC source assets are excluded from the
  released package.

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
