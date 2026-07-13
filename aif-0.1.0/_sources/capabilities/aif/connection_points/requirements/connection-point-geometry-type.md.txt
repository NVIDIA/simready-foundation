# connection-point-geometry-type

| Code     | CP.002 |
|----------|--------|
| Validator| {oav-validator-latest-link}`cp-002` |
| Compatibility | {compatibility}`AIF` |
| Tags     | {tag}`normative` |

## Summary

Connection point prims must be Plane (rectangular) or Disk (circular) geometry only.

## Description

Connection point geometry represents the physical opening on the equipment where a pipe, duct, or cable connects. A Plane maps to rectangular openings (most electrical and airflow connections), and a Disk maps to circular openings (most piping connections).

## Why is it required?

- Geometry type communicates the shape of the physical interface to simulation runtimes
- Incorrect geometry types can cause misaligned connections in facility layout tools

## Examples

```text
# Rectangular electrical connection point → Plane geometry
def Mesh "nvidia_electrical_nominal_voltage_main" { ... }   # Plane

# Circular piping connection point → Disk geometry
def Mesh "vertiv_fws_supply_piping_connection_main" { ... } # Disk
```

## How to comply

Author connection point prims as Plane geometry for rectangular openings (electrical, airflow) and Disk geometry for circular openings (piping). In USD Composer, this can be done via Create > Mesh > Plane or Create > Mesh > Disk. Validation is deferred to v0.2.0 pending the CAD-export workflow.

## Related requirements

- CP.001 `connectionpoints-scope-structure`: geometry prims must be inside the `ConnectionPoints` scope
- CP.003 `connection-point-purpose-guide`: geometry prims must also have `purpose = "guide"`
- CP.006 `connection-point-alignment`: geometry must be positioned to match actual openings

## Validation Status

Validation for this requirement is deferred to v0.2.0. The requirement is documented normatively and must be followed, but no automated check is enforced in v0.1.0.

## For More Information

- [UsdGeomMesh](https://openusd.org/release/api/class_usd_geom_mesh.html)
