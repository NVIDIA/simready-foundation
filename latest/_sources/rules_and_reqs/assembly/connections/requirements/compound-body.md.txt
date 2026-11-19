# compound-body

| Code     | CN.011 |
|----------|--------|
| Validator| CompoundBodyChecker |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The mate body shared by a `compound` connection must be an assembly-local prim carrying no reference or payload arc, with an enabled `PhysicsRigidBodyAPI` and a `physics:mass` equal to the sum of the parts it fuses. It may omit that aggregate only when the parts carry their mass on their colliders, which the runtime sums to the same total. Every part beneath it must author `physics:rigidBodyEnabled = false`, and no joint may sit beneath it.

## Description

This requirement applies to any assembly stage carrying at least one connection with `realization = "compound"`. A stage with only `jointed` connections is skipped.

For each compound connection, both sites resolve to one enabled rigid body (`MC.003`, `CN.006`). That prim is the **compound body**, and it is the single physics actor the fused parts simulate as. It must satisfy all of the following.

### Assembly-local

The compound body is a descendant of the assembly default prim and is not the default prim itself, and it introduces no `references` or `payload` arc.

Both halves matter. Barring the arc is what keeps the aggregate off a part root: a prim that references a published asset means "one of those", and a mass three times that asset's own reads as a corrupt part rather than as a stack. Barring the default prim keeps the actor scoped, so an assembly can hold several compound groups, or mix compound groups with jointed parts, without one rigid body swallowing the whole stage.

The practical consequence is that the compound body is a prim the assembly author creates — typically one `Xform` under the default prim, given `kind = "group"` so the model hierarchy stays contiguous (`CN.012`).

### Enabled body with resolved mass

The compound body has `PhysicsRigidBodyAPI` applied with `physics:rigidBodyEnabled` resolving true, and its mass resolves to the combined mass of its parts by one of two routes.

**Authored aggregate.** `PhysicsMassAPI` applied with a positive `physics:mass` authored on the assembly stage. This route works whatever the parts do with their own mass.

**Collider-derived.** The compound body authors no mass, and every part's mass sits on its collision shapes. Colliders attribute to the nearest enabled body, so the runtime sums them onto the compound body and reaches the same total unaided.

`RB.007` allows a rigid body to state its mass either on the body or on its collision shapes. This requirement pins what the total must be for a compound, and requires the authored aggregate whenever the parts place mass somewhere the runtime will not read it.

### Demoted parts

No other prim in the compound body's subtree may have an enabled rigid body. Each part root authors `physics:rigidBodyEnabled = false` and otherwise keeps the `PhysicsRigidBodyAPI` and `PhysicsMassAPI` its author supplied.

Disabling rather than deleting is deliberate. The part keeps the mass, inertia, and physics material it was validated with, so re-promoting it is a one-attribute edit and the aggregate can be checked against values still present on the stage. A part whose rigid body was stripped leaves nothing to sum and nothing to restore.

Colliders in the demoted subtrees attribute to the compound body, because it is the nearest enabled body above them. That is what makes the fused actor collide with the union of its parts' shapes.

A nested assembly's compound body is a part root like any other: the outer compound demotes it, and the outer compound body carries the aggregate.

### No joints

No prim in the compound body's subtree may be a `UsdPhysicsJoint`. A part that contains a joint, such as a gripper or an assembly with `jointed` connections, joins only through a `jointed` connection.

### Aggregate mass

An authored `physics:mass` on the compound body must equal the sum of the part masses within 1%.

Collect that sum by walking down from the compound body and stopping at the first prim on each branch that authors `physics:mass`; that value stands for its whole subtree. Stopping is what prevents a part's own mass from being added to a nested aggregate beneath it, and it is the same traversal `CN.005` uses.

A branch with no authored mass anywhere warns and skips the fail, matching `CN.005`. An aggregate that disagrees with a complete sum fails: it is a physical claim about the assembly that the assembly's own parts contradict.

The aggregate may be omitted only when every authored `physics:mass` beneath the compound body sits on a prim the runtime reads mass from, meaning a collision shape or the compound body itself. Mass on a demoted part root is inert: the root is neither a collider nor an enabled body, so the runtime discards the authored value and derives that part from collider volume and density instead. A compound whose parts hold mass that way must author the aggregate, and so must a compound with no part mass at all.

### Failure summary

| Condition | Verdict |
|---|---|
| Shared mate body carries a `references` or `payload` arc | Fail |
| Shared mate body is the assembly default prim | Fail |
| No `physics:mass` on the compound body, and a part authors mass on a prim that is neither a collider nor an enabled body | Fail |
| No `physics:mass` on the compound body and none on the parts' colliders | Fail |
| No `physics:mass` on the compound body, with every part's mass on its colliders | Pass |
| A part in the subtree has an enabled rigid body | Fail |
| A prim in the subtree is a joint | Fail |
| Aggregate differs from a complete part sum by more than 1% | Fail |
| A branch authors no mass, so the sum is incomplete | Warn |

## Why is it required?

- Without a dedicated body, the aggregate lands on whichever part happens to be first, and a 28.5 kg pallet reads as 85.5 kg to anyone who does not know the stack convention.
- A compound that keeps only one part's mass simulates lighter than the object it represents, which changes how it falls, tips, and loads whatever carries it.
- Scoping the actor to a prim below the default prim is what lets one assembly hold both compound groups and jointed parts.
- Disabling rather than deleting keeps the demoted part's physics data available, so the aggregate is verifiable and the demotion is reversible.

