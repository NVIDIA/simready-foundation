# Verify Robot Physics Attributes Source Layer

Validates that physics attributes are authored in the physics layer.

## Why 
For modularized USD structure, the physics edits should be limited to the physics layer, so they can be added or removed from the USD depending on the use cases.

## Example

In the base layer (Robot.usd), define the links and their basic properties. 

In the physics layer (physics/physics.usd), add physics attributes like `physics:centerOfMass` or `physics:mass`.

For instance, a joint should only exist the physics layer as its a constraint set on rigid bodies, which are physics layer only attributes.

## How to comply
- Make sure all the physics related attributes (colliders, rigid body, joints) are in the physics layer, as a delta from the base layer