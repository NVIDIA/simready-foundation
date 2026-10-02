# Feature: `FET202_AIF`

| **Property** | **Value** |
|--------------|-----------|
| Feature Name | `FET202_AIF` |
| Runtime | `AIF` |
| Proprietary Techs | `None` |
| Latest Version | `0.2.0` |

## Description

Declares what a piece of cooling equipment removes heat with. An asset that satisfies this
feature states its nominal cooling capacity and carries the liquid connection points its
equipment class implies, so a facility thermal model can place it in a loop and compute a
result that follows from the asset rather than from a template default.

The feature applies to equipment whose class declares a cooling loop — `CDU` and `CRAH`
today. Which classes those are, and which connection point prefixes each one must carry,
are declared per class in `config/aif-equipment-<class>.json` rather than in the validator.
Compute rack equipment produces heat but has no cooling-specific attributes of its own, so
the feature does not apply to it.

## Dependency Graph

```{mermaid}
flowchart LR
    FET202["FET202_AIF\n0.1.0"]
    FET201["FET201_AIF\n0.1.0"]
    FET200["FET200_AIF\n0.1.0"]

    FET202 --> FET201
    FET201 --> FET200

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET202 current
    class FET200,FET201 other
```

## Use Cases

Products or workflows that consume this feature:

- StratumSim datacenter physical simulation, for steady-state facility thermal models.
- DSX / AI Factory operational twin, for cooling capacity planning.
- Cooling equipment manufacturers publishing datacenter assets: Vertiv, Trane, Schneider.

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

* Capability: [AIF/Thermal Cooling](../capabilities/aif/thermal_cooling/capability-thermal_cooling.md)

| Requirement | Requirement Doc | Rule |
|-------------|-----------------|------|
| `TC.001` | [Nominal-Cooling-Capacity](../capabilities/aif/thermal_cooling/requirements/nominal-cooling-capacity.md) | [Implementation](../capabilities/aif/thermal_cooling/validation.py) |
| `TC.002` | [Thermal-Cooling-Connection-Points](../capabilities/aif/thermal_cooling/requirements/thermal-cooling-connection-points.md) | [Implementation](../capabilities/aif/thermal_cooling/validation.py) |

`TC.002` identifies connection points by prim name under the v0.1.0 vocabulary. Under
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

* Capability: [AIF/Thermal Cooling](../capabilities/aif/thermal_cooling/capability-thermal_cooling.md)

| `TC.001` | [Nominal-Cooling-Capacity](../capabilities/aif/thermal_cooling/requirements/nominal-cooling-capacity.md) | [Implementation](../capabilities/aif/thermal_cooling/validation.py) |
| `TC.002` | [Thermal-Cooling-Connection-Points](../capabilities/aif/thermal_cooling/requirements/thermal-cooling-connection-points.md) | [Implementation](../capabilities/aif/thermal_cooling/validation.py) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`
  - Via the AIF pipeline samples, which convert vendor CAD to USD and author the metadata.

Validation or runtime pipeline:

- `simready-validate` — checks the thermal contract against the `AIF-Entity` profile.
- StratumSim — consumes the declared values in a facility thermal model.

## Samples

Sample assets carrying thermal connection points, under `sample_content/aif/`:

- `Synthetic_CRAH` — CRAH, liquid supply and return
- `Generic_CDU` — CDU, facility and technology water loops at primary and secondary
- `gb300` — compute rack, liquid supply and return

## Benchmarks

- None registered. The thermal benchmark is specified on the
  [Connection Points capability](../capabilities/aif/connection_points/capability-connection_points.md#thermal-benchmark), which owns the connection
  vocabulary this feature layers on.

## Adapters

None.
