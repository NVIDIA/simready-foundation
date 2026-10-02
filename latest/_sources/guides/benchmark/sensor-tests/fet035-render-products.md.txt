# FET035 Render Products

Cameras and LiDARs produce synthetic data output via correctly wired RenderProducts.

## Overview

This family loads a scene asset into Isaac Sim Replicator, triggers one
synthetic data generation (SDG) frame, and confirms that each camera and
OmniLidar prim produces output files via its linked RenderProduct. It also
verifies that semantic AOV outputs are written in BLOSC-compressed format as
required by the static validation rules.

A conforming asset must have already passed static validation (RP.001–RP.004)
before these runtime tests are meaningful. An asset that fails static
validation will be reported as VALIDATION_FAILED and skipped.

**Note:** These tests require an asset that contains at least one Camera or
OmniLidar prim wired to a RenderProduct. A prop asset with no cameras or
render products will be reported as not applicable and skipped.

## What a Passing Family Means

A reviewer, PM, or OEM can trust that the asset's render pipeline is fully
wired — every camera and LiDAR has a RenderProduct, every RenderProduct
declares its AOV outputs, and semantic AOVs use BLOSC compression — so that
the asset can be dropped into an Isaac Sim Replicator SDG pipeline and produce
annotated outputs without manual scene reconfiguration.

## Tests

:::{list-table}
:header-rows: 1
:widths: 25 50 25

* - Test
  - What It Checks
  - Validates
* - [render_product_output](fet035/render-product-output.md)
  - Each RenderProduct produces at least one output file per SDG frame, with non-zero file size.
  - FET_035_RTX
* - [semantic_aov_output](fet035/semantic-aov-output.md)
  - Semantic AOV RenderVars produce BLOSC-compressed EXR output files.
  - FET_035_RTX
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET_035_RTX Camera and Render Products](../../../features/FET_035_RTX-0.1.0.json).

```{toctree}
:maxdepth: 1
:hidden:

render_product_output <fet035/render-product-output>
semantic_aov_output <fet035/semantic-aov-output>
```
