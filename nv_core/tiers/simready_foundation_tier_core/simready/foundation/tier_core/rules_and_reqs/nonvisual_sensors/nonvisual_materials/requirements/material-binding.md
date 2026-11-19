# material-binding

| Code     | NVM.004 |
|----------|---------|
| Validator|  |
| Compatibility | {compatibility}`rtx`  |
| Tags     | {tag}`correctness` |

## Summary

Attributes must be on bound materials

## Description

Non-visual material attributes must be authored on materials that are actually bound to geometry prims, not on unbound or unreferenced materials.

## Why is it required?

- Ensures non-visual attributes are applied where they're needed
- Prevents orphaned attributes on unused materials
- Maintains consistency between visual and non-visual material properties

## Examples

```usd
# Invalid: Attributes on unbound material
def Material "UnboundMaterial" {
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
    # This material is not bound to any geometry
}

def Mesh "UnlabeledMesh" {
    # No material binding - will fail validation
}

# Valid: Attributes on bound material
def Material "BoundMaterial" {
    token outputs:surface.connect = </BoundMaterial/Surface.outputs:surface>
    token omni:simready:nonvisual:base = "steel"
    token omni:simready:nonvisual:coating = "paint"
    token[] omni:simready:nonvisual:attributes = ["emissive"]
}

def Mesh "LabeledMesh" {
    rel material:binding = </BoundMaterial>
}
```

## How to comply

Ensure that non-visual material attributes are only authored on materials that are bound to geometry prims through material binding relationships.

## For More Information

- [Non-Visual Materials Capability](../capability-nonvisual_materials.md)
- [Material Base Requirement](material-base.md)
- [Material Coating Requirement](material-coating.md)