## Examples

```usd
# Valid: three pallets fused onto one compound body
def Xform "IndustrialPlasticPallet_Stack_A01" (
    kind = "assembly"
)
{
    def Xform "CompoundBody" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
        kind = "group"
    )
    {
        float physics:mass = 85.5

        def Xform "Pallet_0" (
            prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
        )
        {
            bool physics:rigidBodyEnabled = false
            double3 xformOp:translate = (0, 0, 0)
            uniform token[] xformOpOrder = ["xformOp:translate"]
        }

        def Xform "Pallet_1" (
            prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
        )
        {
            bool physics:rigidBodyEnabled = false
            double3 xformOp:translate = (0, 0, 0.0505)
            uniform token[] xformOpOrder = ["xformOp:translate"]
        }

        def Xform "Pallet_2" (
            prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
        )
        {
            bool physics:rigidBodyEnabled = false
            double3 xformOp:translate = (0, 0, 0.101)
            uniform token[] xformOpOrder = ["xformOp:translate"]
        }
    }
}
```

```usd
# Invalid: the aggregate is authored on a part root, which is a reference to a
# single 28.5 kg pallet
def Xform "Pallet_0" (
    prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
)
{
    float physics:mass = 85.5

    def Xform "Pallet_1" (
        prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false
    }
}
```

```usd
# Valid: no aggregate, because each part carries its mass on its collider and
# the runtime sums colliders onto the nearest enabled body above them
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    kind = "group"
)
{
    def Xform "Pallet_0" (
        prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        # the reference authors physics:mass on the collider mesh, not on its root
        bool physics:rigidBodyEnabled = false
    }
}
```

```usd
# Invalid: compound body authors no mass, and each part's 28.5 kg sits on a
# demoted root, which is neither a collider nor an enabled body, so the runtime
# discards it and derives the stack from collider volume and density
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
    kind = "group"
)
{
    def Xform "Pallet_0" (
        prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        # the reference authors physics:mass = 28.5 on this root
        bool physics:rigidBodyEnabled = false
    }
}
```

```usd
# Invalid: Pallet_1 is still an enabled body, so it is its own actor and the
# sites do not share a mate body
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    float physics:mass = 57

    def Xform "Pallet_0" (
        prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
        bool physics:rigidBodyEnabled = false
    }

    def Xform "Pallet_1" (
        prepend references = @../../pallet/simready_usd/pallet.usd@</RootNode>
    )
    {
    }
}
```

```usd
# Invalid: aggregate is one pallet's mass, not three
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    float physics:mass = 28.5
}
```

```usd
# Valid: two nested stacks fused onto an outer compound body; each inner
# compound body is demoted, and the outer aggregate sums the inner aggregates
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    float physics:mass = 171

    def Xform "Stack_0" (
        prepend references = @../../pallet_stack/simready_usd/pallet_stack.usda@
    )
    {
        over "CompoundBody"
        {
            bool physics:rigidBodyEnabled = false
        }
    }

    def Xform "Stack_1" (
        prepend references = @../../pallet_stack/simready_usd/pallet_stack.usda@
    )
    {
        over "CompoundBody"
        {
            bool physics:rigidBodyEnabled = false
        }
    }
}
```

```usd
# Invalid: the gripper contains joints, so it cannot be fused into a compound
def Xform "CompoundBody" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsMassAPI"]
    kind = "group"
)
{
    def Xform "Gripper" (
        prepend references = @../../gripper/simready_usd/gripper.usda@
    )
    {
        def PhysicsRevoluteJoint "finger_joint"
        {
        }
    }
}
```

## How to comply

1. Create one `Xform` under the assembly default prim with no reference or payload arc. Give it `kind = "group"`.
2. Apply `PhysicsRigidBodyAPI` and `PhysicsMassAPI` to it and leave `physics:rigidBodyEnabled` at its true default.
3. Compose each part under it and author `bool physics:rigidBodyEnabled = false` on each part root, and on each nested compound body. Leave the part's `PhysicsMassAPI` and `physics:mass` alone. Join a part that contains a joint through a `jointed` connection instead.
4. Read `physics:mass` off each part from the composed stage, sum it, and author the result as `physics:mass` on the compound body. Derive this from the asset; do not estimate it. Skip this step only when every part's mass is already on its colliders, where the runtime sums it for you.
5. Pose the parts so the mate sites coincide, and point each compound connection's socket and plug at sites inside those parts.

## Related Requirements

- [mate-realization](mate-realization.md)
- [assembly-child-references](assembly-child-references.md)
- [payload-capacity](payload-capacity.md)
- [assembly-model-hierarchy](assembly-model-hierarchy.md)
- [mate-body-rigid-ancestor](../../mates/requirements/mate-body-rigid-ancestor.md)
- [rigid-body-mass](../../../physics_bodies/physics_rigid_bodies/requirements/rigid-body-mass.md)

## For More Information

- [UsdPhysics Rigid Body](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_rigid_bodies)
- [UsdPhysicsMassAPI](https://openusd.org/dev/api/class_usd_physics_mass_a_p_i.html)
- [USD Model Hierarchy and Kind](https://openusd.org/release/api/class_usd_model_a_p_i.html#Usd_ModelKind)
