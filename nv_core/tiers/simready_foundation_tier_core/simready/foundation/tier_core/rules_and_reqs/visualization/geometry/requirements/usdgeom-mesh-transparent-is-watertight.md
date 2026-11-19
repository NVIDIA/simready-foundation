# transparent-mesh-is-watertight

| Code     | VG.022 |
|----------|-----------|
| Validator|                                |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`correctness` |
| Version | 0.1.0      |

## Summary

Transparent physical bodies should be watertight to allow for simulation of light transmission and refraction.

## Description

Watertight meshes are essential for transparent materials to ensure accurate light simulation, including transmission, refraction, and caustics. A watertight mesh has no holes, gaps, or non-manifold edges that would allow light to pass through unintended areas or create visual artifacts.

Key characteristics of watertight transparent meshes:
- No holes or gaps in the surface
- All edges are shared by exactly two faces
- Consistent face normals
- No overlapping geometry
- Properly closed volume

## Why is it required?
- Accurate light transmission simulation
- Proper refraction calculations
- Realistic caustics and light effects
- Prevents light leakage through mesh gaps
- Ensures consistent transparency behavior
- Maintains visual quality in raytraced rendering

## Examples

### Material Transparency Detection

```usd
# Example 1: Glass material with transparency properties
def Material "GlassWindow" {
    def Shader "GlassShader" {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./glass_base.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "Glass_base"
        
        # Transparency indicators
        bool inputs:thin_walled = true
        float inputs:glass_ior = 1.491
        float inputs:cutout_opacity = 0.8
    }
}

# Example 2: SimPBR material with transmission enabled
def Material "TransparentPlastic" {
    def Shader "SimPBRShader" {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # Transparency indicators
        bool inputs:enable_transmission = true
        bool inputs:enable_opacity = true
        float inputs:alpha_constant = 0.7
        float inputs:opacity_ratio = 0.5
    }
}

# Example 3: Opaque material (no transparency)
def Material "OpaqueMetal" {
    def Shader "SimPBRShader" {
        uniform token info:implementationSource = "sourceAsset"
        uniform asset info:mdl:sourceAsset = @./SimPBR.mdl@
        uniform token info:mdl:sourceAsset:subIdentifier = "SimPBR"
        
        # No transparency indicators
        bool inputs:enable_transmission = false
        bool inputs:enable_opacity = false
        float inputs:alpha_constant = 1.0
        bool inputs:thin_walled = false
    }
}
```

### Mesh Topology Examples

```usd
# Invalid: Non-watertight transparent mesh with holes
def Mesh "TransparentCube" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4]  # Missing one face
    int[] faceVertexIndices = [0, 1, 2, 3, 4, 5, 6, 7, 0, 4, 7, 3, 1, 5, 6, 2, 0, 1, 5, 4]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), (0,0,1), (1,0,1), (1,1,1), (0,1,1)]
    # Missing top face: [3, 2, 6, 7]
    # This mesh has a hole and should not be used with transparent materials
}

# Valid: Watertight transparent mesh
def Mesh "TransparentCube" {
    int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]  # All 6 faces present
    int[] faceVertexIndices = [0, 1, 2, 3, 4, 5, 6, 7, 0, 4, 7, 3, 1, 5, 6, 2, 0, 1, 5, 4, 3, 2, 6, 7]
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0), (0,0,1), (1,0,1), (1,1,1), (0,1,1)]
    # All faces present - watertight
}
```


## How to comply
- Use mesh repair tools to fill holes and gaps
- Ensure all edges are shared by exactly two faces
- Check for and fix non-manifold geometry
- Verify consistent face normals
- Use boolean operations to create proper closed volumes
- Validate mesh topology before applying transparency
- Third-party mesh repair software (Blender, Maya, 3ds Max)

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)
- [Watertight Mesh Requirements](https://en.wikipedia.org/wiki/Watertight_mesh)
- [Light Transport in Transparent Materials](https://en.wikipedia.org/wiki/Light_transport_theory)