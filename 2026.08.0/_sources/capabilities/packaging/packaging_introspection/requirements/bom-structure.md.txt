# BOM Structure

| Code     | PKG.BOM.001 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`essential` |

## Summary

The BOM is a metadata file identified by the name `com.nvidia.simready.packaging.bom.json`. It MUST list all content files in the package with per-item fields, using forward-slash relative paths with no duplicates.

## Description

### Metadata File

The BOM is a metadata file identified by the name `com.nvidia.simready.packaging.bom.json`. It follows the standard metadata conventions defined by PKG.META.001 (JSON with UTF-8 encoding, reverse domain naming, `format_version`, write-once semantics) and is discovered through the standard metadata discovery mechanisms defined by PKG.DEF.001.

### Completeness

The BOM MUST list all content files contained in the package. Content files are all files that are not the package definition file and not metadata files. Folders are implicit and derived from file paths; empty folders cannot be represented (use a placeholder file like `.keep` if needed).

### BOM-Level Fields

The BOM consists of: `format_version` (string, MUST — per PKG.META.001), `items` (array, MUST).

### Item-Level Fields

Each BOM item includes: `relative_path` (string, MUST), `size` (integer, MUST), `hash` (object, SHOULD — required for integrity verification, see PKG.HASH.001).

### Path Format

Relative paths MUST use forward slashes (`/`) as path separators regardless of the underlying storage system. This applies to the `relative_path` field.

### Uniqueness

Each `relative_path` in the BOM MUST be unique within the package. No two BOM items may have the same `relative_path` value.

### Content Hash Authority

When a BOM is present, its `items` array defines the authoritative set of content files for `content_hash` computation (see PKG.HASH.001). Step 1 of the content hash algorithm uses the BOM items instead of enumerating the filesystem, and step 2 uses the `sha256` value from each item's `hash` object instead of computing it from file bytes. The remaining steps (sort, concatenate, hash) are unchanged.

## Why is it required?

- A complete content file manifest enables per-file delivery — consumers can fetch only the files they need instead of downloading the entire package
- A canonical path format prevents platform-specific ambiguity when the same package is consumed on different operating systems

## Examples

```json
// Valid: BOM with two items including hash objects
{
  "format_version": "1.0",
  "items": [
    {
      "relative_path": "meshes/oak_tree.usd",
      "size": 245760,
      "hash": { "sha256": "a1b2c3d4..." }
    },
    {
      "relative_path": "textures/bark_diffuse.png",
      "size": 1048576,
      "hash": {
        "sha256": "e5f60718...",
        "sha256-first1m": "ff00ff00..."
      }
    }
  ]
}
```

```json
// Invalid: duplicate relative_path
{
  "format_version": "1.0",
  "items": [
    { "relative_path": "meshes/tree.usd", "size": 100 },
    { "relative_path": "meshes/tree.usd", "size": 200 }
  ]
}
```

```json
// Invalid: backslash path separator
{
  "format_version": "1.0",
  "items": [
    { "relative_path": "meshes\\tree.usd", "size": 100 }
  ]
}
```

## How to comply

- Create the BOM as a metadata file named `com.nvidia.simready.packaging.bom.json`, following PKG.META.001 conventions
- Include `format_version` as a required field
- Include every content file in the package in the BOM `items` array (exclude the package definition file and metadata files)
- Include `relative_path` and `size` for each item; include `hash` for integrity verification
- Use forward slashes exclusively in all path values
- Ensure each `relative_path` appears exactly once

## Related Requirements

- [metadata-files](/capabilities/packaging/packaging_core/requirements/metadata-files)
- [hash-object-format](/capabilities/packaging/packaging_core/requirements/hash-object-format)
