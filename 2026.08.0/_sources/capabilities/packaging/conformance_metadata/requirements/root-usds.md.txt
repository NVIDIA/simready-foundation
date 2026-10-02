# OpenUSD Root Layers

| Code     | PKG.CONF.002 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`recommended` |

## Summary

Packages MAY include an OpenUSD root layers metadata file declaring the top-level USD entry points that should be validated as self-contained assets

## Description

### Purpose

Packages MAY include a root layers metadata file that declares the top-level USD entry points — the USD files that should be opened and validated as self-contained assets. This is distinct from the BOM (PKG.BOM.001), which lists *every* content file in the package (meshes, textures, materials, etc.). A package may contain many USD files (sub-layers, references, payloads), but only a subset are intended as independent entry points for validation and consumption.

### File Name and Schema

The root layers metadata file MUST be named `com.nvidia.simready.root_usds.json` and placed in `.metadata/`. It follows the standard metadata conventions defined by PKG.META.001 (JSON with UTF-8 encoding, reverse domain naming, `format_version`, write-once semantics).

The file MUST conform to the following structure:
- `format_version` (string, MUST) — version of the OpenUSD root layers metadata format
- `description` (string, SHOULD) — human-readable description
- `entries` (array of strings, MUST) — forward-slash relative paths from the package root to each top-level USD file; each path MUST be unique within the array

### Registration Tier

The root layers metadata file MAY be registered-immutable (listed in the package definition's `metadata` array, covered by the package hash) or post-creation (added to `.metadata/` after package creation). Registered-immutable is the expected default when the publisher knows the entry points at creation time.

### Asset Discovery

Validators use the root layers metadata file, when present, to determine which assets to validate. When the file is absent, validators SHOULD fall back to discovering all `.usd`, `.usda`, and `.usdc` files in the package. When the file is present, validators MUST use only the listed entries — no filesystem scanning.

### Reachability Contract

When the root layers metadata file is present, **every other content file in the package MUST be reachable from at least one of the listed root USDs**. "Reachable" includes:

- USD layers brought in via sub-layers, references, payloads, variant selections, or any other composition arc rooted at one of the listed entries
- Asset paths consumed by those USD layers — textures, MDL/MaterialX shaders, audio, point caches, etc.

Files that are not listed in `entries` and not reachable from any listed root are out of scope for content validation: validators are not required to open them, hash them as content, or report on them. The only exception is package-level metadata (the package definition, the BOM, the conformance metadata files in `.metadata/`), which is always validated through its dedicated rules regardless of root USD reachability.

This contract lets validators skip scanning the package's content tree and dispatch validation exclusively through the declared roots, avoiding duplicate work and ambiguous "what is the parent of this file?" semantics for files reachable from multiple roots.

## Why is it required?

- Without an explicit declaration, validators must either be told by the user which USD files to check (error-prone, non-reproducible) or scan the filesystem using conventions (fragile, implicit)
- Conformance metadata is write-once, so if the wrong set of assets is validated the result is permanently incomplete
- The BOM lists every file in the package but does not distinguish top-level entry points from referenced sub-files

## Examples

```json
// Valid: OpenUSD root layers metadata declaring two top-level entry points
// File: .metadata/com.nvidia.simready.root_usds.json
{
  "format_version": "1.0",
  "entries": [
    "simready_usd/sm_apple_a01_01.usd",
    "simready_physx_usd/sm_apple_a01_01.usd"
  ]
}
```

```json
// Invalid: duplicate entries
// File: .metadata/com.nvidia.simready.root_usds.json
{
  "format_version": "1.0",
  "entries": [
    "simready_usd/sm_apple_a01_01.usd",
    "simready_usd/sm_apple_a01_01.usd"
  ]
}
```

```json
// Invalid: missing required entries array
// File: .metadata/com.nvidia.simready.root_usds.json
{
  "format_version": "1.0"
}
```

## How to comply

- Include an OpenUSD root layers metadata file (`com.nvidia.simready.root_usds.json`) to declare the top-level USD entry points in the package
- List it in the package definition's `metadata` array if set at package creation time
- Each entry in `entries` MUST be a unique forward-slash relative path from the package root to a top-level USD file
- Ensure every non-metadata content file in the package is reachable from at least one of the listed root USDs (transitively, through composition or asset path references); files that aren't reachable should either be added as additional `entries`, removed from the package, or refactored so they are referenced from a listed root
- Follow PKG.META.001 conventions: JSON with UTF-8 encoding, include `format_version`

## Related Requirements

- [conformance-metadata](/capabilities/packaging/conformance_metadata/requirements/conformance-metadata)
- [metadata-files](/capabilities/packaging/packaging_core/requirements/metadata-files)
- [bom-structure](/capabilities/packaging/packaging_introspection/requirements/bom-structure)
