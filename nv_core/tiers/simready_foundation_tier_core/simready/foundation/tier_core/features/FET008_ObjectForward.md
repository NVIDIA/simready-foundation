# Object Forward

| Field | Contract |
|---|---|
| ID | `FET008_ObjectForward.0-1-0` |
| Runtime promise | The loaded asset exposes local facing and scene tooling consumes it for a front-side camera |
| Dependency | `FET001_MinimalPlaceableVisual.1-0-1` |
| Sole requirement | AF.001 |
| Validator | AssetFrameChecker |
| Adapter | `skill:simready-foundation-conform-fet-008-object-forward` |
| Runtime tests | `object_forward_contract`, `object_forward_camera_response` |

The feature card's FET008 / FET_008_STANDARD label is implemented with the
current Foundations 2 identity above. Native upAxis owns stage up. The custom
attribute is a uniform vector3f on the asset root or an explicit component;
namespace inheritance is deliberately absent in this initial contract.

Use `asset_frame.read_forward_direction` and `world_forward_direction` from
the Core tier. Object Forward owns AF.001 directly, without a separate capability.
AssetFrameChecker validates authored root/component directions. The runtime query
checks that the same values remain available on the loaded, composed stage.
The camera-response test exercises `asset_frame.facing_camera_transform` and
checks composed camera positions and viewing directions after engine updates.
Both tests belong to FET008; AF.001 remains its sole validator requirement.
See [runtime evidence](../runtime_tests/docs/fet008-object-forward.md).

The existing toaster, dishwand and joystick in
`sample_content/common_assets/props_general/` demonstrate Object Forward.
Each authors local `(1, 0, 0)` on its default prim. The toaster faces its control
panel; the dishwand faces from the handle toward its working head. The
rotationally symmetric joystick uses the author-selected operator direction.
Semantic front requires author review. Static validation cannot infer it.

Robotics-Prop 5.0.0 requires Object Forward. Robot-Body 3.1.0 includes it
optionally for bodies with a semantic front. Earlier profile versions remain
unchanged. GR.002 retains its distinct per-site approach meaning. There is no
automatic adapter that guesses forward from geometry; the conform skill
requires an explicit vector or visual evidence and writes a staged output.
