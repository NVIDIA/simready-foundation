# isaac-composition

| Code     | ISA.001 |
|----------|---------|
| Validator| |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The asset must be composed correctly for Isaac Sim using a structured payload and reference system with proper file organization.

## Description

Isaac Sim composition defines a structure that uses USD composition patterns. This involves organizing assets into separate payload files for meshes, physics, and configuration data, with a main scene that references and loads these components appropriately.

The composition structure separates visual geometry, physics data, and materials into distinct USD files connected through references and payloads. This organization requires assets to be split into the described layers for loading and assembly in Isaac Sim environments.

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
# Main asset file (myasset.usd)
def Xform "MyAsset" (
    kind = "component"
    prepend references = @./payloads/myasset_base.usd@
    prepend payload = @./payloads/myasset_physics.usd@
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

1. **Main Asset Structure**: The main USD file must have a default prim with `kind = "component"` and use references and payloads to organize content
2. **Payload Organization**: Create separate payload files in a `payloads/` directory:
   - `{asset_name}_meshes.usd`: Contains geometry, materials (as "Looks"), and visual hierarchy
   - `{asset_name}_base.usd`: References the meshes file
   - `{asset_name}_physics.usd`: Contains physics materials, joints, and physics attributes
3. **File Structure**: Organize the asset with the following directory structure:
   .. code-block:: text

      myasset.usd                    # Main composition file
      payloads/
        ├── myasset_meshes.usd       # Geometry and materials
        ├── myasset_base.usd         # Base reference layer
        └── myasset_physics.usd      # Physics data
      configuration/
        └── myasset_physics.usd      # Configuration layer combining base and physics
4. **Material Organization**: Materials must be organized under a "Looks" scope in the meshes payload
5. **Geometry Hierarchy**: 
   - Raw meshes stored in invisible "Meshes" scope
   - Visual hierarchy created in invisible "Visuals" scope with references to raw meshes
   - Main asset hierarchy references visual hierarchy with proper naming convention (_obj → _trans)
6. **Physics Separation**: Physics schemas and attributes must be applied in the physics payload file, not mixed with geometry
7. **Reference Paths**: Use relative paths for all references and payloads to maintain portability
8. **Default Prim**: Each USD file must have a properly set default prim
9. **Metadata**: Set appropriate stage metadata including `upAxis = "Z"` and `metersPerUnit = 1.0`

## For More Information

- [USD Composition Documentation](https://openusd.org/dev/api/usd_page_front.html#usd_composition)
- [USD References and Payloads](https://openusd.org/dev/api/usd_page_front.html#usd_references_and_payloads)
- [USD Kind and Model Hierarchy](https://openusd.org/dev/api/usd_page_front.html#usd_kind_and_model_hierarchy)
- [Isaac Sim Asset Structure Best Practices](https://docs.omniverse.nvidia.com/isaacsim/latest/features/scene_generation/assets/usd_assets_best_practices.html)