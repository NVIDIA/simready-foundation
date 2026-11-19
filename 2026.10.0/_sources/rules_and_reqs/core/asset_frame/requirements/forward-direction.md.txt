# Explicit forward direction

| Code | AF.001 |
|---|---|
| Validator | AssetFrameChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags | {tag}`correctness` |

## Summary

An asset selecting Object Forward MUST declare its semantic facing on its defaultPrim.

## Description

Author `custom uniform vector3f simready:assetFrame:forwardDirection` with a
finite, unit-length default value. The absolute length tolerance is `1e-4`.
Zero, scaled, blocked, connected, missing, or time-sampled values fail. A
relationship or another Sdf type is not a substitute. The prim MUST be
`UsdGeomXformable`. The vector points from the prim's origin toward its front
in that prim's **local coordinate space**. Arbitrary unit directions are valid;
there is no imposed +X, +Y, or +Z forward axis.

The defaultPrim is required when this feature is selected.
Relevant component prims MAY declare their own facing. Every declaration below
the asset root must satisfy the same rule. A component with no declaration
has no semantic facing: this attribute is not a primvar and does not inherit
through namespace parents. USD composition through references, payloads,
inherits and selected variants still resolves normally on the queried prim.
Consumers must load required payloads; validation covers the composed,
loaded variant and does not claim coverage of unloaded or unselected content.

Native stage `upAxis` supplies up. AF.001 does not add a custom `upDirection`
or require forward to be orthogonal to up. UN.006 continues to enforce Z-up
where selected by a profile. A rotated component can have a vertical facing.
Referenced assets with a different authored up axis require the scene author
to apply the corrective referencing transform; stage metadata does not apply
such a transform automatically.

## Why

Geometry bounds do not identify a couch's front, a joystick's operator side,
or a mobile robot's travel-facing direction reliably.

## Examples

Valid:

```usd
#usda 1.0
(
    defaultPrim = "Toaster"
    upAxis = "Z"
)
def Xform "Toaster" {
    custom uniform vector3f simready:assetFrame:forwardDirection = (0, -1, 0)
}
```

Invalid: `(0, -2, 0)` has length 2; a varying `float3` also violates the
contract even if its numeric value is unit length.

## How to comply

Choose the semantic front from the actual asset and author a unit vector on
its defaultPrim. Use `author_forward_direction` with an explicit direction;
it rejects invalid input rather than normalizing it. The conform skill records
the visual rationale. Validate AF.001 with AssetFrameChecker. The optional runtime query checks the same authored contract on the loaded stage.

## Consumer mapping

`read_forward_direction(prim)` returns the local value.
`world_forward_direction(prim, time)` applies the complete USD local-to-world
linear transform with `TransformDir` and normalizes **after** transformation.
Translation does not affect directions; rotation, reflection, scale and reset
transform stacks do. A transform that collapses the vector is an error.
Use fresh `UsdGeom.XformCache` state after edits. Consumers querying a component
must query that component explicitly and cannot substitute an ancestor's value.

## Related requirements and references

UN.006 owns stage up and VG.025 owns root/origin conventions. GR.002 remains the specialized gripper-site approach vector;
Object Forward neither replaces it nor changes FET028.

[OpenUSD stage up](https://openusd.org/release/api/group___usd_geom_up_axis__group.html)
and [XformCache](https://openusd.org/release/api/class_usd_geom_xform_cache.html).
