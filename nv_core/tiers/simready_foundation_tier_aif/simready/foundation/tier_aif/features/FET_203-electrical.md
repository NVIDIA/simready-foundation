# Feature: `FET203_AIF`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET203_AIF` |
| Runtime | `AIF` |
| Proprietary Techs | `None` |
| Latest Version | `0.2.0` |

## Description

Declares what a piece of equipment draws from the facility supply. An asset that satisfies
this feature states its nominal voltage, power rating and line frequency, and carries an
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
    FET203["FET203_AIF\n0.1.0"]
    FET201["FET201_AIF\n0.1.0"]
    FET200["FET200_AIF\n0.1.0"]

    FET203 --> FET201
    FET201 --> FET200

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET203 current
    class FET200,FET201 other
```

## Use Cases

Products or workflows that consume this feature:

- StratumSim datacenter physical simulation, for facility power topology and overload detection.
- DSX / AI Factory operational twin, for electrical capacity planning.
- Cadence and ETAP, as independent software vendors consuming the simulation data.
- Power equipment manufacturers publishing datacenter assets: Vertiv, Eaton, Schneider.

## Requirements

### Version 0.1.0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

This version is used in the following profiles:

- **[`AIF-Entity`](../profiles/aif-entity.md)** (`v0.1.0`).

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connection Points](FET_201-connection_points.md) (`FET201_AIF@0.1.0`) |

#### Requirement List

* Capability: [AIF/Electrical](../capabilities/aif/electrical/capability-electrical.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `EL.001` | [Nominal-Voltage-Required](../capabilities/aif/electrical/requirements/nominal-voltage-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.002` | [Power-Rating-Required](../capabilities/aif/electrical/requirements/power-rating-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.003` | [Electrical-Frequency-Required](../capabilities/aif/electrical/requirements/electrical-frequency-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.004` | [Electrical-Connection-Points](../capabilities/aif/electrical/requirements/electrical-connection-points.md) | [Implementation](../capabilities/aif/electrical/validation.py) |

`EL.004` identifies connection points by prim name under the v0.1.0 vocabulary. Under
v0.2.0 the same connections are found by querying `simready:connectionPoint:domain`.

</details>


### Version 0.2.0

<details>
<summary><strong>Details</strong></summary>

Identical requirements to v0.1.0, rebased onto the v0.2.0 Connection Points vocabulary. A
v0.2.0 profile selects this version so that only one version of Connection Points is pulled
into the evaluation.

#### Used in Profiles

This version is used in the following profiles:

- **[`AIF-Entity`](../profiles/aif-entity.md)** (`v0.2.0`).

#### Feature Dependencies

| **Property** | **Value** |
|--------------|-----------|
| Dependency | [Connection Points](FET_201-connection_points.md) (`FET201_AIF@0.2.0`) |

#### Requirement List

* Capability: [AIF/Electrical](../capabilities/aif/electrical/capability-electrical.md)

| `EL.001` | [Nominal-Voltage-Required](../capabilities/aif/electrical/requirements/nominal-voltage-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.002` | [Power-Rating-Required](../capabilities/aif/electrical/requirements/power-rating-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.003` | [Electrical-Frequency-Required](../capabilities/aif/electrical/requirements/electrical-frequency-required.md) | [Implementation](../capabilities/aif/electrical/validation.py) |
| `EL.004` | [Electrical-Connection-Points](../capabilities/aif/electrical/requirements/electrical-connection-points.md) | [Implementation](../capabilities/aif/electrical/validation.py) |

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
  [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points.md#electrical-benchmark), which owns the connection
  vocabulary this feature layers on.

## Adapters

None.
