# Feature: `FET201_AIF`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET201_AIF` |
| Runtime | `AIF` |
| Proprietary Techs | `None` |
| Latest Version | `0.2.0` |

## Description

Declares every interface on a piece of equipment — where a pipe, cable, duct or fibre meets
it, and what passes through. An asset that satisfies this feature can be composed into a
facility by another tool without hand-integration: run lengths, connection compatibility and
service clearance all follow from what the asset states.

In v0.1.0 a connection point is a named prim. A tool finds a port by parsing `fws_supply`
out of the prim name, and engineering values sit on the equipment as one number for the
whole unit: `aif:spec:nominalFlow` for a coolant distribution unit (CDU) with four ports.

v0.2.0 moves that onto the connection itself. Each connection point declares what it is
(`domain`, `direction`, `system`, `disconnectType`, `serviceClearance`) and what passes
through it, per port and per domain: flow rate, temperature and pressure for thermal;
voltage, current, phases and rated power for electrical; line rate and connector type for
network; vent area and airflow for airflow. A tool composes a facility by querying `domain`,
`system` and `direction` instead of parsing names, and reads boundary conditions per port
instead of per unit.

The four domains share one base vocabulary and differ only in their domain namespace:

| Domain | Vocabulary in v0.2.0 | Feature it enables | Runtime |
|---|---|---|---|
| electrical | `…:electrical:` | [AIF Electrical](FET_203-electrical.md) | StratumSim |
| thermal | `…:thermal:` | [AIF Thermal Cooling](FET_202-thermal_cooling.md) | StratumSim |
| network | `…:network:` | — | NVIDIA Air |
| airflow | `…:airflow:` | — | StratumSim |
| mechanical | reserved token, no namespace in v0.2.0 | robotics assembly | — |
| pneumatic | reserved token, no namespace in v0.2.0 | — | — |

Normative source: [Connection Points](../capabilities/aif/connection_points/capability-connection_points.md)
(CP.001–012, accepted 2026-05-29 for v0.2.0). This page states which of its rules SRF
validates and how the feature is tested; it does not restate the vocabulary. Per the spec's
schema-maturity decision these are namespaced attributes, not USD typed or applied API
schemas. Schema promotion stays a future consideration.

**Why the vocabulary sits under a feature.** Connection Points is conceptually a Capability:
a bare connection point changes no simulation output until a domain vocabulary gives it
meaning. It is carried here as an interim feature entry so profiles can select it, until SRF
supports referencing a Capability directly from a Profile. The carrier drops the `AIF` prefix
when that unwind happens, which is what makes the vocabulary reusable beyond AI factories.

## Dependency Graph

```{mermaid}
flowchart LR
    FET201["FET201_AIF\n0.1.0 / 0.2.0"]
    FET200["FET200_AIF\n0.1.0"]
    FET202["FET202_AIF\n0.1.0"]
    FET203["FET203_AIF\n0.1.0"]

    FET201 --> FET200
    FET202 --> FET201
    FET203 --> FET201

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET201 current
    class FET200,FET202,FET203 other
```

AIF Thermal Cooling and AIF Electrical layer on this feature. It owns the connection
vocabulary and its internal consistency; they own what a given equipment class must declare.

## Use Cases

Products or workflows that consume this feature:

- StratumSim and NVIDIA Air as runtimes; the DSX / AI Factory operational twin.
- Equipment manufacturers publishing datacenter assets: Vertiv, Trane, Eaton, Siemens, Schneider.
- Cadence and ETAP, as independent software vendors consuming the simulation data.
- Dassault 3DEXPERIENCE, PTC and Siemens, as model-based systems engineering and PLM hosts.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

Connection points exist as discoverable, correctly-named geometry.

#### Used in Profiles

This version is used in the following profiles:

- **[`AIF-Entity`](../profiles/aif-entity.md)** (`v0.1.0`).

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [AIF Core Metadata](FET_200-aif_metadata.md) (`FET200_AIF@0.1.0`) |

#### Requirement List

