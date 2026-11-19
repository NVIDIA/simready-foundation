# SimReady Foundation - Content Guidelines and Requirements

## Overview

This documentation is a collection of guidelines and requirements for OpenUSD content. It provides a framework to author OpenUSD content that is suitable for use cases such as rendering, simulation, robotics, and AI training. 

## Key Concepts


### Requirements

Requirements are the core building blocks of this documentation. They are specific, testable rules that assets should follow, such as "upAxis shall be Z" or "meshes shall have normals". Each requirement is assigned a unique ID (for example: VG.027, UN.006, HI.001).

### Capabilities

Capabilities are `CAP`-prefixed static contracts that organize related requirements. Examples include Visualization/Geometry, Core/Units, and Hierarchy. This modular design allows profiles to select only the static contracts needed for a use case.

### Features

Features are runtime behavior families with dotted `<name>[.<runtime>].<version>` IDs. Runtime variants carry tests, runtime-specific requirements, and adapters; a testless source remains a FET when tested variants derive from it. Other requirement-only contracts are capabilities.

### Profiles

Profiles are named, versioned selectors over features and capabilities, each required or optional. The Core tier ships 16 profiles. They cover robotics props, robot bodies and grippers, assemblies, reconstruction, materials, packaging, and label taxonomies. The same asset may be validated independently against several profiles.

### Tiers

Tiers are the slices the specification is distributed in. Each tier owns a set of capabilities, features, and profiles, and ships as its own installable package. A tier records who defines that part of the specification and how broadly it has been adopted, which lets runtime- or vendor-specific content be formally specified and validated without changing the shared core. See [Tiers](guides/tiers.md).



## Getting Started

- **New to SimReady?** Start with the [Getting Started](guides/getting_started.md) guide for an introduction and decision tree.
- **Creating Assets?** Refer to the [Guides](guides/guides.md) to learn how to implement capabilities in your assets.
- **Wondering which tier a profile comes from?** Read [Tiers](guides/tiers.md) for how the specification is divided, owned, and distributed.
- **Looking for specific requirements?** Browse the [Rules and Requirements](shared/rules_and_reqs/rules_and_reqs.md) section for detailed technical specifications.
- **Tracking feature progress?** See the [Features Status Dashboard](shared/features/features.md) for an at-a-glance view of all features, their readiness, versions, and profile membership.
- **Implementing specific features?** Check out the [Features](shared/features/features.md) section for detailed feature implementations and requirements.
- **Building for a specific use case?** Check out the [Profiles](shared/profiles/profiles.md) section to find predefined capability sets.
- **Looking for installable specification catalogs?** Browse [Tiers](shared/tiers/tiers.md) to see which profiles and features each tier owns.
- **Comparing profiles?** See the {ref}`Profile Comparison <profile-comparison>` table for feature-level differences.
- **Need to reference something?** Use the [Indexes](indexes/indexes.md) for quick access to all documentation content.


```{toctree}
:maxdepth: 2
:hidden:

Guides <guides/guides>
Development Workflows <guides/development>
Rules and Requirements <rules_and_reqs/rules_and_reqs>
Capabilities <capabilities/capabilities>
Features <features/features>
Profiles <profiles/profiles>
Tiers <tiers/tiers>
Indexes <indexes/indexes>
Changelist <changelist>

```
