# Requirements

## Summary

- The BOM is a metadata file identified by the name `com.nvidia.simready.packaging.bom.json`, following standard metadata conventions (PKG.META.001)
- The BOM **MUST** list all content files in the package (excludes the package definition and metadata files) with `relative_path` (forward slashes, unique) and `size`
- Each BOM item **SHOULD** include a `hash` object for integrity verification

## Requirements

<!-- PKG_BOM_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- PKG_BOM_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/bom-structure
```
