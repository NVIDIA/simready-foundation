# Requirements

## Summary

- Each package **MUST** have exactly one package definition (`com.nvidia.simready.packaging.json`) at the package root, with required fields `format_version`, `package_id`, and `license`
- The `package_id` **MUST** be globally unique, case-insensitive, and immutable after publication
- Internal file references within USD content MUST follow [AA.001 (anchored asset paths)](/capabilities/core/atomic_asset/requirements/anchored-asset-paths); external references MUST be content-addressable
- Metadata files **MUST** be JSON with UTF-8 encoding, use reverse domain naming, and follow write-once semantics
- Hash fields **MUST** use the common hash object format with at least a `sha256` key; implementations **SHOULD** also include `blake3` and/or `blake2b` when available for performance; when present, `content_hash` and `package_hash` **MUST** be computed using the deterministic SHA-256 algorithms defined in the spec

## Requirements

<!-- PKG_STRUCTURE_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- PKG_STRUCTURE_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/package-definition
requirements/metadata-files
requirements/hash-object-format
```
