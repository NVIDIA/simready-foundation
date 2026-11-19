# no-articulation-loops

| Code     | DJ.011 |
|----------|--------|
| Validator| CheckStage |
| Compatibility | {compatibility}`OpenUSD` |
| Tags     | {tag}`essential` |

## Summary

The articulation must have no loops and at most one joint between any two bodies. Only joints that participate in the articulation are checked; joints with `physics:excludeFromArticulation = true` are ignored.

## Description

Joint–body connections form a tree (bodies as nodes, joints as edges). This rule enforces:

- **No cycles**: The articulation graph must be acyclic. A loop is any cyclic path, e.g. Body_A – Joint_1 – Body_B – Joint_2 – Body_C – Joint_3 – Body_A.
- **Single joint per body pair**: At most one joint may connect the same two bodies.

Only joints that are **in** the articulation are validated. Joints with `physics:excludeFromArticulation = true` are excluded from the graph. Therefore a loop in the overall scene is allowed if at least one joint in that loop has `excludeFromArticulation = true`; that joint is not part of the articulation subgraph, so the articulation can remain a tree.

- **Excluded joints and stability**: It is acceptable to use `excludeFromArticulation` on a joint in the loop, preferably on the **non-critical path** of the simulation. Be aware that an excluded joint is simulated as a simple maximal constraint rather than as part of the articulation’s Featherstone formulation, so it is generally **less stable** than joints inside the articulation set. **Joint drives are not recommended** on excluded joints; this spec does not currently enforce the absence of drives on such joints.
- **Directed parent-to-child order in closed loops (Newton and MuJoCo compatibility)**: Solvers such as Newton and MuJoCo require every non-excluded articulation joint (`physics:excludeFromArticulation = false`) to be directed from parent (`physics:body0`, closer to the articulation root) to child (`physics:body1`, farther from the root). When breaking a closed kinematic loop (such as a 4-bar linkage `J2_link -(P1)-> P1_link -(P2)-> P2_link -(P2_01)-> J3_link`), set `physics:excludeFromArticulation = true` on the **loop-closing joint** (`P2_01`) whose `body1` reconnects to an already-visited ancestor or branch, rather than on the root-side entry joint (`P1`), so the remaining articulation tree is traversed strictly from `body0` to `body1` (and omit `MjcJointAPI` on the excluded `P2_01` joint in `runnables/physics/mujoco.usda`). In addition, ensure passive parallel-branch joints (`P1`, `P2`) in `runnables/physics/newton.usda` and `runnables/physics/mujoco.usda` zero out any inherited `targetPosition = 0` position-drive springs (`drive:angular:physics:stiffness = 0`, `damping = 0`) so residual springs do not fight the closed loop or cause passive loop joints to be classified as active DOFs. Keep general (nonlinear) four-bar and closed-loop dependence governed by the loop-closing joint/constraint without adding competing affine mimic constraints; only author `NewtonMimicAPI` / `MjcEqualityJointAPI` when the source mechanism specification or a verified constant-ratio mechanism establishes that exact affine relation.

## Why is it required?

* Physics articulations expect a tree-like structure for correct simulation
* Multiple joints between the same two bodies are ambiguous for the solver
* Cyclic link paths without an excluded joint can cause undefined or unstable behavior

## Examples

### Invalid: Simple loop (cycle)
— Body_A, Body_B, Body_C with one joint each, notice there is a loop but no "excludeFromArticulation" is set to true.

```text
        Body_A
       /      \
  Joint_1    Joint_3
     /          \
  Body_B      Body_C
     \          /
   Joint_2 ————/
```
*Articulation graph: cycle (invalid).*

```usd
def Xform "Body_A" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_B" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_C" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def PhysicsRevoluteJoint "Joint_1"
{
    rel physics:body0 = </Body_A>
    rel physics:body1 = </Body_B>
}

def PhysicsRevoluteJoint "Joint_2"
{
    rel physics:body0 = </Body_B>
    rel physics:body1 = </Body_C>
}

def PhysicsRevoluteJoint "Joint_3"
{
    rel physics:body0 = </Body_C>
    rel physics:body1 = </Body_A>
}
```

### Valid: Simple chain (tree)
— Body_A, Body_B, Body_C with one joint each, forms a loop and excludeFromArticulation is set to true on Joint_3.

```text
        Body_A
       /      \
  Joint_1   Joint_3 (excluded)
     /          \
  Body_B      Body_C
     \          /
   Joint_2 ————/
```
*Articulation graph: tree A—B—C; Joint_3 excluded from articulation.*

```usd
def Xform "Body_A" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_B" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_C" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def PhysicsRevoluteJoint "Joint_1"
{
    rel physics:body0 = </Body_A>
    rel physics:body1 = </Body_B>
}

def PhysicsRevoluteJoint "Joint_2"
{
    rel physics:body0 = </Body_B>
    rel physics:body1 = </Body_C>
}

def PhysicsRevoluteJoint "Joint_3"
{
    rel physics:body0 = </Body_C>
    rel physics:body1 = </Body_A>
    bool physics:excludeFromArticulation = 1    
}
```

### Also valid: Simple chain (tree)
— Body_A, Body_B, Body_C with one joint each, forms a loop and excludeFromArticulation is set to true on Joint_2.

```text
        Body_A
       /      \
  Joint_1    Joint_3
     /          \
  Body_B   Joint_2 (excluded)
     \          /
      \      Body_C
       \    /
        ——/
```
*Articulation graph: tree A—B—C via Joint_1 and Joint_3; Joint_2 excluded from articulation.*

```usd
def Xform "Body_A" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_B" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def Xform "Body_C" (
    prepend apiSchemas = ["PhysicsRigidBodyAPI"]
)
{
}

def PhysicsRevoluteJoint "Joint_1"
{
    rel physics:body0 = </Body_A>
    rel physics:body1 = </Body_B>
}

def PhysicsRevoluteJoint "Joint_2"
{
    rel physics:body0 = </Body_B>
    rel physics:body1 = </Body_C>
    bool physics:excludeFromArticulation = 1
}

def PhysicsRevoluteJoint "Joint_3"
{
    rel physics:body0 = </Body_C>
    rel physics:body1 = </Body_A>
}
```


## How to comply

* Ensure the articulation subgraph (excluding joints with `physics:excludeFromArticulation = true`) is a tree (no cycles)
* Ensure each body pair is connected by at most one joint that is in the articulation
* To allow a physical loop in the mechanism, set `physics:excludeFromArticulation = true` on one of the joints in the loop so the articulation graph remains acyclic

## Related requirements

- [check-robot-relationships](check-robot-relationships.md)
- [physics-joint-has-drive-or-mimic-api](physics-joint-has-drive-or-mimic-api.md)

## For More Information

* [USD Physics Joint Relationships](https://openusd.org/dev/api/usd_physics_page_front.html#usdPhysics_joints)
* [PhysX Articulation](https://docs.omniverse.nvidia.com/physx/physx/5.3.1/docs/Articulations.html)