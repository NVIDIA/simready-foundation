# Conformance Metadata

**Capability:** Conformance Metadata (PKG.CONF)

```{include} /capabilities/_includes/badges/conformance_metadata.md
```

## Overview

This capability defines the requirements for SimReady Foundations conformance metadata — metadata files that record both declared profile conformance and validation evidence. Packages MAY include one or more conformance files, serving two roles:

- **Declaration**: Conformance files listed in the package definition's `metadata` array represent the publisher's declared profile conformance. These are set at creation time and covered by the package hash.
- **Evidence**: Conformance files added after package creation record independent or third-party validation results. These are not covered by the package hash but are preserved by tools during copying and mirroring.

Conformance metadata makes a package's validation status portable and durable — moving a package between registries or storage locations does not lose proof of compliance.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
