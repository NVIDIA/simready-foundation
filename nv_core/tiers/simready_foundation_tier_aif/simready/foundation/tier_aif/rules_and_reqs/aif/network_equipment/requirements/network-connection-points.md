# network-connection-points

| Code | NET.003 |
|---|---|
| Validator | {oav-validator-latest-link}`net-003` |
| Compatibility | {compatibility}`AIF` |
| Tags | {tag}`essential` |

## Summary

This requirement applies only to `network-equipment` in AIF 0.3.

The equipment default prim must contain a `ConnectionPoints` Scope with at least
one direct child Xform whose `simready:connectionPoint:domain` is the USD token
`network`. Each port has a stable prim path, with a descriptive name encouraged.

CAP201_ConnectionPoints.0-3-0 owns the composition, guide purpose, base and
network-domain property checks. Its open vocabulary and completeness reporting
apply unchanged. Inter-equipment links are authored by an assembled scene;
this capability specifies no scene-link schema, cable model or network runtime.

## How to comply

Author the values described above and validate with `AIF-Entity@0.3.0`.
