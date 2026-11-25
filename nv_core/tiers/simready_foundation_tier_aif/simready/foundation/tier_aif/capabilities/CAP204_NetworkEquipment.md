# Capability: `CAP204_NetworkEquipment`

| Property | Value |
|---|---|
| Contract | `CAP204_NetworkEquipment.0-3-0` |
| Display name | AIF Network Equipment |
| Tier | AIF |
| Classification | Non-standard, capability-only |
| Status | Proposed for review |
| Dependencies | `CAP200_AifMetadata.0-3-0`, `CAP201_ConnectionPoints.0-3-0` |
| Requirements | `NET.001`, `NET.002`, `NET.003` |
| Profile | `AIF-Entity@0.3.0` |

The [network requirements](../rules_and_reqs/aif/network_equipment/capability-network_equipment.md)
apply when the Properties-layer or composed `aif:core:assetClass` resolves to
`network-equipment`. Other equipment classes retain their own class-specific
requirements; AM.008 rejects unknown classes. Network equipment is registered
only in the AIF 0.3 class catalog. Legacy AM.007 continues to reject that class,
and AIF-Entity 0.1.0 / 0.2.0 retain their published selections and class behavior.

DSX Air is the intended pre-simulation consumer. Offline validation proves data
structure, not simulator import, image availability or network runtime behavior.
No simulator adapter, cable model or scene-level link schema is introduced.

The [synthetic sample](../../../../../../../sample_content/aif/Synthetic_NetworkEquipment/)
is fictional and exercises AIF-Entity 0.3.0. Allocation semantics, supported
images, MB/GB interpretation and consumer mapping require acceptance review.
