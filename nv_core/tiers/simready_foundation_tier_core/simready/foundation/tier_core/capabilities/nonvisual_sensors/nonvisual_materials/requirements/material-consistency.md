# material-consistency

| Code     | NVM.005 |
|----------|---------|
| Validator|  |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`correctness` |

## Summary

Properties must be consistent with visual materials

## Description

Non-visual material properties must be consistent with the visual material properties. For example, a material that appears metallic in visual rendering should have appropriate non-visual attributes that reflect its metallic nature.

## Why is it required?

- Ensures consistency between visual and non-visual representations
- Prevents conflicting material properties
- Maintains realistic material behavior across different sensor types

## Examples

```usd
# Invalid: Inconsistent material properties
def Material "InconsistentMaterial" {
    token outputs:surface.connect = </InconsistentMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "plastic"  # Claims to be plastic
    token omni:simready:nonvisual:coating = "none"
    token[] omni:simready:nonvisual:attributes = []
    
    def Shader "Surface" {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:metallic = 1.0  # But visually appears metallic
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
    }
}

# Valid: Consistent material properties
def Material "ConsistentMaterial" {
    token outputs:surface.connect = </ConsistentMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"  # Matches visual metallic appearance
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = []
    
    def Shader "Surface" {
        uniform token info:id = "UsdPreviewSurface"
        float inputs:metallic = 1.0
        color3f inputs:diffuseColor = (0.8, 0.8, 0.8)
    }
}
```

## How to comply

Ensure that non-visual material attributes accurately reflect the visual appearance and properties of the material. For example:
- Metallic-looking materials should use metal base types
- Transparent materials should use appropriate glass or clear material types
- Painted surfaces should specify appropriate coating attributes

## For More Information

- [Non-Visual Materials Capability](../capability-nonvisual_materials.md)
- [Material Base Requirement](material-base.md)
- [Material Coating Requirement](material-coating.md)
