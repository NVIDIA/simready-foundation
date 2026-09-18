# Package Definition

| Code     | PKG.DEF.001 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`essential` |

## Summary

Each package MUST have exactly one valid package definition with a globally unique, case-insensitive, immutable identity, placed at the package root alongside a `.metadata/` folder

## Description

### Definition File

Each package MUST have exactly one package definition identified by the canonical name `com.nvidia.simready.packaging.json`. The file MUST be placed at the package root; the package root is the parent directory of this file. Metadata files MUST be stored in the `.metadata/` folder at the package root. Consumers discover metadata files by looking for expected file names in `.metadata/`.

### Required Fields

The package definition MUST include `format_version` (string, "major.minor" format), `package_id` (string), and `license` (string). It SHOULD include `content_hash` (hash object) and `package_hash` (hash object) for integrity verification. It MAY include `description` (string) and `metadata` (array). The `license` field SHOULD use an SPDX license identifier (e.g., `Apache-2.0`, `MIT`, `LicenseRef-Proprietary`). The `description` field SHOULD NOT exceed 500 characters; detailed information SHOULD be provided through metadata files. Additional fields MAY be present; implementations MUST ignore unknown fields during processing and MUST preserve them when reading and writing, ensuring that tools which do not understand a field do not remove it during transport, mirroring, or re-publication.

### Metadata Entries

Each entry in the `metadata` array MUST include `name` (file name identifying the metadata type) and `hash` (content hash object for integrity verification). Each entry MAY include `data` (inline embedded content). The referenced metadata files MUST NOT be modified after package creation, as they are included in the package hash.

### Package Identity

The `package_id` MUST be a non-empty UTF-8 string of at most 255 characters. It MUST NOT contain control characters (U+0000–U+001F, U+007F–U+009F), whitespace, or any of `<>:"/\|?*`. The `package_id` MUST be globally unique across all registries; reverse domain name notation is recommended (e.g., `com.acme.assets.vegetation.20260115`). Package identifiers MUST be treated as case-insensitive: two values differing only in letter case MUST be considered identical. Once published, everything covered by the `package_hash` MUST NOT be modified; new changes require publishing under a new `package_id`.

## Why is it required?

- Every tool that reads a package needs a single, well-known entry point and a predictable directory layout
- A globally unique, immutable identifier ensures that a `package_id` always refers to exactly the same content, regardless of where or when it is consumed

## Examples

```json
// Valid: minimal package definition with required fields
{
  "format_version": "1.0",
  "package_id": "com.acme.assets.vegetation.oak_tree.20260115",
  "license": "Apache-2.0"
}
```

```json
// Valid: package definition with optional fields and declared conformance
{
  "format_version": "1.0",
  "package_id": "com.acme.assets.vegetation.oak_tree.20260115",
  "license": "Apache-2.0",
  "description": "Photorealistic oak tree for outdoor scenes",
  "content_hash": { "sha256": "a1b2c3d4e5f6..." },
  "package_hash": { "sha256": "f6e5d4c3b2a1..." },
  "metadata": [
    {
      "name": "com.nvidia.simready.conformance.Prop-Robotics-Physx@1.0.0.json",
      "hash": { "sha256": "1234abcd..." }
    }
  ]
}
```

```json
// Invalid: missing required fields (no license)
{
  "format_version": "1.0",
  "package_id": "com.acme.assets.vegetation.oak_tree.20260115"
}
```

```json
// Invalid: package_id with forbidden characters
{
  "format_version": "1.0",
  "package_id": "com.acme/assets:oak tree",
  "license": "Apache-2.0"
}
```

## How to comply

- Place `com.nvidia.simready.packaging.json` at the package root with a `.metadata/` folder alongside it
- Include `format_version` (major.minor), `package_id`, and `license` as required fields
- Use an SPDX license identifier; keep `description` under 500 characters
- Preserve unknown fields when reading and writing (round-trip safety)
- Use reverse domain name notation for `package_id`; treat identifiers as case-insensitive
- List immutable metadata files in the `metadata` array with `name` and `hash`
- Never modify published package content; publish changes as a new package

## Related Requirements

- [anchored-asset-paths (AA.001)](/capabilities/core/atomic_asset/requirements/anchored-asset-paths)
- [metadata-files](/capabilities/packaging/packaging_core/requirements/metadata-files)
- [hash-object-format](/capabilities/packaging/packaging_core/requirements/hash-object-format)
- [conformance-metadata](/capabilities/packaging/conformance_metadata/requirements/conformance-metadata)

## For More Information

- [SPDX License List](https://spdx.org/licenses/)
