# Networking

| Property | Value |
|---|---|
| Contract | `CAP204_Networking.0-3-0` |
| Display name | Networking |
| Tier | AIF |
| Classification | Non-standard, capability-only |
| Status | Proposed for review |
| Dependencies | `CAP200_AifMetadata.0-3-0`, `CAP201_ConnectionPoints.0-3-0` |
| Requirements | `NET.001`, `NET.002`, `NET.003` |
| Profiles | `AIF-Entity@0.3.0`, `Networking@0.3.0` |

The [network requirements](../rules_and_reqs/aif/network_equipment/capability-network_equipment.md)
apply when the Properties-layer or composed `aif:core:assetClass` resolves to
`network-equipment`. Other equipment classes retain their own class-specific
requirements; AM.008 rejects unknown classes. Network equipment is registered
only in the AIF 0.3 class catalog. Legacy AM.007 continues to reject that class,
and AIF-Entity 0.1.0 / 0.2.0 retain their published selections and class behavior.

DSX Air is the intended pre-simulation consumer. The Networking capability validates the node
configuration and port declarations offline. The [Networking feature](../features/FET207_Networking.DSXAir.md)
uses a named port from that contract to test reachability in a running simulation.

The [synthetic switch](../../../../../../../sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda)
exercises both profiles. Allocation semantics, supported
images, MB/GB interpretation and consumer mapping require acceptance review.
