# Simulation Network Topology

| Contract | Reference simulator | Profile |
|---|---|---|
| `FET207_SimulationNetworkTopology.0-3-0` | DSX Air | [Networking 0.3.0](../profiles/networking.md) |

A named USD network port maps to a source interface in the simulated topology.
The source and peer must be distinct devices whose designated interfaces share a
direct link. The connectivity check passes when the peer responds to at least one
of three IPv4 echo requests sent through the mapped source interface.

## Asset requirements

The [Networking capability](../capabilities/CAP204_Networking.md) selects equipment identity,
node resources and network ports. [NET.004](../rules_and_reqs/aif/network_equipment/requirements/network-device-eligibility.md)
requires the network-equipment class for this feature. Static validation uses
the composed equipment USD and its Properties layer. The runtime measurement
uses the existing simulation and the port mapping supplied by its operator.

## DSX Air connectivity procedure

Use two Linux devices in an active [DSX Air](https://dsx-air.nvidia.com/) simulation with a direct data link,
IPv4 addresses on that link, iproute2 and iputils. Each device needs an existing
SSH service and a guest user with permission to run the probes. Set
`DSX_AIR_TOKEN` through the environment to a bearer with read access to the
simulation, its exported topology, nodes, interfaces and services. Set
`DSX_AIR_ORG` if required by the account. OpenSSH uses the local SSH agent or
default identities and verifies the worker host key in the user's known hosts.

Create a local JSON fixture with the actual simulation and SSH service UUIDs.
The values below illustrate the mapping for the synthetic switch.

```json
{
  "simulation_id": "00000000-0000-4000-8000-000000000001",
  "asset_port": "ethernet_01",
  "source": {
    "service_id": "00000000-0000-4000-8000-000000000002",
    "user": "cumulus",
    "interface": "swp1"
  },
  "peer": {
    "service_id": "00000000-0000-4000-8000-000000000003",
    "user": "cumulus",
    "interface": "swp2"
  },
  "peer_ipv4": "192.0.2.2"
}
```

The adapter resolves both SSH services to distinct nodes in the specified
simulation, verifies the direct link in the exported topology, checks the
address on the peer and binds the ping to the source interface. The result
includes the simulation ID, USD port, device and interface names, peer address
and transmitted/received counts. No replies is a measured failure. Missing
access or an invalid fixture is an execution error.

With the AIF tier installed, run the adapter directly from the repository root:

```sh
python -m simready.foundation.tier_aif.dsx_air \
  sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda \
  /path/to/lab-fixture.json
```

For Evaluate, provide the same fixture through `DSX_AIR_CONNECTIVITY_FIXTURE`.
The manifest selects `simready.foundation.tier_aif.runtime_tests:device_connectivity`.
Its adapter is `simready.foundation.tier_aif.dsx_air:run_connectivity`.
