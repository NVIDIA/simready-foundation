# Asset-Optimization

`Asset-Optimization@1.1.0` checks a USD asset for four structural optimization
opportunities. Version `1.0.0` selects the first three and remains unchanged.
The Isaac tier owns this profile. It applies to props, robots and other assets
independently of their broader conformance profiles.

## Profile definition

```toml
[Asset-Optimization]
"1.1.0" = {capabilities = [
    {selector = "CAP102_RigidBodyCollapse.Isaac.0-1-0"},
    {selector = "CAP103_VisualMeshMerge.Isaac.0-1-0"},
    {selector = "CAP104_RenderCollisionSeparation.Isaac.0-1-0"},
    {selector = "CAP105_MaterialXRemoval.Isaac.0-1-0"},
]}
```

All four capabilities are required and have no dependencies.

| Capability | Pass condition | Repair |
| --- | --- | --- |
| [Rigid-Body Collapse](../capabilities/CAP102_RigidBodyCollapse.Isaac.md) | No eligible fixed-joint body pair remains (`OPT.001`). | Collapse eligible bodies and preserve aggregate dynamics. |
| [Visual Mesh Merge](../capabilities/CAP103_VisualMeshMerge.Isaac.md) | Each body has at most one eligible visual mesh (`OPT.002`). | Merge compatible visual meshes. |
| [Render-Collision Separation](../capabilities/CAP104_RenderCollisionSeparation.Isaac.md) | Render-only prims have no inactive collision schemas (`OPT.003`). | Remove the inactive schema stack. |
| [MaterialX Removal](../capabilities/CAP105_MaterialXRemoval.Isaac.md) | Materials have no connected MaterialX outputs (`OPT.004`). | Keep or derive a USD Preview Surface, then remove MaterialX shaders. |

## Workflow

1. Open the asset with its intended payloads loaded and variant selections
   composed. The stage must have a valid default prim.
2. Validate the asset:
   `simready-validate --profile Asset-Optimization --version 1.1.0 asset.usd`.
3. If all checks pass, no adapter is needed. A capability with no applicable
   content passes.
4. For a failed check, run its adapter on a staged copy that preserves the
   asset's dependencies.
5. Save, reopen, and rerun validation. Report adapter blockers separately from
   validation failures.

The validator checks only the submitted asset and the opportunities listed above.

## Adapters

The installed `simready.feature_adapters` provider declares one adapter per CAP
target. Derive selects them by capability, including when no source profile is
supplied. The registered source is
`FET003_RigidBody.0-2-0` for physics and mesh adapters and
`FET006_Materials.Openpbr.0-2-0` for MaterialX removal. These are adapter endpoints,
not validation dependencies. Each callback checks its repair preconditions and
can also be called independently.

| Order | Adapter | Output capability |
| --- | --- | --- |
| 1 | `fixed_joint_rigid_body_merge` | `CAP102_RigidBodyCollapse.Isaac.0-1-0` |
| 2 | `remove_inactive_render_collision_schemas` | `CAP104_RenderCollisionSeparation.Isaac.0-1-0` |
| 3 | `rigid_body_visual_mesh_merge` | `CAP103_VisualMeshMerge.Isaac.0-1-0` |
| 4 | `remove_materialx_shaders` | `CAP105_MaterialXRemoval.Isaac.0-1-0` |

Collapse and cleanup can expose additional visual meshes to merge. Run the
complete sequence when deriving the full profile. If a repair cannot preserve
the required data, retain the source and report the reason.

## Evidence

Static validation determines this profile's result. Adapter tests compare input
and output mass properties, geometry, transforms, materials, and relationships.
New material previews approximate advanced shading. Runtime performance and
simulator shape counts require separate measurements.

Validate broader contracts such as `Robotics-Prop` or `Robot-Body` separately
when requested; this profile does not add their requirements.
