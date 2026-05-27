# Conformance Metadata

| Code     | PKG.CONF.001 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`recommended` |

## Summary

Packages MAY include conformance metadata files recording SimReady Foundations validation results, following defined naming and JSON schema conventions

## Description

### Purpose

Packages MAY include one or more conformance metadata files recording the results of SimReady Foundations validation. Conformance files serve two roles depending on how they are registered:

- **Declaration (registered-immutable)**: Conformance files listed in the package definition's `metadata` array are set at package creation time, covered by the package hash, and represent the publisher's declared profile conformance. The packaging tool is responsible for validating before including these files.
- **Evidence (post-creation)**: Conformance files added to `.metadata/` after package creation are NOT listed in the `metadata` array and are NOT covered by the package hash. These allow independent or third-party validation to be recorded without modifying the package identity.

Multiple conformance files allow declaration and post-creation evidence to coexist. For example, a publisher may validate core features before publishing (declaration, included in the package hash), and a third party may validate against an additional profile afterward (evidence, added as post-creation metadata).

### File Naming

Conformance files MUST be named `com.nvidia.simready.conformance.{profile}@{profile_version}.json`. Any literal `@` or `%` in the profile name or version MUST be percent-encoded (`%40`, `%25`). Each conformance file records validation results for exactly one profile and version.

Examples:
- `com.nvidia.simready.conformance.Prop-Robotics-Physx@1.0.0.json`
- `com.nvidia.simready.conformance.Package@1.0.0.json`
- `com.nvidia.simready.conformance.Prop-Robotics-Neutral@1.0.0.json`

### Consistency

The `profile` and `profile_version` fields inside the conformance file MUST match the profile name and version encoded in the filename (after percent-decoding).

### JSON Schema

Each conformance metadata file MUST conform to the following structure:
- `format_version` (string, MUST) — version of the conformance metadata format
- `profile` (string, MUST) — profile name the package was validated against
- `profile_version` (string, MUST) — version of the profile used for validation
- `timestamp` (string, MUST) — ISO 8601 datetime of the validation run
- `assets` (array, MUST) — one entry per validated asset in the package
- `assets[].asset` (string, MUST) — forward-slash relative path from the package root to the validated file (e.g. `simready_usd/sm_apple_a01_01.usd`); for package-level validation use the package definition filename (e.g. `com.nvidia.simready.packaging.json`)
- `assets[].features` (array, MUST) — list of all features tested for this asset
- `assets[].features[].<id>` (object, MUST) — feature ID as key, containing validation details
- `assets[].features[].<id>.version` (string, MUST) — version of the feature that was validated
- `assets[].features[].<id>.passed` (boolean, MUST) — whether the feature passed validation
- `assets[].features[].<id>.failing_requirements` (array of strings, MUST) — requirement IDs that failed; empty when `passed` is `true`
- `assets[].features[].<id>.dependencies` (array, MUST) — feature dependencies evaluated during validation, each entry following the same `{ "<id>": { "version": "<ver>" } }` shape; empty when the feature has no dependencies
- `content_hash` (hash object, MAY) — the content hash of the package contents at the time validation was performed, computed as defined by PKG.HASH.001. When present, consumers can recompute the content hash from the current BOM and compare: a match proves the validation results still apply to the current source files without re-running the validation engine. Omitted when the content hash is not available (e.g. when validating a package that has no BOM)

A package may contain multiple assets validated independently — for example, a `simready_usd` variant validated against one profile and a `simready_physx_usd` variant validated against another. Each asset entry carries its own features array so consumers can determine the full validation outcome per asset from a single file. Both passing and failing features are recorded.

## Why is it required?

- Without a portable record, a package's validation status is lost when it moves between storage systems
- Multiple conformance files allow declaration and post-creation evidence to coexist in the same package
- The `@`-delimited qualifier makes profile identity parseable from the filename without reading the file, enabling efficient discovery

## Examples

