# No Overrides

Robot USDs avoid local override layers that mask upstream schemas or physics.

## Why
Guarantees predictable behavior across compositions and validators.

## How to comply
- Author changes in source layers, not anonymous/session layers.
- Avoid muting/overriding schema-defining layers.

## Example

Do not use session layers to override physics attributes. Instead, edit the physics layer directly.