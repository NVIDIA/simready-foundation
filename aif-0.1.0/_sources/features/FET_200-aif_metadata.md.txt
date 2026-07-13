# AIF Core Metadata

**Feature ID:** FET200_AIF_NEUTRAL

> **Reclassified as a Capability.** AIF Core Metadata is a Capability, not a Feature
> -- its rules validate attribute presence but do not change simulation output.
> Authoritative documentation now lives in the
> [Core Metadata capability](../capabilities/aif/metadata/capability-metadata).
> This entry is retained as an **interim feature carrier**: its rules stay in the
> `FET_200` feature JSON so validation passes until SRF supports
> Profile-to-Capability referencing.

Requires all AIF equipment metadata: identity, dimensions, SimReady version, description, and equipment-class-specific `aif:spec:*` attributes.

## Requirements

- AM.001: properties sublayer present
- AM.002: `aif:core:assetClass` present
- AM.003: manufacturer, modelNumber, assetVersion present
- AM.004: physical dimension attributes present
- AM.005: `aif:core:simreadyVersion` present
- AM.006: asset description and documentation URL present
- AM.007: all `aif:spec:*` attributes for the declared equipment class present
