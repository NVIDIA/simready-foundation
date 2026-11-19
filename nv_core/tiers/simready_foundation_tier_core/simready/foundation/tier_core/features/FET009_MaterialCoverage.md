# Feature: `FET009_MaterialCoverage`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET009_MaterialCoverage` |
| Runtime                 | `OpenUSD` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines rendered material coverage. An asset that satisfies this feature renders with its own
materials on at least `min_material_coverage` (default `0.98`) of its silhouette, measured
once for each render context the feature covers. The measurement classifies the colours of
probe renders: a pixel counts as uncovered where test-owned control materials show through,
which they do on geometry that resolves no material from the asset's own bindings. The
bindings resolve through USD, so the property belongs to the asset; the runtime tests render
it in Kit with RTX.

The feature also holds the static check, `VM.MAT.001`: every renderable Gprim resolves a
material. Static validation counts the Gprims that resolve none, and the runtime tests measure
the same property in pixels, with the renderer resolving the bindings. The two diverge on the
same defect by the visible size of the geometry concerned. They also diverge on one defect the
static check does not report: for a Gprim with `materialBind` subsets, `VM.MAT.001` checks only
the subsets, so faces outside every subset of a Gprim that resolves no material itself pass it
and fail here.

| Render context | Surface | Test | Asset with no surface on the context |
|----------------|---------|------|--------------------------------------|
| universal | UsdPreviewSurface | `preview_surface_renders` | Measured |
| `mtlx` | OpenPBR | `openpbr_renders` | Skipped |
| `mdl` | MDL | `mdl_renders` | Skipped |

The universal test never skips: every profile that selects this feature requires
[`FET006_Materials`](FET006_Materials.md), whose `VM.PS.002` reports a
material with no UsdPreviewSurface. [`FET006_Materials.Openpbr`](FET006_Materials.Openpbr.md)
and [`FET006_Materials.MDL`](FET006_Materials.MDL.md) are optional. Where no material that
renderable geometry resolves at the `full` purpose has a surface on the `mtlx` or `mdl`
context, the test for that context skips: the renderer would render the universal surfaces in
their place, which the universal test already measures. A skipped test does not fail the feature.
An asset that claims either feature and lacks its surface fails static validation
(`VM.PBR.001`, `VM.MDL.003`). A run forced with `--features` can reach the coverage tests
without that validation, and there a skip establishes only that the surface is absent.

Coverage does not establish which network the renderer evaluated. Under the `mtlx` or `mdl`
context, a material with no surface on that context renders its universal surface; under the
universal context, a material with no UsdPreviewSurface renders the renderer's fallback
material. Neither shows the
controls through, so both count as covered, and so does a shader that fails to evaluate.

## Dependency Graph

```{mermaid}
flowchart LR
    FET009["FET009_MaterialCoverage\n0-1-0"]
    FET006["FET006_Materials\n0-3-0"]

    FET009 --> FET006

    classDef current fill:#90EE90,stroke:#333
    classDef other fill:#fff,stroke:#333
    class FET009 current
    class FET006 other
```

## Use Cases

Products or workflows that consume this feature:

- RTX rendering in Kit and Isaac Sim, where a surface the asset does not bind renders with
  whatever material an enclosing scene or the renderer supplies.
- Synthetic data generation, where every pixel of the asset in a camera frame is meant to
  show the asset's own material.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Robot-Body](../profiles/robot-body.md): required in `4.0.0`
- [Robot-Gripper](../profiles/robot-gripper.md): required in `4.0.0`
- [Robotics-Prop](../profiles/robotics-prop.md): required in `5.0.0`

#### Feature Dependencies

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Dependency              | [`Materials (USDPreviewSurface)`](FET006_Materials.md) (`FET006_Materials.0-3-0`) |

#### Requirement List

* Capability: [Visualization/Materials](../rules_and_reqs/visualization/materials/capability-materials.md)
    * Requirements:
        * [Material Assignment](../rules_and_reqs/visualization/materials/requirements/material-assignment.md)
            * `VM.MAT.001`

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`, package source folder, or package root as applicable.

Validation or runtime pipeline:

- SimReady validation verifies that every renderable `Gprim` resolves a material the asset
  authors (`VM.MAT.001`).
- SimReady Evaluate renders the asset in Kit with RTX once per render context and
  compares the share of its silhouette that shows no control material against
  `min_material_coverage` (default `0.98`).

Runtime requirements:

- Kit or Isaac Sim with the RTX renderer, at the engine version each test page lists.
- Compatible `simready.evaluate` and `simready.evaluate.engine-kit` builds, selected
  by the tier's `evaluate` extra and installed in the host and engine environments.
- Pillow and numpy importable in Kit's Python. Without them the probe frames cannot be read,
  and the run ends as a setup error instead of a coverage verdict.
- Each test pins `/persistent/app/hydra/material/renderContexts` to its own context for the
  run and restores the previous list afterwards.
- Launching Kit with `--/persistent/app/material/materialx/validate=true` logs a MaterialX
  material that fails to evaluate. The FET006 `openpbr_renders` test reads that log; the
  coverage tests count such a material as covered.

## Samples

- [`obs_joystick_a01`](../../../../../../../sample_content/common_assets/props_general/obs_joystick_a01/simready_usd/sm_obs_joystick_a01_01.usd)
- [`gen_appliance_toaster_v01_01`](../../../../../../../sample_content/common_assets/props_general/gen_appliance_toaster_v01_01/simready_usd/sm_gen_appliance_toaster_v01_01.usd)

## Runtime Evaluation

- Suite: [FET006 Materials](../runtime_tests/docs/fet006-materials.md)
  - Tests:
    - [preview_surface_renders](../runtime_tests/docs/fet006/preview-surface-renders.md)
    - [openpbr_renders](../runtime_tests/docs/fet006/openpbr-renders.md)
    - [mdl_renders](../runtime_tests/docs/fet006/mdl-renders.md)

  The three FET006 render tests are registered under this feature as well as their FET006
  feature, and one run counts toward both. They cover `VM.MAT.001` at runtime.

## Adapters

None. Coverage depends on the bindings an asset authors, so no adapter derives this feature
from another one. The `simready-foundation-conform-fet-009-standard` skill repairs a coverage
failure on staged output. It binds the geometry `VM.MAT.001` reports, and each Gprim whose
`materialBind` subsets leave faces out while it resolves no material itself, to the asset's
own materials, then reruns the static gate and the coverage tests. A low coverage ratio does
not identify the defect on its own, so the skill stops when neither check names a prim.
