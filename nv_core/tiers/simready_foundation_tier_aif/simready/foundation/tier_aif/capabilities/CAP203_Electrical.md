# Capability: `CAP203_Electrical`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP203_Electrical` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

## Description

Declares what a piece of equipment draws from the facility supply. An asset that satisfies
this capability states its nominal voltage, power rating and line frequency, and carries an
electrical connection point, so a facility power model can size a feed and detect an
overload from the asset's own declared values.

The three AC concepts appear under a different `aif:spec:*` name on each equipment class.
The name each class uses, and whether the class takes an AC supply at all, are declared per
class in `config/aif-equipment-<class>.json` rather than in the validator. The feature
applies to `CDU`, `CRAH` and `UPS` today. Compute rack equipment takes DC power profiles
rather than AC parameters, so the feature does not apply to it.

## Dependency Graph

```{mermaid}
flowchart LR
    FET203["CAP203_Electrical\n0-1-0"]
    FET201["CAP201_ConnectionPoints\n0-1-0"]
    FET200["CAP200_AifMetadata\n0-1-0"]

    FET203 --> FET201
    FET201 --> FET200

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET203 current
    class FET200,FET201 other
```

## Use Cases

Products or workflows that consume this capability:

- StratumSim datacenter physical simulation, for facility power topology and overload detection.
- DSX / AI Factory operational twin, for electrical capacity planning.
- Cadence and ETAP, as independent software vendors consuming the simulation data.
- Power equipment manufacturers publishing datacenter assets: Vertiv, Eaton, Schneider.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [AIF-Entity](../profiles/aif-entity.md): required in `0.1.0`

#### Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connection Points](CAP201_ConnectionPoints.md) (`CAP201_ConnectionPoints.0-1-0`) |

#### Requirement List

* Capability: [AIF/Electrical](../rules_and_reqs/aif/electrical/capability-electrical.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `EL.001` | [Nominal-Voltage-Required](../rules_and_reqs/aif/electrical/requirements/nominal-voltage-required.md) |
| `EL.002` | [Power-Rating-Required](../rules_and_reqs/aif/electrical/requirements/power-rating-required.md) |
| `EL.003` | [Electrical-Frequency-Required](../rules_and_reqs/aif/electrical/requirements/electrical-frequency-required.md) |
| `EL.004` | [Electrical-Connection-Points](../rules_and_reqs/aif/electrical/requirements/electrical-connection-points.md) |

`EL.004` identifies connection points by prim name under the v0.1.0 vocabulary. Under
v0.2.0 the same connections are found by querying `simready:connectionPoint:domain`.

</details>


### Version 0-2-0

<details>
<summary><strong>Details</strong></summary>

Identical requirements to v0.1.0, rebased onto the v0.2.0 Connection Points vocabulary. A
v0.2.0 profile selects this version so that only one version of Connection Points is pulled
into the evaluation.

#### Used in Profiles

- [AIF-Entity](../profiles/aif-entity.md): required in `0.2.0`

#### Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connection Points](CAP201_ConnectionPoints.md) (`CAP201_ConnectionPoints.0-2-0`) |

#### Requirement List

* Capability: [AIF/Electrical](../rules_and_reqs/aif/electrical/capability-electrical.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `EL.001` | [Nominal-Voltage-Required](../rules_and_reqs/aif/electrical/requirements/nominal-voltage-required.md) |
| `EL.002` | [Power-Rating-Required](../rules_and_reqs/aif/electrical/requirements/power-rating-required.md) |
| `EL.003` | [Electrical-Frequency-Required](../rules_and_reqs/aif/electrical/requirements/electrical-frequency-required.md) |
| `EL.004` | [Electrical-Connection-Points](../rules_and_reqs/aif/electrical/requirements/electrical-connection-points.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Via the AIF pipeline samples, which convert vendor CAD to USD and author the metadata.

Validation or runtime pipeline:

- `simready-validate` — checks the electrical contract against the `AIF-Entity` profile.
- StratumSim — consumes the declared values in a facility power model.

## Samples

Sample assets carrying electrical connection points, under `sample_content/aif/`:

- `Synthetic_UPS` — UPS, nominal voltage feed
- `Synthetic_CRAH` — CRAH, fan supply
- `Generic_CDU` — CDU, pump supply
- `gb300` — compute rack, eight feeds

## Benchmarks

- None registered. The electrical benchmark is specified on the
  [Connection Points capability](../rules_and_reqs/aif/connection_points/capability-connection_points.md#electrical-benchmark), which owns the connection
  vocabulary this capability layers on.

## Adapters

None.


## Version 0-3-0 — AIF 0.3

`CAP203_Electrical.0-3-0` carries exactly the same requirements as version
0-2-0 and depends on `CAP201_ConnectionPoints.0-3-0`. This keeps the AIF 0.3
dependency graph on its versioned metadata catalog while preserving the 0.2
connection-point vocabulary and thermal/electrical expectations. The 0-1-0 and
0-2-0 definitions remain unchanged.