* Capability: [AIF/Connection Points](../capabilities/aif/connection_points/capability-connection_points.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `CP.001` | [ConnectionPoints-Scope-Structure](../capabilities/aif/connection_points/requirements/connectionpoints-scope-structure.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.004` | [Connection-Point-Naming-Convention](../capabilities/aif/connection_points/requirements/connection-point-naming-convention.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.005` | [Connection-Points-Composition](../capabilities/aif/connection_points/requirements/connection-points-composition.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |

Documented normatively and outside this version's requirement set: CP.002 (Plane or Disk
geometry), CP.003 (`purpose = "guide"`), CP.006 (alignment to physical openings).

</details>

### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

Connection points are Xform prims carrying `simready:connectionPoint:*` properties. A profile
sees this version only once it names it; selecting it changes nothing about how any existing
asset validates.

#### Used in Profiles

This version is used in the following profiles:

- **[`AIF-Entity`](../profiles/aif-entity.md)** (`v0.2.0`).

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [AIF Core Metadata](FET_200-aif_metadata.md) (`FET200_AIF@0.1.0`) |

#### Requirement List

* Capability: [AIF/Connection Points](../capabilities/aif/connection_points/capability-connection_points.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `CP.001` | [ConnectionPoints-Scope-Structure](../capabilities/aif/connection_points/requirements/connectionpoints-scope-structure.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.005` | [Connection-Points-Composition](../capabilities/aif/connection_points/requirements/connection-points-composition.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.010` | [Connection-Point-Prim-Structure](../capabilities/aif/connection_points/requirements/connection-point-prim-structure.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.011` | [Connection-Point-Base-Namespace](../capabilities/aif/connection_points/requirements/connection-point-base-namespace.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |
| `CP.012` | [Connection-Point-Domain-Namespace](../capabilities/aif/connection_points/requirements/connection-point-domain-namespace.md) | [Implementation](../capabilities/aif/connection_points/validation.py) |

CP.005 requires the metadata to be authored as composition overs in a dedicated
`*ConnectionPoints*.usda` sublayer. CP.002 and CP.003 are documented since v0.1.0 and are
brought into scope here: CP.010 requires an Xform, which a Plane or Disk mesh is not, and
carries CP.003's `purpose = "guide"` rule.

Also from Core: [Units](../capabilities/core/units/requirements.md) and
[Atomic Asset](../capabilities/core/atomic_asset/capability-atomic_asset.md). Vocabulary
units are fixed — metres, Pascals, watts, litres/second for thermal, cubic metres/second for
airflow, Celsius — and there are no unit-annotation properties.

**Open tokens.** Token values in the vocabulary are representative, not closed enumerations.
An unrecognised token is reported at informational or warning level and must not fail
validation. This applies to CP.010, CP.011 and CP.012 alike.

**Prim naming: CP.004 does not carry forward.** Semantic identity lives in properties, so the
vocabulary spec states that *"prim names are not load-bearing for tool queries and are not
validated… No naming convention is enforced by the vocabulary or its validators."* Tools query
`system` and `direction` instead. Descriptive names remain encouraged, and the spec recommends
the built-in USD `displayName` metadata for human-readable labels.

**Outside the requirement set.**
[Connection-Point-Alignment](../capabilities/aif/connection_points/requirements/connection-point-alignment.md),
CP.006, geometry aligned to physical openings. It is documented normatively and listed by
neither version; alignment is authored manually.

Completeness is reported, not failed: a connection point below production
completeness is valid and says so. The three levels, and what upgrading a v0.1.0
asset costs each party, are on the
[Connection Points capability](../capabilities/aif/connection_points/capability-connection_points.md).

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Via the AIF pipeline samples, which convert vendor CAD to USD and author the connection points.

Validation or runtime pipeline:

- `simready-validate` — checks the connection point vocabulary against the `AIF-Entity` profile.
- **StratumSim** — datacenter physical simulation, steady-state. Covers the `thermal`,
  `electrical` and `airflow` domains. Engine and CLI: `stratumsim`.
- **NVIDIA Air** — networking digital twin. Covers the `network` domain.

## Samples

Per-class exemplars cover the three connection profiles the vocabulary was validated against:
thermal-dominant, electrical-dominant, network-dominant.

| Class | Asset | Exercises |
|---|---|---|
| CDU | Generic_CDU | thermal — FWS + TCS liquid loops |
| UPS | Synthetic_UPS | electrical — power ports, DC bus |
| Compute rack | generic | network — OSFP, high-speed data |
| CRAH | generic | airflow + liquid supply/return |

Each conforming exemplar has a deliberately-broken counterpart. Those counterparts were
authored against a specific set of harness assertions and name the assertion that catches
each planted defect, so they exercise those assertions rather than the asset. Treat them as
fixtures for the harness rather than as sample assets.

The sample assets are in `sample_content/aif/` — `Generic_CDU`, `gb300`, `Synthetic_CRAH` and
`Synthetic_UPS`, one per equipment class.

## Benchmarks

- None registered. One benchmark per domain feature is specified on the
  [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points.md#proving-the-vocabulary-at-runtime); none is
  authored in the SimReady benchmark library yet.

## Adapters

| From Feature | To Feature | Adapter | Status | Notes |
|--------------|------------|---------|--------|-------|
| `FET201_AIF@0.1.0` | `FET201_AIF@0.2.0` | — | Planned | Derives v0.2.0 property layers from the v0.1.0 connection point prims. The prim name carries `domain`, `direction` and `system` under CP.004, and the equipment-level `aif:spec:*` values give the per-port starting values, so the structural conversion is mechanical. The engineering values that have no v0.1.0 source are the part a person has to supply. |

Step-by-step conversion, including tooling for already-fielded assets, belongs to the partner
end-to-end runbook rather than to this feature.
