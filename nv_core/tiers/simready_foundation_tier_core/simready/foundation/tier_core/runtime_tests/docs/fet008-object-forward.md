# FET008 Object Forward

## Overview

`FET008_ObjectForward.0-1-0` has `object_forward_contract` version
1.0.0 and `object_forward_camera_response` version 1.0.1 runtime tests.
They check that explicitly authored local facing survives composition and
that a front-side camera consumes it correctly in a loaded scene.

## What a Passing Family Means

The loaded root and authored components expose the source asset's directions.
Changing facing on temporary asset references changes the composed camera
position and viewing direction as expected. Semantic front requires author
review; the tests cannot infer it from geometry.

## Tests

:::{list-table}
:header-rows: 1
:widths: 30 45 25

* - Test
  - What It Checks
  - Validates
* - [object_forward_contract](fet008/object-forward-contract.md)
  - Queries root/component directions and compares locations and values with the source.
  - FET008 Object Forward
* - [object_forward_camera_response](fet008/object-forward-camera-response.md)
  - Measures front-camera positions and viewing directions after engine updates.
  - FET008 Object Forward
:::

## Relationship to the Feature

Both tests provide evidence for
[Object Forward](../../features/FET008_ObjectForward.md).
AF.001 remains the sole requirement, validated by AssetFrameChecker.
The tests are independent of the physics solver. Local unit tests do not
claim Kit/Isaac runtime qualification.

```{toctree}
:maxdepth: 1
:hidden:

object_forward_contract <fet008/object-forward-contract>
object_forward_camera_response <fet008/object-forward-camera-response>
```
