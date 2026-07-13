# connection-point-alignment

| Code     | CP.006 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-006` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

Connection point geometry must be positioned and sized to match the actual physical openings on the equipment.

## Description

Each connection point prim should be placed at the exact location of the corresponding physical interface on the equipment model, oriented so its normal vector points in the direction of flow or connection. The geometry size should match the actual opening dimensions.

## Why is it required?

- Accurate positioning enables simulation runtimes to automatically connect piping, ducts, and cables
- Misaligned connection points produce incorrect simulation results in facility models

## Examples

A correctly aligned FWS supply connection point prim is placed at the center of the pipe flange on the equipment surface, with its normal vector pointing outward in the direction of fluid flow.

## How to comply

Position each connection point prim at the physical opening location on the main geometry. For piping connections, align with the top of the pipe opening. For airflow vents, simplify intricate vent patterns to their aggregate area. Validation is deferred pending the CAD-export workflow.

## Related requirements

- CP.001 `connectionpoints-scope-structure`: connection point prims must be inside the `ConnectionPoints` scope
- CP.002 `connection-point-geometry-type`: geometry type must match the opening shape before alignment is meaningful
- CP.004 `connection-point-naming-convention`: prims must be correctly named to identify what they represent

## Validation Status

Validation for this requirement is deferred to v0.2.0+. The "+" indicates the timeline is less certain than CP.002 and CP.003 (also deferred to v0.2.0): CP.006 depends on an automated placement workflow during CAD-to-USD export that has not yet been designed, whereas CP.002 and CP.003 are simpler validators whose enforcement only awaits implementation. Until the workflow exists, connection point alignment is authored manually.

## For More Information

- [UsdGeomXformable](https://openusd.org/release/api/class_usd_geom_xformable.html)
