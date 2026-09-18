# Toolbox Prop Demo and Executive Review

## Executive summary

The demo proves that the newest Isaac transformer implementation can be run as
a normal Python module, without loading Kit extensions, while retaining the
complete robot-capable rule source. A separate prop profile avoids the former
robot side effects and produces runtime physics variants matching the authored
toolbox contract.

The implementation was staged: the standalone package and demo were completed
first; the production prop feature adapter now consumes this package through the
`FET_001_STANDARD@1.0.1` -> `FET_100_ISAAC@0.4.0` path in
`nv_core/cip_specs/asset_handler_modules/physx_to_isaacsim`.

## Sample

Input:

```text
sample_content/common_assets/props_general/
  obs_electricians_large_tool_box_a01/simready_usd/
    sm_obs_electricians_large_tool_box_a01_01.usd
    runnables/physics/{physx,newton,mujoco}.usd
    materials/
    textures/
```

The source is a five-link articulated prop with four revolute joints, grasp
guide data, semantic labels, visual and physics materials, and three runtime
variant sets. It is not a robot.

## Command

```bash
PYTHONPATH=nv_core/cip_specs/isaac_asset_transformer/src \
python -m simready.asset_transformer.cli \
  sample_content/common_assets/props_general/obs_electricians_large_tool_box_a01/simready_usd/sm_obs_electricians_large_tool_box_a01_01.usd \
  _build/transform_demo/obs_electricians_large_tool_box_a01/simready_isaac \
  --profile simready_physx_to_isaac_prop
```

Use `--overwrite` only to replace that generated demo directory. Existing
`sample_content/**/simready_isaac` trees are never used as output.

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
  PhysX {Enabled, Disabled}
  Newton {Enabled, Disabled}
  MuJoCo {Enabled, Disabled}

payloads/base.usda
  sublayer -> Physics/physics.usda
  references -> instances.usda -> geometries.usd
  material routing -> materials.usda and Textures/

runtime Enabled payload
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
- Defaults: `PhysX=Enabled`, `Newton=Disabled`, `MuJoCo=Disabled`.
- Enabled and disabled payload layers exist for all three runtimes.
- Runtime instance layers exist for PhysX, Newton, and MuJoCo.
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
- Complete upstream production-rule source inventory.
- Kit-free dependency-light rule discovery.
- Two independent toolbox transforms produce the same interface structure.
- Runtime variants, prop cleanup, multibody/grasp preservation, absence of
  robot APIs, and physics-material resolution.
- Runtime switching is tested on both direct-mesh and merged-parent instance
  layouts, including each composed solver approximation.

Run:

```bash
python -m pytest nv_core/cip_specs/isaac_asset_transformer/tests -q
```

## Known limitations and review risks

1. Robot and solver-conversion rules require optional Isaac Python packages;
   they are ported but cannot execute in a USD-only environment.
2. Plain USD reports `OmniPBR.mdl` as unresolved because it is a runtime built-in
   MDL identifier. A local copy is retained under `source_assets/`, matching the
   prior transformer output behavior.
3. The manager can emit transient warnings while opening its initial relocated
   working copy before `FlattenRule` selects disabled runtime variants. The
   final interface paths resolve to the generated runtime payloads.
4. The production `physx_to_isaacsim` adapter now uses this package for the prop
   path. Its output promotion and cleanup logic is factored into
   `physx_to_isaacsim/promotion.py` and unit-tested in
   `tests/test_isaac_prop_adapter_promotion.py`; end-to-end promotion inside a
   live CIP/Kit runtime still needs environment-specific verification.

## Review decision requested

Approve the standalone package and `simready_physx_to_isaac_prop.json` contract
as the basis for replacing the Kit-extension dependency. Adapter integration
should be a follow-up change so rollback remains limited to the adapter import
and orchestration boundary.
