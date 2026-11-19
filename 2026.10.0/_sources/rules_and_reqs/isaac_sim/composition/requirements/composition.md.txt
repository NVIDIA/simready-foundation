# isaac-composition

| Code     | ISA.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset must be composed correctly for Isaac Sim using one of the supported
layer layouts and a reference or payload arc to its base layer.

## Description

Isaac Sim composition uses USD composition arcs to separate geometry, physics,
instances, and materials. Layers may use any USD layer encoding (`.usd`,
`.usda`, or `.usdc`) and may be delivered loose or inside a `.usdz` package.
Validation inspects authored references, payloads, and sublayers without forcing
payloads to load.

Two complete layouts are supported:

- Legacy prop: `<stem>_base`, `<stem>_meshes`, and `<stem>_physics`, all using
  the same stem.
- Performance robot: `base`, `geometries`, `instances`, and `materials`.

The default prim in the entry layer must author either a reference or payload
arc to the corresponding base layer.

## Examples

```usd
# Invalid: Simple asset without proper Isaac Sim composition structure
def Xform "MyAsset" (
    kind = "component"
) {
    # All geometry, materials, and physics mixed together
    # No payload structure for efficient loading
    def Mesh "mesh_01" {
        # geometry data...
    }
    def Material "material_01" {
        # material data...
    }
}

# Valid: Isaac Sim composition with proper payload structure
# Main asset file (myasset.usd, myasset.usda, or myasset.usdc)
def Xform "MyAsset" (
    kind = "component"
    prepend references = @./payloads/myasset_base.usd@
) {
    # Main scene composition with references and payloads
}

# Base payload file (payloads/myasset_base.usd)
def Xform "MyAsset" (
    prepend references = @./myasset_meshes.usd@
) {
    # References to mesh data
}

# Meshes payload file (payloads/myasset_meshes.usd)
def Xform "MyAsset" {
    def Scope "Looks" {
        # Materials organized under Looks
        def Material "material_01" {
            # Material definitions...
        }
    }
    
    def Scope "Meshes" (
        visibility = "invisible"
    ) {
        # Raw mesh data (invisible)
        def Mesh "mesh_obj_01" {
            # Geometry data without physics schemas
        }
    }
    
    def Scope "Visuals" (
        visibility = "invisible"
    ) {
        # Visual hierarchy with references
        def Xform "mesh_trans_01" {
            def Xform "mesh_obj_01" (
                prepend references = </Meshes/mesh_obj_01>
            ) {
            }
        }
    }
    
    # Main asset hierarchy with visual references
    def Xform "mesh_obj_01" {
        def Xform "mesh_trans_01" (
            prepend references = </Visuals/mesh_trans_01>
        ) {
        }
    }
}

# Physics payload file (payloads/myasset_physics.usd)
def Xform "MyAsset" {
    def Scope "PhysicsMaterials" {
        # Physics materials
    }
    
    def Scope "Joints" {
        # Joint definitions with corrected body paths
    }
    
    # Physics attributes applied to mesh hierarchy
    over "mesh_obj_01/mesh_trans_01/mesh_obj_01" {
        # Physics schemas and attributes applied here
        prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsRigidBodyAPI"]
        physics:approximation = "sdf"
    }
}
```

## How to comply

1. **Main Asset Structure**: The entry layer must have a default prim with
   `kind = "component"` and a reference or payload to the base layer.
2. **Choose one complete layout**:
   - Legacy prop: `{asset_name}_base`, `{asset_name}_meshes`, and
     `{asset_name}_physics`.
   - Performance robot: `base`, `geometries`, `instances`, and `materials`.
3. **Layer Encoding**: Each layer may use `.usd`, `.usda`, or `.usdc`; use the
   same logical names regardless of encoding. The complete hierarchy may also
   be packaged in USDZ.
4. **Example legacy file structure**:
   .. code-block:: text

      myasset.usd                    # Main composition file
      payloads/
        ├── myasset_meshes.usd       # Geometry and materials
        ├── myasset_base.usd         # Base reference layer
        └── myasset_physics.usd      # Physics data
5. **Material Organization**: Materials must be organized under a "Looks" scope in the meshes payload
6. **Geometry Hierarchy**:
   - Raw meshes stored in invisible "Meshes" scope
   - Visual hierarchy created in invisible "Visuals" scope with references to raw meshes
   - Main asset hierarchy references visual hierarchy with proper naming convention (_obj → _trans)
7. **Physics Separation**: Physics schemas and attributes must be applied in the physics layer, not mixed with geometry
8. **Reference Paths**: Use relative paths for all references and payloads to maintain portability
9. **Default Prim**: Each USD file must have a properly set default prim
10. **Metadata**: Set appropriate stage metadata including `upAxis = "Z"` and `metersPerUnit = 1.0`

## For More Information

- [USD Composition Documentation](https://openusd.org/dev/api/usd_page_front.html#usd_composition)
- [USD References and Payloads](https://openusd.org/dev/api/usd_page_front.html#usd_references_and_payloads)
- [USD Kind and Model Hierarchy](https://openusd.org/dev/api/usd_page_front.html#usd_kind_and_model_hierarchy)
- [Isaac Sim Asset Structure Best Practices](https://docs.omniverse.nvidia.com/isaacsim/latest/features/scene_generation/assets/usd_assets_best_practices.html)