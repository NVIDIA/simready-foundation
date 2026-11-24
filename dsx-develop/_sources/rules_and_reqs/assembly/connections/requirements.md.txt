# Requirements

## Summary

A connection pairs one socket mate site with one plug mate site on a composed assembly stage, composes both parts by reference, and declares a `realization` that must agree with how the two mate bodies resolve. One shared mate body takes `compound`, where composition holds the pairing and there is no joint. Two distinct mate bodies take `jointed`, where an authored `UsdPhysicsFixedJoint` holds the pairing and the connection points at it with `simready:mate:joint`. The assembly also carries an `assemblyType` classification from a closed list.

A compound's shared mate body is specified by `CN.011`: an assembly-local prim with no reference arc, an enabled `PhysicsRigidBodyAPI`, and a `physics:mass` summed from the parts it fuses, each of which authors `physics:rigidBodyEnabled = false`. The aggregate may be omitted only when the parts carry their mass on their colliders, which the runtime sums onto the compound body by itself. A part that contains a joint joins only through a `jointed` connection.

`CN.012` fixes the model hierarchy: an `assembly` default prim over `component` or `assembly` child asset roots. A nested assembly's connections occupy the sites they pair (`CN.007`); its unpaired sites stay available.

Requirements split across features by the `realization` token. `CAP027_Connections` owns the declaration and the compound shape. `CAP029_ConnectionJoint` adds the authored joint and its payload rating for `jointed` connections, and the PhysX, Newton, and MuJoCo variants constrain what may be layered onto that joint.

## Requirements

```{requirements-table}
```

```{toctree}
:maxdepth: 1
:hidden:

requirements/connection-rels
requirements/connection-targets-resolve
requirements/opposite-roles
requirements/interface-match
requirements/payload-capacity
requirements/mate-realization
requirements/exclusive-pairing
requirements/assembly-type
requirements/connection-joint
requirements/assembly-child-references
requirements/compound-body
requirements/assembly-model-hierarchy
requirements/physx-connection-joint
requirements/newton-connection-joint
requirements/mujoco-connection-joint
```
