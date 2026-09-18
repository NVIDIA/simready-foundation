# SimReady Isaac Asset Transformer

This package is a standalone, Kit-free port of the Isaac asset transformer
framework and its complete production rule catalog. Both the prop and robot
composition paths are now used in production by
`asset_handler_modules/physx_to_isaacsim`: the
`FET_001_STANDARD@1.0.1` -> `FET_100_ISAAC@0.4.0` adapter runs the
`simready_physx_to_isaac_prop` transform, and the
`FET_001_STANDARD@1.0.1` -> `FET_101_ISAAC@0.1.0` adapter runs the
`simready_physx_to_isaac_robot` transform. The legacy Kit-extension paths remain
for the older `FET_100_ISAAC@0.1.0` / `FET100_BASE_ISAACSIM` outputs.

The first supported demonstration converts a SimReady prop into a clean,
layered Isaac package. The robot path runs the bundled
`simready_physx_to_isaac_robot` transform; its `RobotSchemaRule` uses the Isaac
schema when installed and otherwise falls back to a Kit-free path that authors
`IsaacRobotAPI` and the robot link/joint relationships directly.

## Install

From this directory:

```bash
python -m pip install -e ".[usd,test]"
```

The prop path needs Pixar USD and NumPy. Robot-schema, mesh-conversion, and
URDF/MuJoCo conversion rules additionally need:

```bash
python -m pip install -e ".[full]"
```

Rules with unavailable optional dependencies are skipped during discovery.
Selecting a profile that names a skipped rule produces a focused missing-rule
error; unrelated profiles continue to work.

## Run the prop demo

From the repository root:

```bash
PYTHONPATH=nv_core/cip_specs/isaac_asset_transformer/src \
python -m simready.asset_transformer.cli \
  sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd \
  _build/transform_demo/obs_electricians_large_tool_box_a01/simready_isaac \
  --profile simready_physx_to_isaac_prop
```

The command refuses to replace an existing output unless `--overwrite` is
passed. It writes `transform_report.json` beside the generated interface layer.

## Public API

```python
from simready.asset_transformer import load_profile, transform_package

profile = load_profile("simready_physx_to_isaac_prop")
report = transform_package(
    "path/to/asset.usd",
    "path/to/new/package",
    profile=profile,
    interface_asset_name="asset.usda",
)
```

Bundled profile transforms:

- `simready_physx_to_isaac_robot`: robot-oriented PhysX-to-Isaac transform.
- `simready_physx_to_isaac_prop`: prop-specific PhysX-to-Isaac transform.

## Documentation

- [Architecture and profiles](docs/architecture.md)
- [Toolbox sample and executive review](docs/toolbox_prop_demo.md)

## Current integration boundary

`nv_core/cip_specs/asset_handler_modules/physx_to_isaacsim/__init__.py` uses this
package for both standalone composition paths. It registers a
`FET_001_STANDARD@1.0.1` -> `FET_100_ISAAC@0.4.0` adapter that runs the
`simready_physx_to_isaac_prop` transform and a
`FET_001_STANDARD@1.0.1` -> `FET_101_ISAAC@0.1.0` adapter that runs the
`simready_physx_to_isaac_robot` transform, both through
`simready.asset_transformer`; the output package is then reintegrated into the
CIP output stage via the shared `physx_to_isaacsim/promotion.py` helper. The
adapter still owns the CIP decorators and output-stage promotion, and stamps
`kind = component` on the composed interface for `ISA.001`. The legacy
Kit-extension adapters (`FET_100_ISAAC@0.1.0`, `FET100_BASE_ISAACSIM`) remain on
the Kit backend.
