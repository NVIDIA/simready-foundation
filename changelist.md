# Changelist

Release history for the SimReady Foundation. Versions use the
`YYYY.MM.patch` scheme and correspond to the `release-<version>` branches.
The current version is recorded in `VERSION.md`.

Entries are newest first.

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
