# usdgeom-mesh-overlap

| Code     | VG.006 |
|----------|-----------|
| Validator| |
| Compatibility | {compatibility}`Core USD`  |
| Tags     | {tag}`performance` |

## Summary

Meshes should not overlap unnecessarily
 

## Description

Colliding/overlapping meshes can lead to issues in clash detection and physics. These issues are often unintentional and not representative of "the real world". They can also cause visual artifacts and raytracing performance issues.

## Why is it required?
- Visual artifacts
- Slow raytracing performance
- Physics simulation issues
- Clash detection problems

## How to comply
- Place objects with proper spacing
- Check for non-uniform scale issues
- Review composition and transform hierarchies
- Fix in source application and re-convert

## For More Information
- [UsdGeom Mesh Documentation](https://openusd.org/release/api/class_usd_geom_mesh.html)