# Toolbox Prop Demo and Executive Review

## Executive summary

The demo runs the public, Kit-free `isaacsim.asset.transformer` framework as a
normal Python module. A thin `simready.asset_transformer` integration provides
the prop profile and SimReady-specific rules, avoiding robot side effects while
producing runtime physics variants matching the authored toolbox contract.

The production prop feature adapter consumes this integration through the
`FET001_MinimalPlaceableVisual.1-0-1` -> `CAP100_IsaacComposition.Isaac.0-4-0` path in
`nv_core/tiers/simready_foundation_tier_core/tools/asset_handler_modules/physx_to_isaacsim`.

Run the demo with Python 3.12 after
`pip install "simready-foundation-tier-core[isaac]"`.
This optional extra installs the public
`isaacsim-asset-isolated==6.2.0.1` and
`isaacsim-robot-schema==6.2.0.0` distributions from PyPI.

## Sample

Input:

```text
sample_content/common_assets/props_general/
  obs_electricians_large_tool_box_a01/simready_usd/
    sm_obs_electricians_large_tool_box_a01_01.usd
    .thumbs/256x256/sm_obs_electricians_large_tool_box_a01_01.usd*.png
    payloads/{base,instances,instances_physx,instances_newton,instances_mujoco,materials}.usda
    runnables/physics/{physx,newton,mujoco}.usd
```

The source is a five-link articulated prop with four revolute joints, grasp
guide data, semantic labels, visual and physics materials, and three runtime
variant sets. It is not a robot.

The shipped sample is already in composed form: its runnables reference
`payloads/instances_<runtime>.usda`. `RuntimeInstanceRoutingRule` rebuilds those
runtime instance layers against the regenerated `instances.usda`. Runtime
references on enclosing objects are mapped to the generated child mesh instances;
object properties remain on their original prims. Re-running the transform on
composed input yields the same output contract. The source may
be read-only; the generated package is always owner-writable.

## Command

```bash
python3.12 -m simready.asset_transformer.cli \
  sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd \
  _build/transform_demo/obs_electricians_large_tool_box_a01/simready_isaac \
  --profile simready_physx_to_isaac_prop
```

Use `--overwrite` only to replace that generated demo directory. Without it, an
existing output is left untouched and the CLI exits with status 2 and a
one-line error. Existing `sample_content/**/simready_isaac` trees are never
used as output.

## Layout change

Before:

```text
root USD
  inline geometry, materials, neutral physics, joints, grasp, semantics
  PhysX Enabled -> runnables/physics/physx.usd
  Newton Enabled -> runnables/physics/newton.usd
  MuJoCo Enabled -> runnables/physics/mujoco.usd
```

After:

```text
interface USDA
  reference -> payloads/base.usda
  PhysX {Enabled -> runnables/physics/physx.usd, Disabled -> empty}
  Newton {Enabled -> runnables/physics/newton.usd, Disabled -> empty}
  MuJoCo {Enabled -> runnables/physics/mujoco.usd, Disabled -> empty}

payloads/base.usda
  sublayer -> Physics/physics.usda
  references -> instances.usda -> geometries.usd
  material routing -> materials.usda and Textures/

runnables/physics/<runtime>.usd
  swaps instance wrapper reference -> instances_<runtime>.usda
  runtime prototype mesh carries solver APIs and collision approximation
```

## Differences from the old robot-oriented transform

- No `robot.usda`.
- No `IsaacRobotAPI`, `IsaacLinkAPI`, robot link list, or robot joint list.
- No aggregate `Physics` interface variant.
- No `none` runtime variants.
- No `/Render`, `/OmniverseKit_*`, or asset-level `/PhysicsScene`.
- Neutral physics is always present; runtime overlays remain selectable.
- Physics material bindings resolve after geometry instancing.
- Solver mesh opinions are authored inside runtime-specific instance
  prototypes instead of being ignored on instance-proxy paths.

## Demo evidence

The generated package is at:

```text
_build/transform_demo/obs_electricians_large_tool_box_a01/simready_isaac/
```

Observed results:

- Every profile rule reported success in `transform_report.json`.
- Interface root prims: `RootNode` only.
- Interface variant sets: `PhysX`, `Newton`, `MuJoCo`.
- Defaults: all three runtimes are `Disabled`.
- Enabled payloads exist under `runnables/physics/`; Disabled variants are empty.
- Runtime instance layers exist for PhysX, Newton, and MuJoCo, and every
  runnable reference resolves inside the package.
- Source thumbnails are copied to `.thumbs/<size>/<interface>.usda*.png`.
- `payloads/base.usda` keeps a package-relative `assetInfo:identifier`.
- The composed stage retains `/RootNode/Joints/joint_lid_joint_01`.
- The composed stage retains
  `/RootNode/Geometry/box_obj_01/grasp_identifier`.
- No composed prim has `IsaacRobotAPI`.
- The box mesh resolves its bound physics material through
  `UsdShade.MaterialBindingAPI`.
- The actual composed instance-proxy meshes resolve `physics:approximation` as
  `sdf` for PhysX, `none` for Newton, and `convexHull` for MuJoCo.

## Validation and tests

The pytest suite verifies:

- Robot and prop profile contracts.
- Public framework and normal-rule registration plus SimReady-rule discovery.
- Version- and signature-guarded patches for the remaining upstream gaps.
- Upstream joint-state and UDIM material behavior the old patches provided.
- Two independent toolbox transforms produce the same interface structure.
- Runtime variants, prop cleanup, multibody/grasp preservation, absence of
  robot APIs, and physics-material resolution.
- Runtime switching is tested on both direct-mesh and merged-parent instance
  layouts, including each composed solver approximation.
- Re-transforming a composed, read-only package rebuilds the runtime instance
  layers, keeps the thumbnail, and leaves only package-relative asset paths.
- RV-shaped robot sources keep activation descriptors that name existing
  variant options.
- The CLI refuses an existing output without a traceback.

Run:

```bash
python -m pytest nv_core/tiers/simready_foundation_tier_core/tools/isaac_asset_transformer/tests -q
```

## Known limitations and review risks

1. Plain USD reports `OmniPBR.mdl` as unresolved because it is a runtime built-in
   MDL identifier. A local copy is retained under `source_assets/`, matching the
   prior transformer output behavior.
2. The manager can emit transient warnings while opening its initial relocated
   working copy before `FlattenRule` selects disabled runtime variants. The
   final interface paths resolve to the generated runtime payloads.
3. The production `physx_to_isaacsim` adapter uses the public framework through
   the thin SimReady package for the prop
   path. Its output promotion and cleanup logic is factored into
   `physx_to_isaacsim/promotion.py` and unit-tested in
   `tests/test_isaac_prop_adapter_promotion.py`; end-to-end promotion inside a
   live CIP/Kit runtime still needs environment-specific verification.

4. Geometry, material, and flatten fixes are temporary monkeypatches guarded by
   the exact public wheel version and method signatures. Profiles preserve the
   public rule FQCNs; remove the patches after an upstream isolated wheel
   includes the fixes.
