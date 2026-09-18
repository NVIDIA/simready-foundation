# SimReady Foundation - Content Guidelines and Requirements

## Overview

This documentation is a collection of guidelines and requirements for OpenUSD content. It provides a framework to author OpenUSD content that is suitable for use cases such as rendering, simulation, robotics, and AI training. 

```{important}
These are the SimReady Foundation 7.1 docs. Foundation releases use a
`major.minor` product version, and major or minor releases are not
backward-compatible with older Foundation releases. Keep the documentation,
tier content, and supporting tool versions aligned with Foundation 7.1. Assets,
custom tiers, and validation stamps from 7.0 or earlier must be migrated as
needed and validated again before being treated as 7.1-conformant. See the
[7.1 release notes](changelist.md#release-notes) for details and the
[Foundation 7.1 library set](guides/foundation_pypi.md#foundation-71-library-set)
for compatible validation, Benchmark, and packaging versions.
```

## Key Concepts


### Requirements

Requirements are the core building blocks of this documentation. They are specific, testable rules that assets should follow, such as "upAxis shall be Z" or "meshes shall have normals". Each requirement is assigned a unique ID (for example: VG.027, UN.006, HI.001).

### Capabilities

Capabilities are categories that organize related requirements. Examples include Visualization/Geometry, Core/Units, and Hierarchy. This modular design allows you to implement only the capabilities needed for your particular use case.

### Features

Features are collections of requirements tailored for specific use cases or software features. For example, the "Minimal Placeable Visual" feature references all requirements needed for an asset to be visualized and placed in a scene.

### Profiles

Profiles are predefined bundles of features designed for common scenarios. Examples include the Prop Robotics Neutral profile. Profiles make it easy to test and validate complete asset workflows.

### Tiers

Tiers are the slices the specification is distributed in. Each tier owns a set of capabilities, features, and profiles, and ships as its own installable package. A tier records who defines that part of the specification and how broadly it has been adopted, which lets runtime- or vendor-specific content be formally specified and validated without changing the shared core. See [Tiers](guides/tiers).



## Getting Started

- **New to SimReady?** Start with the [Getting Started](guides/getting_started) guide for an introduction and decision tree.
- **Creating Assets?** Refer to the [Guides](guides/guides) to learn how to implement capabilities in your assets.
- **Wondering which tier a profile comes from?** Read [Tiers](guides/tiers) for how the specification is divided, owned, and distributed.
- **Looking for specific requirements?** Browse the [Capabilities](capabilities/capabilities) section for detailed technical specifications.
- **Tracking feature progress?** See the [Features Status Dashboard](features/features) for an at-a-glance view of all features, their readiness, versions, and profile membership.
- **Implementing specific features?** Check out the [Features](features/features) section for detailed feature implementations and requirements.
- **Building for a specific use case?** Check out the [Profiles](profiles/profiles) section to find predefined capability sets.
- **Comparing profiles?** See the {ref}`Profile Comparison <profile-comparison>` table for feature-level differences.
- **Need to reference something?** Use the [Indexes](indexes/indexes) for quick access to all documentation content.


```{toctree}
:maxdepth: 2
:hidden:

Release notes <changelist>
Guides <guides/guides>
Development Workflows <guides/development>
Capabilities <capabilities/capabilities>
Features <features/features>
Profiles <profiles/profiles>
Indexes <indexes/indexes>

```
