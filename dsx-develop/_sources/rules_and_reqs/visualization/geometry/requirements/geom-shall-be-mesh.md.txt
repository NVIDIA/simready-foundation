# geom-shall-be-mesh

| Code     | VG.MESH.001 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`essential` |

## Summary

All geometry shall be represented as non-subdivided mesh primitives using the UsdGeomMesh schema.

## Description

Geometric surfaces shall be encoded as meshes to ensure compatibility with standard rendering pipelines, collision detection systems, and simulation frameworks. Mesh geometry provides surface topology, vertex positions, and face connectivity that can be efficiently processed by rendering hardware and software algorithms.

Subdivision Meshes, Curves, point clouds, implicit surfaces, procedural geometry, and other non-mesh representations are not supported in the current specification.

## Examples

### Valid: Standard mesh geometry

```usd
#usda 1.0

def Mesh "ValidGeometry" {
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
    int[] faceVertexCounts = [4]
    int[] faceVertexIndices = [0, 1, 2, 3]
    normal3f[] primvars:normals = [(0, 0, 1)]
    uniform token primvars:normals:interpolation = "uniform"
}
```

### Valid: Triangulated mesh

```usd
#usda 1.0

def Mesh "TriangulatedMesh" {
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 2, 0, 2, 3]
    normal3f[] primvars:normals = [(0, 0, 1), (0, 0, 1)]
    uniform token primvars:normals:interpolation = "uniform"
}
```

### Invalid: Point cloud (not supported)

```usd
#usda 1.0

def Points "InvalidPointCloud" {
    point3f[] points = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
}
```

### Invalid: Implicit surface (not supported)

```usd
#usda 1.0

def Sphere "InvalidImplicit" {
    double radius = 1.0
}
```

## How to comply

- Set `subdivisionScheme` to "none"
- Convert all geometry to mesh representation before export
- Ensure proper triangulation or polygonization of curved surfaces
- Maintain appropriate mesh density for intended use case
- Validate mesh topology and connectivity
- Use appropriate interpolation methods for normals and other attributes
- Test mesh compatibility with target visualization systems

## For More Information

- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)

## Notes

**Future Technology Considerations:**

This requirement is subject to change as new geometry representation technologies emerge and mature. The following technologies may be considered for future adoption:

- **Point Clouds**: High-density point cloud representations may be supported for large-scale environmental data, LiDAR scans, or photogrammetry workflows
- **3D Gaussian Splatting (3DGS)**: Neural rendering techniques using 3D Gaussian representations may be adopted for real-time visualization of complex scenes
- **Neural Radiance Fields (NeRF)**: Implicit neural representations may be supported for novel view synthesis and scene reconstruction
- **Signed Distance Functions (SDF)**: Implicit surface representations may be adopted for procedural geometry and level-of-detail systems
- **Voxel Representations**: Volumetric data structures may be supported for medical imaging, scientific visualization, or simulation data

Any future adoption of these technologies will be evaluated based on:

- Industry standardization and adoption
- Performance characteristics and scalability
- Integration complexity with existing pipelines
- Backward compatibility requirements
- Use case specific benefits and trade-offs

The current mesh-based requirement ensures maximum compatibility and reliability while the industry continues to evolve toward more advanced geometry representations.