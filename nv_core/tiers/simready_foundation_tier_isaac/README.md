# SimReady Foundation Isaac optimization tier

`simready-foundation-tier-isaac` provides static optimization checks and adapters
for USD assets. It owns four capabilities in the Isaac tier and depends on Core
for the shared catalog and validation infrastructure.

## Contract

`Asset-Optimization@1.1.0` selects the capabilities below. Version `1.0.0`
selects the first three and remains unchanged.

| Capability | Requirement | Adapter |
| --- | --- | --- |
| `CAP102_RigidBodyCollapse.Isaac.0-1-0` | `OPT.001`: no eligible fixed-joint body pair | `fixed_joint_rigid_body_merge` |
| `CAP103_VisualMeshMerge.Isaac.0-1-0` | `OPT.002`: no multiple eligible visual meshes per rigid body | `rigid_body_visual_mesh_merge` |
| `CAP104_RenderCollisionSeparation.Isaac.0-1-0` | `OPT.003`: no inactive collision schemas on render-only prims | `remove_inactive_render_collision_schemas` |
| `CAP105_MaterialXRemoval.Isaac.0-1-0` | `OPT.004`: no connected MaterialX render contexts | `remove_materialx_shaders` |

Each check reads one composed USD asset with a default prim. An asset with no
applicable content passes. No source asset or optimization stamp is required.

## Validate and optimize

Install compatible Core and Isaac wheels, then run:

```bash
simready-validate --profile Asset-Optimization --version 1.1.0 path/to/asset.usd
```

If validation passes, keep the asset as it is. If an `OPT.*` check fails, run
the corresponding adapter on a staged copy and validate the saved output again.

The four callbacks can also be called independently from
`simready.foundation.tier_isaac.asset_handler_modules.isaac_optimization`.
Each takes an input stage and an output stage containing a writable copy of the
input composition. Preserve referenced dependencies when staging the output.

For the complete profile, run collapse, collision-schema cleanup, visual merge,
then MaterialX removal. If an adapter cannot preserve the required data, report
the blocker and retain the source. Validate other requested profiles separately.

## Installed discovery

The wheel advertises:

- `usd_validation_nvidia`: validators and generated requirement enums.
- `simready.tier`: capability, profile, and rule locations.
- `simready.feature_adapters`: four callbacks, each targeting one exact CAP ID
  selected by `Asset-Optimization@1.1.0`.

Derive selects adapters by their exact output capabilities, including when no
source profile is supplied. Each adapter checks its own repair preconditions.
See the [profile](simready/foundation/tier_isaac/profiles/asset-optimization.md)
for adapter endpoints and execution order.

## Build and test

From the repository root:

```bash
./repo.sh build_tiers
python -m pytest nv_core/tiers/simready_foundation_tier_isaac/tests -q
```

Run tests with the built Core and Isaac wheels installed. Visual merging requires
`usd-optimize>=1.4.0`, sharing the host's OpenUSD runtime. The tested standalone
configuration is Windows / Python 3.12 with `usd-optimize==1.4.0`,
`usd-exchange==3.0.1`, Derive `2026.10.0rc0`, and Validate `2026.10.0rc1`.
Exchange supplies USD 26.08; install the base validation/derivation packages
without their USD extras and keep `usd-core` out of that environment.

Visual merging uses the `usd_optimize.core` `merge` operation on selected meshes and
keeps collision geometry separate. Version 1.4 handles geometric primvar
transforms and face materials; the adapter preserves the remaining USD data.

Tests cover the four-adapter chain, both profile versions, source preservation,
physics, geometry, materials, and validation after repair. Static validation
does not measure simulation speed, rendering cost, or load time.

### Preservation checks

Collapse and visual-merge tests compare physics, joints, collision behavior,
geometry, materials, and custom mesh data across different hierarchies.

Automatic optimization follows these rules:

- Preserve joints and which parts collide with each other.
- Combine only bodies with compatible physics settings and motion.
- Refuse collapse when moving bodies use local-space velocities or an additional
  enabled joint would connect a body to itself.
- Collapse instanced bodies under an editable compound body while keeping their
  geometry instanced.
- Reject inputs the operation cannot preserve, including unsupported animation
  or skinning.
- Calculate mass, center of mass, and inertia from supported geometry or use
  complete authored values; never guess.
- Keep collision settings that change over time.
- Restore the staged output if collapse or mesh merging fails.
- Preserve mesh data and face materials across references and sublayers.
- Merge meshes only when their material bindings and unbound faces can be
  preserved. Purpose-specific bindings need a separate authoring workflow.

"Static" means no authored animation; the optimized object can still move during
simulation. These safeguards do not change the existing `OPT.001`–`OPT.003`
validation rules.

### MaterialX removal

The adapter removes `mtlx` / `MTLX` outputs and their private shader networks,
preserves existing USD Preview Surface and MDL shading, and keeps material
bindings and shared inputs. If needed, it creates a preview from OpenPBR or
MaterialX Standard Surface values and supported textures. Advanced lobes such as
transmission and subsurface scattering are approximated by that preview.
Unsupported procedural graphs require an authored or baked preview first.

The network layouts follow the [USD Exchange SDK](https://docs.omniverse.nvidia.com/usd/code-docs/usd-exchange-sdk/3.0.0/docs/authoring-usd.html)
and [NVIDIA SimReady Materials](https://github.com/NVIDIA-Omniverse/PhysicalAI-SimReady-Materials).
