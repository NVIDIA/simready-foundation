# Packaging Core

**Capability:** Packaging Core (PKG)

```{include} /capabilities/_includes/badges/package_structure.md
```

## Overview

This capability defines the requirements for a structurally valid, self-contained SimReady asset package. It covers the package definition file (identity, required fields, directory layout, metadata entries), the metadata file framework, and the shared hash object format.

A conforming package MUST have exactly one package definition (`com.nvidia.simready.packaging.json`) at the package root, with metadata stored in a `.metadata/` folder. Internal references within USD content follow [AA.001 (anchored asset paths)](/capabilities/core/atomic_asset/requirements/anchored-asset-paths); external references must be content-addressable. All hash fields use a common object format with BLAKE3 as the authoritative algorithm.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