```json
// Valid: declaration with multiple assets — registered-immutable conformance (in metadata array)
// File: .metadata/com.nvidia.simready.conformance.Prop-Robotics-Physx@1.0.0.json
{
  "format_version": "1.0",
  "profile": "Prop-Robotics-Physx",
  "profile_version": "1.0.0",
  "timestamp": "2026-03-02T00:00:00",
  "assets": [
    {
      "asset": "simready_physx_usd/sm_apple_a01_01.usd",
      "features": [
        {
          "FET001_BASE_NEUTRAL": {
            "version": "0.1.0",
            "passed": true,
            "failing_requirements": [],
            "dependencies": []
          }
        },
        {
          "FET003_BASE_PHYSX": {
            "version": "0.1.0",
            "passed": false,
            "failing_requirements": ["RB.MB.001"],
            "dependencies": [
              { "FET001_BASE_NEUTRAL": { "version": "0.1.0" } }
            ]
          }
        }
      ]
    }
  ]
}
```

```json
// Valid: declaration — single asset (in metadata array)
// File: .metadata/com.nvidia.simready.conformance.Prop-Robotics-Neutral@1.0.0.json
{
  "format_version": "1.0",
  "profile": "Prop-Robotics-Neutral",
  "profile_version": "1.0.0",
  "timestamp": "2026-03-02T00:00:00",
  "assets": [
    {
      "asset": "simready_usd/sm_apple_a01_01.usd",
      "features": [
        {
          "FET001_BASE_NEUTRAL": {
            "version": "0.1.0",
            "passed": true,
            "failing_requirements": [],
            "dependencies": []
          }
        }
      ]
    }
  ]
}
```

```json
// Valid: evidence — package-level conformance (not in metadata array)
// File: .metadata/com.nvidia.simready.conformance.Package@1.0.0.json
{
  "format_version": "1.0",
  "profile": "Package",
  "profile_version": "1.0.0",
  "timestamp": "2026-03-15T14:30:00",
  "assets": [
    {
      "asset": "com.nvidia.simready.packaging.json",
      "features": [
        {
          "FET030_PACKAGING_CORE": {
            "version": "0.1.0",
            "passed": true,
            "failing_requirements": [],
            "dependencies": []
          }
        }
      ]
    }
  ]
}
```

```json
// Valid: declaration with content_hash — proves results apply to a specific source snapshot
// File: .metadata/com.nvidia.simready.conformance.Package-Candidate@1.0.0.json
{
  "format_version": "1.0",
  "profile": "Package-Candidate",
  "profile_version": "1.0.0",
  "timestamp": "2026-03-01T12:00:00",
  "content_hash": {
    "sha256": "a1b2c3d4e5f6..."
  },
  "assets": [
    {
      "asset": "simready_usd/sm_apple_a01_01.usd",
      "features": [
        {
          "FET035_PACKAGE_CANDIDATE": {
            "version": "0.1.0",
            "passed": true,
            "failing_requirements": [],
            "dependencies": []
          }
        }
      ]
    }
  ]
}
```

```json
// Invalid: missing required profile, timestamp, and assets fields
// File: .metadata/com.nvidia.simready.conformance.Prop-Robotics-Neutral@1.0.0.json
{
  "format_version": "1.0"
}
```

```json
// Invalid: asset entry missing required asset path
// File: .metadata/com.nvidia.simready.conformance.Prop-Robotics-Neutral@1.0.0.json
{
  "format_version": "1.0",
  "profile": "Prop-Robotics-Neutral",
  "profile_version": "1.0.0",
  "timestamp": "2026-03-02T00:00:00",
  "assets": [
    {
      "features": [
        { "FET001_BASE_NEUTRAL": { "version": "0.1.0", "passed": true, "failing_requirements": [], "dependencies": [] } }
      ]
    }
  ]
}
```

## How to comply

- Include conformance metadata files if SimReady Foundations validation has been performed
- Name each file `com.nvidia.simready.conformance.{profile}@{profile_version}.json`; percent-encode any `@` or `%` in the profile name or version
- Ensure the `profile` and `profile_version` fields inside the file match the profile name and version encoded in the filename
- Structure files as JSON with `format_version`, `profile`, `profile_version`, `timestamp`, and `assets` array
- Each entry in `assets` MUST have an `asset` path (relative to the package root) and a `features` array
- Include all tested features per asset, each with `version`, `passed`, `failing_requirements`, and `dependencies`
- For package-level validation, use the package definition filename as the `asset` value (e.g. `com.nvidia.simready.packaging.json`)

## Related Requirements

- [package-definition](/capabilities/packaging/packaging_core/requirements/package-definition)
- [metadata-files](/capabilities/packaging/packaging_core/requirements/metadata-files)
- [root-usds](/capabilities/packaging/conformance_metadata/requirements/root-usds)
