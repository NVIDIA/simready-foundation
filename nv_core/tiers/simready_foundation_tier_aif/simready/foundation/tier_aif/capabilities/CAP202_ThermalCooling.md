# Capability: `CAP202_ThermalCooling`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `CAP202_ThermalCooling` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0`, `0-2-0` |

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
    FET202["CAP202_ThermalCooling\n0-1-0"]
    FET201["CAP201_ConnectionPoints\n0-1-0"]
    FET200["CAP200_AifMetadata\n0-1-0"]

    FET202 --> FET201
    FET201 --> FET200

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET202 current
    class FET200,FET201 other
```

## Use Cases

Products or workflows that consume this capability:

- StratumSim datacenter physical simulation, for steady-state facility thermal models.
- DSX / AI Factory operational twin, for cooling capacity planning.
- Cooling equipment manufacturers publishing datacenter assets: Vertiv, Trane, Schneider.

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

* Capability: [AIF/Thermal Cooling](../rules_and_reqs/aif/thermal_cooling/capability-thermal_cooling.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `TC.001` | [Nominal-Cooling-Capacity](../rules_and_reqs/aif/thermal_cooling/requirements/nominal-cooling-capacity.md) |
| `TC.002` | [Thermal-Cooling-Connection-Points](../rules_and_reqs/aif/thermal_cooling/requirements/thermal-cooling-connection-points.md) |

`TC.002` identifies connection points by prim name under the v0.1.0 vocabulary. Under
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

* Capability: [AIF/Thermal Cooling](../rules_and_reqs/aif/thermal_cooling/capability-thermal_cooling.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `TC.001` | [Nominal-Cooling-Capacity](../rules_and_reqs/aif/thermal_cooling/requirements/nominal-cooling-capacity.md) |
| `TC.002` | [Thermal-Cooling-Connection-Points](../rules_and_reqs/aif/thermal_cooling/requirements/thermal-cooling-connection-points.md) |

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
  [Connection Points capability](../rules_and_reqs/aif/connection_points/capability-connection_points.md#thermal-benchmark), which owns the connection
  vocabulary this capability layers on.

## Adapters

None.


## Version 0-3-0 — AIF 0.3

`CAP202_ThermalCooling.0-3-0` carries exactly the same requirements as version
0-2-0 and depends on `CAP201_ConnectionPoints.0-3-0`. This keeps the AIF 0.3
dependency graph on its versioned metadata catalog while preserving the 0.2
connection-point vocabulary and thermal/electrical expectations. The 0-1-0 and
0-2-0 definitions remain unchanged.
