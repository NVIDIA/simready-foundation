# SimReady Isaac Asset Transformer

This package is the thin SimReady integration for the public, Kit-free
`isaacsim.asset.transformer` framework. The public
`isaacsim-asset-isolated==6.2.0.1` distribution supplies the manager, models,
registry, and normal production rules. `simready.asset_transformer` retains the
SimReady profiles and CLI, SimReady-specific rules, and three small guarded
temporary patches (see `src/simready/asset_transformer/patches/UPSTREAM.md`). Both the prop and robot
composition paths are used by
`asset_handler_modules/physx_to_isaacsim`: the
`FET001_MinimalPlaceableVisual.1-0-1` -> `CAP100_IsaacComposition.Isaac.0-4-0` adapter runs the
`simready_physx_to_isaac_prop` transform, and the
`FET001_MinimalPlaceableVisual.1-0-1` -> `CAP101_RobotComposition.Isaac.0-1-0` adapter runs the
`simready_physx_to_isaac_robot` transform. Deprecated Kit-extension adapter
paths are no longer registered.

The prop demonstration converts a SimReady prop into a clean, layered Isaac
package. The robot path runs the bundled `simready_physx_to_isaac_robot`
profile with the public transformer and robot-schema packages.

## Install

Python 3.12 is required. The optional tier-core `[isaac]` extra installs
`isaacsim-asset-isolated==6.2.0.1` and
`isaacsim-robot-schema==6.2.0.0`, both available on PyPI and installed
with the extra:

```bash
python3.12 -m pip install \
  -e "nv_core/tiers/simready_foundation_tier_core[isaac,usd,test]"
```

The tier wheel includes the thin `simready.asset_transformer` integration; it
does not include a standalone fork of the public framework or normal rule
catalog.

## Run the prop demo

From the repository root:

```bash
python3.12 -m simready.asset_transformer.cli \
  sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd \
  _build/transform_demo/obs_electricians_large_tool_box_a01/simready_isaac \
  --profile simready_physx_to_isaac_prop
```

The command refuses to replace an existing output unless `--overwrite` is
passed, reporting a concise usage error. Transformation runs in a temporary
directory and publishes the package only when all rules succeed and composition checks pass; a failed run
preserves any existing output and writes `<output>.failed-transform.json`
beside it (or to `--report`). Successful runs write `transform_report.json`
beside the generated interface layer. Source files may be read-only: copied
dependencies are made writable, and source files and permissions stay intact.

Existing `.thumbs/256x256/<source USD filename>.png` thumbnails are copied to
match the generated interface filename. Runtime instance layers are rebuilt
when transforming an already composed source.

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

`nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/physx_to_isaacsim/__init__.py` uses the
public framework through this integration for both composition paths. It registers a
`FET001_MinimalPlaceableVisual.1-0-1` -> `CAP100_IsaacComposition.Isaac.0-4-0` adapter that runs the
`simready_physx_to_isaac_prop` transform and a
`FET001_MinimalPlaceableVisual.1-0-1` -> `CAP101_RobotComposition.Isaac.0-1-0` adapter that runs the
`simready_physx_to_isaac_robot` transform. The output package is then reintegrated into the
CIP output stage via the shared `physx_to_isaacsim/promotion.py` helper. The
adapter uses the tier's Kit-free decorator, owns output-stage promotion, and
stamps `kind = component` on the composed interface for `ISA.001`. Installed
consumers discover it through the `simready.feature_adapters` entry-point group.

Before registering rules, the integration applies version- and
signature-guarded patches to the public geometry rule, the variant-routing copy
helper, and the manager's staged-package publish step. Profiles continue to reference the public
`isaacsim.asset.transformer.rules.*` fully qualified class names. These patches
are temporary and are removed after an upstream isolated wheel includes the
fixes.
