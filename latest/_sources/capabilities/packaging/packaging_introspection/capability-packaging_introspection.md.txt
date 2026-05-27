# Packaging Introspection

**Capability:** Packaging Introspection (PKG.BOM)

```{include} /capabilities/_includes/badges/bill_of_materials.md
```

## Overview

This capability defines the requirements for the Bill of Materials (BOM) — a metadata file (`com.nvidia.simready.packaging.bom.json`) that provides a content-level manifest enabling per-file retrieval and selective delivery. The BOM lists every content file in a package with its logical path, size, and optional content hash. It follows the standard metadata conventions (PKG.META.001) and is discovered through the standard metadata discovery mechanisms.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
