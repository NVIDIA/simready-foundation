# Feature: `FET035_RenderProducts.RTX`

| **Property**            | **Value**         |
|-------------------------|-------------------|
| Contract                | `FET035_RenderProducts.RTX` |
| Runtime                 | `RTX` |
| Proprietary Techs       | `None` |
| Versions                | `0-1-0` |

## Description

Defines the simulation-readiness contract for the USD render pipeline wiring on assets used in synthetic data generation (SDG) and software-in-the-loop (SIL) workflows. Every RenderProduct prim must have a valid camera relationship and at least one AOV declared via orderedVars. Each RenderVar must declare a valid sourceName. Semantic AOV RenderVars must use BLOSC lossless compression to preserve integer segmentation labels.

RenderProduct and RenderVar rules apply to all sensor types including cameras and LiDAR — they are render pipeline infrastructure, not sensor-specific. The capability lives under `rendering/render_products/` rather than under any sensor modality directory.

## Dependency Graph

This feature has no dependencies and no other features depend on it directly.

## Use Cases

Products or workflows that consume this feature:

- SimReady validation verifies render product wiring requirements at asset authoring time.
- Isaac Sim Replicator SDG pipelines consume render products to generate annotated training data.
- Isaac Sim runtime evaluation tests (`render_product_output`, `semantic_aov_output`) verify live annotator output.

## Requirements

### Version 0-1-0

<details>
<summary><strong>Details</strong></summary>

#### Used in Profiles

- [Sensor-Camera](../../../../../../sr_specs/docs/shared/profiles/profiles.md): required in `1.0.0`

#### Feature Dependencies

None.

#### Requirement List

* Capability: [Visual Sensors/Render Products](../rules_and_reqs/rendering/render_products/capability-render_products.md)

| Requirement | Requirement Doc |
|-------------|-----------------|
| `RP.001` | [RP.001](../rules_and_reqs/rendering/render_products/requirements/render-product-camera.md) |
| `RP.002` | [RP.002](../rules_and_reqs/rendering/render_products/requirements/render-product-ordered-vars.md) |
| `RP.003` | [RP.003](../rules_and_reqs/rendering/render_products/requirements/render-var-source-name.md) |
| `RP.004` | [RP.004](../rules_and_reqs/rendering/render_products/requirements/semantic-aov-compression.md) |
| `RP.005` | [RP.005](../rules_and_reqs/rendering/render_products/requirements/compression-type-valid.md) |
| `RP.006` | [RP.006](../rules_and_reqs/rendering/render_products/requirements/generic-model-output-compression.md) |

</details>

## Pipelines

Source file type:

- `.usd`, `.usda`, `.usdc`

Validation or runtime pipeline:

- `simready-validate` verifies FET035_RenderProducts.RTX requirements at asset authoring time.
- `simready-evaluate --features FET035_RenderProducts.RTX` runs Replicator-based AOV output verification in Isaac Sim.

## Samples

- [sample_content/common_assets/sensors/render_products/RenderProductsCheckerPass.usda](../../../../../../../sample_content/common_assets/sensors/render_products/RenderProductsCheckerPass.usda)
- [sample_content/common_assets/sensors/render_products/SemanticAovCompressionCheckerPass.usda](../../../../../../../sample_content/common_assets/sensors/render_products/SemanticAovCompressionCheckerPass.usda)
- [sample_content/common_assets/sensors/render_products/GenericModelOutputCompressionCheckerWarn.usda](../../../../../../../sample_content/common_assets/sensors/render_products/GenericModelOutputCompressionCheckerWarn.usda)
- [sample_content/common_assets/sensors_fails/render_products/RenderProductsCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/render_products/RenderProductsCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/render_products/SemanticAovCompressionCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/render_products/SemanticAovCompressionCheckerFail.usda)
- [sample_content/common_assets/sensors_fails/render_products/CompressionTypeCheckerFail.usda](../../../../../../../sample_content/common_assets/sensors_fails/render_products/CompressionTypeCheckerFail.usda)

## Evaluates

- `render_product_output` — verifies structural RenderProduct wiring and that each annotator returns non-empty output via Replicator.
- `semantic_aov_output` — verifies BLOSC compression is authored and semantic annotators return non-empty arrays.

## Adapters

- `_fix_compression` (RP.004 Suggestion) — sets `srtx:compression:type = "blosc"` on semantic AOV RenderVars.
