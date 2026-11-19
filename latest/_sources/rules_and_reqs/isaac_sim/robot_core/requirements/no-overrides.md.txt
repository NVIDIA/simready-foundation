# no-overrides

| Code     | RC.002 |
|----------|--------|
| Compatibility | {compatibility}`Isaac Sim` |
| Tags     | {tag}`correctness` |

## Summary

Robot USDs avoid local override layers that mask upstream schemas or physics.

## Why
Guarantees predictable behavior across compositions and validators.

## How to comply
- Author changes in source layers, not anonymous/session layers.
- Avoid muting/overriding schema-defining layers.

## Example

Do not use session layers to override physics attributes. Instead, edit the physics layer directly.

## Validation scope

`NoOverrides` checks default-valued attribute opinions in the open stage's root
layer stack. A single opinion on a `def` prim is part of the asset's definition.
A value on an `over` prim spec, or multiple local default-value opinions for one
attribute, is reported. Selected variant opinions are checked at their authored
prim-spec paths.

Physics and PhysX attribute opinions in a `physics.usd`, `physics.usda`, or
`physics.usdc` layer are allowed, consistent with RC.005 and RC.006. Other
attributes in that layer remain subject to this check. Physics-layer opinions
remain part of the comparison: a stronger opinion authored outside a physics
layer is reported when it masks a weaker physics-layer default.

Session-layer opinions, time samples, and opinions inside referenced or payloaded
assets are outside this check. Referenced and payloaded assets are validated
independently. The `Render` prim subtree is excluded.
