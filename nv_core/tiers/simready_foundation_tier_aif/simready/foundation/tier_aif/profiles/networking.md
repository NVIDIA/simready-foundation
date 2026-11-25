# Networking

`Networking@0.3.0` is the dedicated AIF networking-equipment profile. It selects
network-device eligibility, typed equipment metadata, pre-simulation node
configuration and CP2 network ports, with the Core visual and publishing baseline.

| Kind | Exact selector |
|---|---|
| Feature | `FET001_MinimalPlaceableVisual.1-0-0` |
| Feature | `FET207_SimulationNetworkTopology.0-3-0` |
| Capability | `CAP000_Core.0-2-0` |
| Capability | `CAP200_AifMetadata.0-3-0` |
| Capability | `CAP201_ConnectionPoints.0-3-0` |
| Capability | `CAP204_Networking.0-3-0` |
| Capability | `CAP031_SelfContainedPackage.0-1-0` |
| Capability | `CAP033_SimReadyPackage.0-4-0` |

All selectors are required and exact. The feature selects the Networking capability,
which depends on the same metadata and connection-point versions; catalog
resolution deduplicates the repeated selections. The profile carries no earlier AIF contract version.

[NET.004](../rules_and_reqs/aif/network_equipment/requirements/network-device-eligibility.md)
requires `aif:core:assetClass = "network-equipment"` in both the Properties layer
and composed root. This distinguishes the dedicated profile from AIF-Entity's
class-conditional network requirements. A generic nonnetwork equipment asset
fails Networking eligibility. Existing AIF-Entity 0.1.0, 0.2.0 and 0.3.0 remain
independently selectable with their existing contract selections.

The [synthetic switch](../../../../../../../sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda)
is a standalone positive example with static validation receipts for
`Networking@0.3.0` and `AIF-Entity@0.3.0`. Its package declares one equipment
interface, keeps the render stage in `dcc_source/` and passes the
`Package-Candidate@1.3.0` preflight. After regenerating and rendering the switch,
run `python validate.py --stamp` from its sample directory to refresh both receipts.
Evaluate reads them during planning. A staged copy with a
different equipment class is a negative eligibility case.

[Simulation Network Topology](../features/FET207_SimulationNetworkTopology.md) specifies
connectivity checks between two devices in an explicitly designated, running
DSX Air simulation. The authored equipment properties configure nodes before
simulation starts; scene topology, supported node/image mappings and the selected
running simulation define the runtime test context. Static profile validation
and runtime connectivity evidence are reported separately. A standalone asset's
offline pass does not establish runtime connectivity.
