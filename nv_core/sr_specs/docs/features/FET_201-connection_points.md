# Connection Points

**Feature ID:** FET201_AIF_NEUTRAL

> **Reclassified as a Capability.** Connection Points is a Capability, not a
> Feature, and drops the "AIF" prefix for cross-vertical reuse (e.g.
> robotics/grippers). Authoritative documentation now lives in the
> [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points).
> This entry is retained as an **interim feature carrier**: its rules stay in the
> `FET_201` feature JSON so validation passes until SRF supports
> Profile-to-Capability referencing.

Requires connection point prims organized under a `ConnectionPoints` scope, following naming conventions, and composed as a separate sublayer.

## Requirements

- CP.001: `ConnectionPoints` Scope prim exists
- CP.002: connection point geometry is Plane or Disk *(deferred to v0.2.0)*
- CP.003: connection point prims have `purpose = "guide"` *(deferred to v0.2.0)*
- CP.004: connection point prims follow `<vendor>_<type>_<suffix>` naming
- CP.005: `<AssetName>_ConnectionPoints.usd` sublayer present
- CP.006: connection point geometry is aligned to physical openings *(deferred to v0.2.0+)*

## Dependencies

- FET200_AIF_NEUTRAL v0.1.0 (AIF Core Metadata)
