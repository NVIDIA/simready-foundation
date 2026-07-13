# FET004 Requirement Repair Notes

Use this reference with `simready-foundation-conform-fet-004-simulate-multi-body-physics` when a validation report names FET004 requirements.

## Applicability

FET004 is for assets that are intentionally multi-body: articulated props, mechanisms, robots, or PhysX assets with multiple intended rigid bodies. It is not a way to make every prop pass a multibody gate.

For single-rigid-body props, report FET004 as not applicable when the selected profile allows prop physics through FET003. Do not add dummy bodies or split geometry just to satisfy RB.MB.001.

Do not use mesh count as the deciding signal. A single physical object may be authored as many meshes for material assignment, LOD, CAD part boundaries, or rendering convenience. FET004 applies when there is evidence of multiple intended rigid bodies, joints, articulations, robot links, or source multibody structure.

Before attempting repair, check profile docs such as `profiles.toml` comments for optional or conditional FET004 wording. If the profile says FET004 is optional/conditional and the asset is a one-body prop, summarize the gate as skipped/not applicable and continue to the next profile feature.

## No New Geometry Rule

The skill may author or repair physics metadata, schemas, joint prims, articulation roots, relationships, and attributes. It must not author new meshes, primitive shapes, collider proxies, duplicated visuals, or imported geometry.

If conformance requires geometry that is not already present in the USD, block and report the need for upstream CAD/URDF/MJCF/source conversion or user-provided geometry.

## Requirement Map

| Requirement | Meaning | Repair Approach |
|---|---|---|
| `RB.MB.001` | Asset must contain at least two rigid bodies for multibody simulation. | Apply `UsdPhysics.RigidBodyAPI` only to existing xformable part roots that clearly represent separate physical bodies. If only one real body exists, skip or block; never create geometry. |
| `JT.001` | Rigid bodies that are not free-floating should be constrained by joints. | Add or repair `UsdPhysicsJoint` prims only when body pairing and joint type are known from existing joints, source metadata, robot topology, naming, or user input. |
| `JT.002` | Joint body targets must exist or remain empty for world anchoring. | Retarget to existing prims when the intended body is clear. Leave world-anchored sides empty when intended. Block on missing unknown targets. |
| `JT.003` | `physics:body0` and `physics:body1` must each have at most one target. | Reduce multi-target relationships only when one target is unambiguously correct; otherwise block. |
| `JT.ART.002` | Articulation roots cannot be nested. | Keep one clear articulation root and remove or relocate nested roots only when the intended root is obvious. |
| `JT.ART.003` | Articulation roots are not allowed on kinematic bodies. | Clear kinematic mode only when dynamic articulation is intended. Otherwise block for user intent. |
| `JT.ART.004` | Articulation roots are not allowed on static or disabled bodies. | Enable the rigid body only when dynamic articulation is intended. Otherwise block for user intent. |

## Variant Notes

`FET004_BASE_NEUTRAL@0.1.0` depends on `FET003_BASE_NEUTRAL@0.1.0` and carries the joint/articulation/RB.MB requirements above.

`FET004_BASE_PHYSX@0.1.0` depends on `FET003_BASE_PHYSX@0.1.0` and `FET004_BASE_NEUTRAL@0.1.0`; it also includes the selected PhysX collision requirement from the manifest.

`FET004_BASE_PHYSX@0.2.0` depends on `FET003_BASE_PHYSX@0.2.0` and `FET004_BASE_NEUTRAL@0.1.0`; it includes `PHYSX.COL.001` and `PHYSX.COL.002`.

`FET004_ROBOT_PHYSX` uses a robot-specific manifest with rigid-body, joint, articulation, PhysX collider, and robot collision requirements. It intentionally omits RB.COL.001. Preserve robot link and joint semantics.

## Block Conditions

Stop and report when:

- The USD contains only one physical body candidate.
- The selected profile marks FET004 optional or conditional and the asset has no multibody intent.
- The only way to pass is to create, duplicate, split, or import geometry.
- Joint type, axis, anchor frame, or body pairing cannot be inferred safely.
- A missing joint target has no existing replacement prim.
- Multiple articulation roots are plausible and the intended root is unclear.
- PhysX collider conformance needs new collider geometry.
- Runtime behavior, such as a drop test or joint motion test, is required but unavailable.

## Stage Summary Checklist

Include these points in the report:

- FET004 variant and version.
- Whether FET004 was applied, skipped as not applicable, failed, or blocked.
- Rigid-body roots before and after repair.
- Joint prims before and after repair.
- Articulation roots before and after repair.
- Explicit confirmation that no geometry was created.
- Validation report path and first remaining failing gate.
