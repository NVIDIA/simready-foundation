# Sensor-Camera Profile USD Authoring Guide

This document describes how to author a USD asset that conforms to the
`Sensor-Camera` profile.

`Sensor-Camera` is a sensor profile: it validates the render pipeline wiring
an asset carries, not the asset itself. Stamp it alongside the asset's primary
profile ([`Robot-Body`](robot-body.md), [`Robotics-Prop`](robotics-prop.md), or whichever profile matches the host asset — see the [profile index](profiles.md#profile-comparison)).

Despite the name, this profile is not limited to cameras. `RenderProduct` and
`RenderVar` prims are render pipeline infrastructure shared by every RTX
sensor, LiDAR included. That is why the capability lives under
`rendering/render_products/` rather than under a sensor modality. An asset
whose LiDAR writes through a render product is checked by this profile as
well as by [`Sensor-LiDAR`](sensor-lidar.md).

Validating an asset against this profile requires both the Sensors tier and
the Core tier:

```bash
pip install simready-validate simready-foundation-tier-sensors simready-foundation-tier-core
```

## Profile definition

The `Sensor-Camera` profile contains a single feature (see `profiles.toml`
alongside this document, and the
[feature dependency graph](../features/feature-dependency-graph)):

```toml
[Sensor-Camera]
"1.0.0" = {features = [
    {"FET_035_RTX" = {version = "0.1.0"}}, # "Render Products (camera pipeline, AOVs)"
]}
```

[`FET_035_RTX`](../features/FET_035_RTX.md) defines the contract for the USD
render pipeline used by synthetic data generation (SDG) and
software-in-the-loop (SIL) workflows.

## What the profile checks

All six requirements belong to the
[Visual Sensors/Render Products](../capabilities/rendering/render_products/capability-render_products.md)
capability.

| Requirement | Summary |
|---|---|
| [`RP.001`](../capabilities/rendering/render_products/requirements/render-product-camera.md) | A `RenderProduct` must have a `camera` relationship targeting a valid prim. |
| [`RP.002`](../capabilities/rendering/render_products/requirements/render-product-ordered-vars.md) | A `RenderProduct` must have an `orderedVars` relationship containing at least one valid `RenderVar`. |
| [`RP.003`](../capabilities/rendering/render_products/requirements/render-var-source-name.md) | A `RenderVar` must have a non-empty `sourceName`. |
| [`RP.004`](../capabilities/rendering/render_products/requirements/semantic-aov-compression.md) | A `RenderVar` whose `sourceName` starts with `semantic` must use BLOSC compression. |
| [`RP.005`](../capabilities/rendering/render_products/requirements/compression-type-valid.md) | `srtx:compression:type`, when authored, must be `hevc`, `h264`, `av1`, or `blosc`. |
| [`RP.006`](../capabilities/rendering/render_products/requirements/generic-model-output-compression.md) | A `RenderVar` with `sourceName = "GenericModelOutput"` should use BLOSC compression. Warning, not failure. |

These checks apply only to the `RenderProduct` and `RenderVar` prims a stage
actually contains. An asset with no render products **passes** this profile
without asserting anything. A passing result therefore means "every render
product present is wired correctly", not "this asset produces annotated
output" — confirm the render products exist before treating conformance as
evidence that it does.

## Required USD authoring

### Wire each render product to a camera and at least one AOV

A `RenderProduct` with no camera has nothing to render from, and one with no
`orderedVars` has nowhere to write. Both produce an empty pipeline that loads
without complaint.

```usd
def Xform "World"
{
    def Camera "RGB_Camera"
    {
        float focalLength = 24.0
    }

    def RenderVar "RgbRenderVar"
    {
        token sourceName = "rgb"          # RP.003
        token dataType = "color3f"
    }

    def RenderProduct "RenderProduct"
    {
        rel camera = </World/RGB_Camera>              # RP.001
        rel orderedVars = [</World/RgbRenderVar>]     # RP.002
        int2 resolution = (1920, 1080)
    }
}
```

The prims sit under a common root because the relationship targets are
absolute paths. Authored at stage top level without that root, `</World/...>`
resolves to nothing and the asset fails the very rules this snippet
demonstrates. Only the commented lines are required by the profile;
`focalLength`, `dataType`, and `resolution` are authored to suit the sensor.

Every `RenderVar` needs a non-empty `sourceName` (`RP.003`); the name selects
which annotator feeds the variable, so an empty one silently produces no
output.

### Choose compression by data type, not by habit

Compression is where this profile does its most valuable work, because every
failure mode here is silent. `srtx:compression:type` is optional — omit it and
no compression is applied — but an authored value must be one of exactly four
codecs (`RP.005`). An unrecognised value such as `h265` does not raise an
error; the encoder simply fails to initialize and no output appears.

| Codec | Intended for |
|---|---|
| `hevc`, `h264`, `av1` | Video-like outputs such as `LdrColor` and `HdrColor` |
| `blosc` | Non-visual or high-bit-depth data: `GenericModelOutput`, `HdrColor`, `DepthLinearSD`, and semantic AOVs |

Semantic AOVs must use `blosc` (`RP.004`). Segmentation output is integer
label data, and a lossy video codec alters those integers, which quietly
corrupts the labels a training set depends on.

```usd
def RenderVar "SemanticVar"
{
    token sourceName = "semanticSegmentation"
    token dataType = "uint"
    uniform token srtx:compression:type = "blosc"
}
```

`RP.006` applies the same reasoning to `GenericModelOutput`, which carries
LiDAR point cloud data — per-point coordinates, intensities, timestamps. It is
a warning rather than a failure because a pipeline may have a deliberate
reason to override compression, but a lossy codec there corrupts point cloud
values in ways that are hard to trace back to their cause.

When `RP.004` fails, the validation report includes a suggested fix that sets
`srtx:compression:type = "blosc"` on the offending semantic AOV render vars.
Read the report rather than assuming the change was applied; suggestions are
reported, not written into the asset.

## Validation

A sensor profile is validated in its own run. "Stamping both profiles" means
validating the asset against each one; there is no combined invocation:

```bash
simready-validate --profile Robotics-Prop --version 4.0.0 path/to/asset.usd
simready-validate --profile Sensor-Camera --version 1.0.0 path/to/asset.usd
```

Both runs must pass. The sensor profile is not a substitute for the primary
one — on its own it says nothing about units, hierarchy, physics, materials,
or packaging.

If you record the result in the optional `validation` dictionary under
`SimReady_Metadata`, note that the documented form holds a single `profile`
and `profile_version`. Record the primary profile there and track sensor
conformance alongside it; the metadata has no multi-profile form today.

## Runtime verification

Static validation confirms the pipeline is wired and the codecs are legal. It
cannot confirm that annotators return data. Two Benchmark tests cover that:

```bash
pip install "simready-foundation-tier-sensors[benchmark]"
simready-benchmark --features FET_035_RTX
```

The `[benchmark]` extra installs the Benchmark engine; a validator-only tier
install does not include it.

- `render_product_output` verifies the structural wiring and that each
  annotator returns non-empty output through Replicator.
- `semantic_aov_output` verifies BLOSC compression is authored and that
  semantic annotators return non-empty arrays.

## Samples

Passing:

- `sample_content/common_assets/sensors/render_products/RenderProductsCheckerPass.usda`
- `sample_content/common_assets/sensors/render_products/SemanticAovCompressionCheckerPass.usda`
- `sample_content/common_assets/sensors/render_products/GenericModelOutputCompressionCheckerWarn.usda` (illustrates the `RP.006` warning)

Failing:

- `sample_content/common_assets/sensors_fails/render_products/RenderProductsCheckerFail.usda`
- `sample_content/common_assets/sensors_fails/render_products/SemanticAovCompressionCheckerFail.usda`
- `sample_content/common_assets/sensors_fails/render_products/CompressionTypeCheckerFail.usda`

## References

- [`FET_035_RTX` feature](../features/FET_035_RTX.md)
- [Render Products capability](../capabilities/rendering/render_products/capability-render_products.md)
- [`Sensor-LiDAR` profile](sensor-lidar.md)
- `profiles.toml`, the profile definition alongside this document
