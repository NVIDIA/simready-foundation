# Requirements

## Summary

**Graspable Vectors** is a line or lines (1 start point, 1 end point) that intersect the prop or object.  These lines denote how the robotic grippers will try and align itself to the object and close it's grippers.  

These lines can be authored or expressed in the USD as basis curves.  Usd Basis curves will allow for the vector visualization in all runtimes.  Alternatively, lines can be authored in USD as a mesh, however it will be dependent on the runtime to display this representation.  For example, Omniverse Kit cannot display a mesh without triangles.      

- **Basis Curve**: BasisCurves are a batched curve representation analogous to the classic RIB definition via Basis and Curves statements. BasisCurves are often used to render dense aggregate geometry like hair or grass.
- **Mesh**: As a point-based primitive, meshes are defined in terms of points that are connected into edges and faces. Many references to meshes use the term 'vertex' in place of or interchangeably with 'points', while some use 'vertex' to refer to the 'face-vertices' that define a face. To avoid confusion, the term 'vertex' is intentionally avoided in favor of 'points' or 'face-vertices'.


## Schema / OpenUSD Specification
<!-- SCORE_TAG:LINK_TO_SCHEMA_DOCS:CORE -->

Collider approximations are created using the following schemas that are part of the core OpenUSD specification.

- [UsdBasisCurve Documentation](https://openusd.org/dev/api/class_usd_geom_basis_curves.html)
- [UsdMesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)


## Requirements

<!-- SCORE_TAG:LIST_OF_REQUIREMENTS -->
<!-- PHYSICS_GRASPABLE_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- PHYSICS_GRASPABLE_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements/graspable-vector-line
```