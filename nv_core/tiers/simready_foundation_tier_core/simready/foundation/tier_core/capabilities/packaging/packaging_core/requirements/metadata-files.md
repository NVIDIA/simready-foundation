# Metadata Files

| Code     | PKG.META.001 |
|----------|-----------|
| Validator| _Not yet implemented_ |
| Compatibility | {compatibility}`core-packaging` |
| Tags     | {tag}`essential` |

## Summary

Metadata files MUST be JSON with UTF-8 encoding, use reverse domain naming, and follow write-once semantics

## Description

### Format

All metadata files MUST be JSON documents with UTF-8 encoding. Each file MUST include `format_version` ("major.minor" format, following the same versioning convention as the package definition). Each file SHOULD include `description` (human-readable description to support discovery). Metadata files SHOULD include descriptive information (e.g., tags, categories, physical properties) that enables AI agents to select appropriate assets. Additional fields MAY be present; implementations MUST ignore unknown fields during processing and MUST preserve them when reading and writing, ensuring that tools which do not understand a field do not remove it during transport, mirroring, or re-publication.

### Naming

Each metadata file name MUST use reverse domain notation (e.g., `com.nvidia.simready.conformance.json`). The `name` field in a metadata entry (in the package definition) MUST match the file name of the metadata file.

### Write-Once Semantics

Metadata files MUST NOT be modified or deleted once written. New metadata files MAY be added to a package after creation. Tools that copy or mirror a package MUST include all files in `.metadata/`, regardless of whether they are listed in the package definition's `metadata` array. Removing any metadata file requires publishing under a new `package_id`.

### Metadata Registration Tiers

Metadata files fall into one of three registration tiers based on their relationship with the package definition's `metadata` array:

- **Registered-immutable**: Listed in the `metadata` array at package creation time. These files are included in the package hash computation and MUST NOT change after package creation. Features that define registered-immutable metadata MUST specify that the file be listed in the `metadata` array when present. Example: `com.nvidia.simready.packaging.bom.json` (PKG.BOM.001).
- **Post-creation**: Added to the `.metadata/` folder after package creation. These are NOT listed in the `metadata` array and are NOT covered by the package hash. Tools MUST still preserve these files when copying or mirroring. Example: `com.nvidia.simready.conformance.Prop-Robotics-Physx@1.0.0.json` (PKG.CONF.001) when added post-publish.
- **Either**: Some metadata files MAY be registered-immutable (added at creation) or post-creation (added later), depending on the use case. Example: conformance metadata can be pre-publish (in the `metadata` array, as publisher-declared conformance) or post-publish (added later as independent validation evidence).

## Why is it required?

- A uniform format and naming convention lets any tool discover and parse package metadata without prior agreement between publisher and consumer
- Write-once semantics ensure that metadata added after publishing (e.g., third-party validation results) coexists safely with the publisher's original metadata

## Examples

```json
// Valid: metadata file with required format_version and reverse domain name
// File: .metadata/com.acme.physics.json
{
  "format_version": "1.0",
  "description": "Physical properties for simulation",
  "mass_kg": 12.5,
  "friction_coefficient": 0.6
}
```

```json
// Invalid: metadata file missing format_version
// File: .metadata/com.acme.physics.json
{
  "mass_kg": 12.5
}
```

```json
// Invalid: metadata file with non-reverse-domain name
// File: .metadata/physics.json
{
  "format_version": "1.0"
}
```

## How to comply

- Use JSON with UTF-8 encoding; always include `format_version` (major.minor)
- Name metadata files using reverse domain notation
- Never modify or delete existing metadata files; new files may be added after creation
- Include all `.metadata/` files when copying or mirroring packages
- Preserve unknown fields when reading and writing (round-trip safety)

## Related Requirements

- [package-definition](/capabilities/packaging/packaging_core/requirements/package-definition)
- [hash-object-format](/capabilities/packaging/packaging_core/requirements/hash-object-format)
