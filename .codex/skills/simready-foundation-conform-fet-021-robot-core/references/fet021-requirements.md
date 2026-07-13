# FET021 Requirement Repair Map

Use this reference when a validation report or inspection identifies `FET021_ROBOT_CORE_RUNNABLE` or `FET021_ROBOT_CORE_ISAAC` failures. Load the selected JSON manifest first:

- `FET_021_robot_core_runnable_0.2.0.json`
- `FET_021-robot_core_isaac-0.2.0.json`
- `FET_021-robot_core_isaac-0.1.0.json`

The feature markdown and requirement docs are useful context, but the selected manifest and current validation report decide which IDs are in scope.

## Manifest Requirements

| Feature Variant | Requirements |
|---|---|
| `FET021_ROBOT_CORE_RUNNABLE@0.2.0` | `RC.003`, `RC.007`, `RC.008`, `RC.009` |
| `FET021_ROBOT_CORE_ISAAC@0.2.0` | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007`, `RC.008`, `RC.009` |
| `FET021_ROBOT_CORE_ISAAC@0.1.0` | `RC.001`, `RC.003`, `RC.004`, `RC.005`, `RC.006`, `RC.007` |

## Requirement Map

| Requirement | What It Means | Safe Repair | Block When |
|---|---|---|---|
| `RC.001` | Isaac robot asset folder contains only the interface layer at the root plus referenced subfolders. | Re-stage the package into a clean output folder and copy only the interface layer plus referenced subfolders/files. | The source folder contains files whose referenced/unreferenced status cannot be proven. Never delete original source files. |
| `RC.003` | Robot asset path follows `Manufacturer/robot/robot.usd` or `Manufacturer/robot/version/robot.usd`; folder name matches robot filename. | Stage the output into a compliant folder path and rename the interface file consistently. Update relative references if the move changes anchors. | Published package paths cannot change, external references would break, or the intended manufacturer/robot/version names are unknown. |
| `RC.004` | Isaac robot interface asset has a representative thumbnail. Current validator checks `.thumbs/256x256/<interface-file-name>.png` beside the root layer. | Copy an existing representative thumbnail, or generate one from an approved render, into the expected staged thumbnail path. | No representative render/image exists or the local environment cannot generate one. |
| `RC.005` | `physics:*` attributes are authored in a layer whose identifier ends with `_physics.usd`. | Move physics attribute opinions into the staged `_physics.usd` layer while preserving composed values. | Layer strength, variants, references, or payloads make the move unsafe or behavior-changing. |
| `RC.006` | Physics and PhysX API schemas are applied in a layer whose identifier ends with `_physics.usd`. | Move `Physics*` and `Physx*` API schema opinions into the staged `_physics.usd` layer while preserving composed schemas. | Schema opinions are mixed with non-physics authoring or cannot be moved without composition changes. |
| `RC.007` | Default prim has Isaac robot schema/API and non-empty `isaac:physics:robotLinks` and `isaac:physics:robotJoints` relationships. | Apply the robot schema and populate relationships from existing unambiguous link rigid bodies and joint prims. | Isaac schema is unavailable, default prim is wrong, link/joint topology is ambiguous, or links/joints are missing. |
| `RC.008` | Default prim has valid `isaac:robotType`; value must not be `Default`. | Author the robot type from explicit source metadata or user approval. Allowed validator values are `End Effector`, `Manipulator`, `Humanoid`, `Wheeled`, `Holonomic`, `Quadruped`, `Mobile Manipulators`, and `Aerial`. | Robot type is unknown, user has not approved a value, or docs/examples disagree with validator allowed values. |
| `RC.009` | First target of `isaac:physics:robotJoints` is the root joint, and pinning must match robot type. `Manipulator` and `End Effector` require a pinned root joint; other valid types require both joint bodies to be rigid. | Reorder robot joints only when root joint identity is clear. For fixed-base types, make one root joint body target empty/world or non-rigid. For other types, ensure both bodies target rigid bodies. | Root joint identity is unclear, changing body targets would alter robot physics, or robot type is unknown. |

## Common Repair Decisions

Use this decision order before editing:

1. Choose the selected FET021 variant from the profile manifest.
2. Confirm earlier robot physics features have authored real rigid bodies and joints. FET021 can reference them, but it should not invent a robot topology from scratch.
3. Decide the robot type before repairing root joint pinning.
4. Decide the robot root/default prim before applying schema or relationships.
5. Decide whether package layout repairs are allowed to rename or move the root layer.
6. Decide whether physics-layer repairs can preserve composed opinions exactly.

## USD Authoring Notes

Use USD APIs and schema wrappers where available instead of string editing. When the Isaac robot schema package is available, prefer its constants for API names, relationship names, and attribute names.

Important current validator details:

- `RC.003` checks path shape and compares folder name to interface filename stem.
- `RC.004` currently checks `.thumbs/256x256/<interface-file-name>.png`; for `robot.usd`, that means `robot.usd.png`.
- `RC.005` checks every authored `physics:*` attribute property stack item and expects the layer identifier to end with `_physics.usd`.
- `RC.006` checks applied API schema names starting with `Physics` or `Physx` and expects the layer identifier to end with `_physics.usd`.
- `RC.007` imports `usd.schema.isaac.robot_schema` and checks the default prim for robot API plus non-empty robot links/joints relationships.
- `RC.008` rejects `Default`; docs may show values not accepted by the current validator, so follow the validator for pass/fail.
- `RC.009` treats a missing body target or a target without `RigidBodyAPI` as pinned.

## Report Template

For each repair attempt, record:

| Field | Meaning |
|---|---|
| `requirement_id` | Requirement being repaired. |
| `status` | `repaired`, `already_passed`, `blocked`, or `failed`. |
| `affected_prims` | Prim paths inspected or changed. |
| `old_value` and `new_value` | Path, schema, relationship, attribute, layer, thumbnail, or joint target changed. |
| `variant` | Selected FET021 feature ID and version. |
| `outputs` | Files written, copied, moved, or references changed. |
| `reason` | Short explanation, especially for blocked items or manifest/report mismatches. |
