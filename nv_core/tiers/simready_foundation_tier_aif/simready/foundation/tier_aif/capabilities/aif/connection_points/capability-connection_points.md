# Connection Points

**Capability:** Connection Points (CP)

## Overview

Validates AIF connection point prims that represent thermal, electrical, and airflow interfaces on equipment assets. Connection points are simple geometry prims (Plane or Disk) positioned at equipment openings: piping connections, electrical sockets, and air vents.

CP.002 belongs to v0.1.0 and CP.010 replaces it. CP.010 carries CP.003's `purpose = "guide"` rule into v0.2.0. CP.006 is listed by neither version.

Version 0.2.0 of the vocabulary describes a connection point as an Xform prim carrying
namespaced `simready:connectionPoint:*` properties, replacing the geometry prims and
name-parsing of v0.1.0. It is covered by CP.010, CP.011 and CP.012. Both vocabularies
coexist and assets migrate incrementally.

## Validation profiles

The spec defines three completeness levels, and validators report which one an asset
satisfies rather than treating incompleteness as failure:

| Profile | Contents | Validator behaviour |
|---|---|---|
| **Stub** | All five base properties, no domain properties | Structurally valid; reported incomplete |
| **Draft** | All five base properties plus at least one domain property | Missing domain properties are warnings |
| **Production** | All base plus all domain properties for its domain | The target state; required for simulation-ready |

## Upgrading from v0.1.0

Both forms coexist indefinitely. There is no coordinated cutover date, and a v0.1.0 asset
stays valid against a v0.1.0 profile. What the upgrade costs is different for each party.

**In SRF.** A profile opts in by naming `version = "0.2.0"`; until it does, nothing it
validates changes. Under v0.2.0, TC.002 and EL.004 locate connection points by property query
rather than by prim name.

**For an asset author.** Add the five base properties to each connection Xform, then the
domain properties for that connection's domain. Existing equipment-level properties such as
`aif:spec:nominalFlow` stay where they are; nothing is removed. Where a pre-release asset used
`simready:connectionPoint:type`, rename it to `domain`. Validators warn and map the old name,
and it will not survive a future schema promotion. Aim for the production profile; stub and
draft assets are valid and report as incomplete.

**For a consuming tool.** This is the migration with real work in it. Boundary conditions move
from one value per unit to one per port, and ports are found by querying `domain`, `system`
and `direction` instead of by parsing prim names. A tool that only reads v0.1.0 properties
keeps working. A tool that wants per-port data is rewritten.

**What stops being guaranteed.** CP.004 does not carry forward, so prim names are no longer
validated. Anything that infers meaning from a name like `fws_supply` keeps working only for
as long as authors happen to keep writing that name, and fails silently rather than loudly
when one doesn't. That is the practical reason to move a name-parsing consumer onto property
queries even though its current code still runs.

</details>

## Proving the vocabulary at runtime

One benchmark per domain feature. Each reads `simready:connectionPoint:*` properties off the
asset, per port rather than per unit, and never parses prim names. Binding one connection
point to another is outside v0.2.0, so the harness authors the topology and the assets supply
what flows through it.

Common to all of them: the benchmark runs after the static conformance validator. SimReady's
job is to give the runtime the inputs it needs; the runtime produces the report. Numeric
bounds are not specified here; they come from the domain SMEs when the benchmarks are
authored on the shared harness.

Proving a rule rejects a bad asset belongs to the validators, where a fixture violates one
stated requirement and that requirement's checker must report it. CP.010–012 carry that
obligation. A benchmark answers a different question, whether the asset drives the runtime at
all, and a paired invalid asset does not help answer it: measured against StratumSim, the CP2
UPS exemplar and its deliberately-broken twin are admitted identically, because the twin's
defects are value errors and the runtime's admission gate checks types and structure.

| Verdict | Condition |
|---|---|
| **Pass** | Every value the runtime needed was read from a connection point, the runtime accepted the layout built from them, and the run returned non-default results. |
| **Fail** | A required value is absent or wrong, or the runtime rejects the layout. |
| **Incomplete** | The runtime has no parameter for what the asset declares, so the declared value cannot reach the result. Also reported when an asset is below production validation profile. Distinct from Pass, so a partial run is never read as green. |

### Electrical benchmark

1. Build a stage with the SimReady asset. Two classes on one power network, an
   uninterruptible power supply feeding a compute rack, exercises the per-port case.
2. Stand up StratumSim.
3. Lift the electrical connection point properties off the asset and populate an in-memory
   layout: equipment types, rated power, nominal voltage, phases, frequency.
4. Run StratumSim and verify the results are non-default, meaning they follow from the
   declared values rather than from template defaults.

### Thermal benchmark

1. Build a stage with the SimReady asset.
2. Stand up StratumSim.
3. Lift the thermal connection point properties and populate the cooling equipment's
   parameters: design flow rate, temperatures, operating pressure.
4. Run StratumSim and verify the results are non-default.

Step 4 needs a StratumSim equipment path in which heat load, flow, pump or fan operation and
supply/return temperatures affect one another. Against a generic cooling template each channel
follows its own default and the results are default by construction.

### Network benchmark

Two routes, not exclusive.

**Compatibility, no runtime required.**

1. Build a stage with two assets whose network ports are intended to mate.
2. For each declared port, compare `portType`, `supportedConfigurations` and
   `allowedTransceivers` against the port it meets.
3. Verify compatible pairs are accepted and incompatible ones rejected.

**Fabric instantiation in NVIDIA Air.**

1. Build a stage with the SimReady asset.
2. Lift the network connection point properties into an Air topology: nodes, ports, line rates.
3. Import the topology and start the simulation through the DSX Air SDK.
4. Verify the node comes up carrying the declared ports.

### Airflow benchmark

As thermal, against the airflow properties, and with the same requirement of the runtime.

```{toctree}
:maxdepth: 1

Requirements <requirements>
```
