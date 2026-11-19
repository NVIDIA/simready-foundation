# Connections

This capability defines declared pairings on an **assembly** stage: which socket and plug are connected, whether their catalog interfaces match, and how the pairing is physically held.

## Summary

A connection prim lives under a `Connections` Scope beneath the assembly default prim. It targets one socket site and one plug site, requires opposite roles and equal `mechanical:interface` tokens, requires both parts to be composed by reference rather than authored inline, and declares a `realization` that must agree with how the two mate bodies resolve. A mate body is the nearest ancestor with an **enabled** `PhysicsRigidBodyAPI`, so a part the assembly demoted with `physics:rigidBodyEnabled = false` is transparent to that walk.

Parts demoted that way, sitting under one enabled body, take `compound`. Both sites resolve to that shared body, the assembly is a single physics actor, composition holds the alignment, and there is no joint. `CN.011` specifies the body: assembly-local, carrying no reference arc, and carrying `physics:mass` equal to the sum of the parts it fuses.

Two distinct mate bodies take `jointed`. An authored `UsdPhysicsFixedJoint` holds the pairing, and the connection points at it with `rel simready:mate:joint` so a consumer resolves the joint by lookup rather than by searching for a matching body pair. The joint is authored rather than inferred, which keeps the assembly rigid in a runtime that does not read the `simready:mate:` namespace and satisfies `RB.012` for nested rigid bodies. A SimReady-aware runtime still owns the joint: it follows the relationship and disables, retunes, or deletes the prim to release the pairing.

Sites never hold the joint. The assembly default prim carries a required `simready:mate:assemblyType` classification from a closed list.

`realization` also selects which feature governs a connection. `compound` connections are fully specified by `CAP027_Connections`, including the compound body. `jointed` connections additionally fall under `CAP029_ConnectionJoint` and its PhysX, Newton, and MuJoCo variants. One assembly may mix both, in which case each group of compound connections has its own compound body.

Assemblies nest. The default prim is `assembly`, and each child asset root is `component` or `assembly` (`CN.012`). A nested assembly's connections occupy the sites they pair (`CN.007`), and its unpaired sites stay available to the outer assembly. A part that contains a joint joins only through a `jointed` connection (`CN.011`).

## Schema / OpenUSD Specification

- [UsdPhysics Joints](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
- [UsdPhysicsFixedJoint](https://openusd.org/dev/api/class_usd_physics_fixed_joint.html)
- [UsdGeomScope](https://openusd.org/dev/api/class_usd_geom_scope.html)

Custom attributes and relationships use the `simready:mate:` prefix on connection prims.

## Validation

Static checkers live in `validation.py` and are registered in `rules_and_reqs/__init__.py`. Requirement pages state the fail/warn contract.

Mass for `CN.005` and `CN.011` is summed from `PhysicsMassAPI` in the subtree, stopping at the first prim on each branch that authors `physics:mass` so a compound aggregate is never added to the part masses beneath it. `SR.003` root-layer `mass` does not compose across a reference and is not the source. `CN.005` applies only to `jointed` connections; a compound has no joint to rate, and `CN.011` checks its aggregate instead.

{doc}`Full Requirements List <requirements>`

```{toctree}
:maxdepth: 1
:hidden:

requirements
```
