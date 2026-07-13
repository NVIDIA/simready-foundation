# Verify Robot Physics Schema Source Layer

Validates that physics schema are authored in the physics layer.

## Why 
For modularized USD structure, the physics edits should be limited to the physics layer, so they can be added or removed from the USD depending on the use cases.

## Example

Apply Physx schemas like `PhysicsRigidBodyAPI` or `PhysicsDriveAPI:angular` only in the physics layer (Physics/physics.usd), not in the base layer.

For example, a prim with rigid body properties should have the schema applied in the physics layer.

## How to comply
- Make sure all the physics related schemas (Physx Schemas, Mujoco Schemas) are in the physics layer, as a delta from the base layer