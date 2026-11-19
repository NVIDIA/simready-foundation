---
name: simready-foundation-conform-fet-022-mujoco
description: "Use for repairing exact CAP022_DrivenJoints.MuJoCo SimReady conformance for MuJoCo driven-joint conformance. Use when a profile, validation report, or user request names CAP022_DrivenJoints.MuJoCo; default to `CAP022_DrivenJoints.MuJoCo.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_022_MUJOCO."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - mujoco
---

# SimReady Conform CAP022_DrivenJoints.MuJoCo

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact capability skill when the selected profile, validation report, or user request names `CAP022_DrivenJoints.MuJoCo`. It repairs or stages MuJoCo driven-joint conformance without drifting into another runtime contract.

Default to `CAP022_DrivenJoints.MuJoCo.0-1-0` when the user asks for this capability without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP022_DrivenJoints.MuJoCo.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP022_DrivenJoints.MuJoCo.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_driven_joints/requirements/mujoco-joint-api.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/physics_bodies/physics_driven_joints/requirements/mujoco-actuator-targets.md`

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the capability markdown for human-readable contract details, requirement links, samples, runtime tests, and adapters.

## Capability Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `CAP022_DrivenJoints.MuJoCo.0-1-0` | CAP004_Multibody.RobotMuJoCo.0-1-0 | `DJ.011`, `MUJOCO.DJ.001`, `MUJOCO.DJ.002` |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `CAP022_DrivenJoints.MuJoCo` manifest, feature markdown, and MuJoCo requirement docs before editing.
3. Create or use a staged output location unless the user explicitly asks for in-place edits.
4. Repair only the requirements listed by the selected `CAP022_DrivenJoints.MuJoCo` manifest and its dependencies.
5. Preserve existing USD joint topology, body relationships, and authored limits unless a reported validation failure requires a narrow correction.
6. Apply `MjcJointAPI` to non-fixed articulation joints (`physics:excludeFromArticulation = false`) that belong to the MuJoCo driven-joint contract. Do not apply `MjcJointAPI` to loop-closing joints excluded from the articulation (`physics:excludeFromArticulation = true`).
7. Author or repair MuJoCo joint tuning attributes only on USD physics joint prims. Keep `mjc:armature` finite and non-negative.
8. Author or repair `MjcActuator` prims for independently driven joints so each actuator has `rel mjc:target` pointing to a valid `MjcJointAPI` joint (or a fixed `MjcTendon` with `uniform token mjc:type = "fixed"` whose selected `mjc:path` / `mjc:path:indices` entries target valid 1-DOF `MjcJointAPI` joints with non-zero `mjc:path:coef` contribution).
9. For 1-DOF scalar mimic / equality-coupled follower joints (`PhysicsRevoluteJoint` or `PhysicsPrismaticJoint`), apply `["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"]` on the follower joint with `rel newton:mimicJoint` targeting an actuated leader joint (see **MuJoCo Mimic Joints, Tendons, and Closed-Loop Linkages** below) instead of authoring a competing `MjcActuator` on the follower.
10. Keep authored actuator ranges finite and ordered, and keep authored gain and bias parameter arrays numeric.
11. Rerun the same profile gate or the narrowest available feature/capability validation gate. If MuJoCo runtime evidence is unavailable, report that limitation instead of claiming a runtime pass.
12. Summarize the selected `CAP022_DrivenJoints.MuJoCo` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## MuJoCo Mimic Joints, Tendons, and Closed-Loop Linkages

Following the official `mjcPhysics` schema and `mujoco-usd-converter` conventions (as exemplified by `newton-assets/robotiq_2f85_v4/usd_structured`):

- **Mimic / Equality-Coupled Joints (`NewtonMimicAPI` + `MjcEqualityJointAPI`)**:
  - In `mjcPhysics`, `MjcEqualityJointAPI` inherits from `NewtonMimicAPI`. The legacy properties `mjc:coef0`, `mjc:coef1`, and `mjc:target` on `MjcEqualityJointAPI` are deprecated; instead, `NewtonMimicAPI` owns the target relationship and linear polynomial terms while `MjcEqualityJointAPI` owns solver impedance/reference parameters (`mjc:solimp`, `mjc:solref`) and higher-order polynomial terms (`mjc:coef2`, `mjc:coef3`, `mjc:coef4`).
  - Because `MjcEqualityJointAPI` builds on `NewtonMimicAPI` (just as `MjcCollisionAPI` builds on `NewtonCollisionAPI`), `NewtonMimicAPI` and `newton:mimicJoint`, `newton:mimicEnabled`, `newton:mimicCoef0`, `newton:mimicCoef1` are explicitly permitted under `RV.011` in a MuJoCo composition.
  - On each mimic follower joint in `runnables/physics/mujoco.usda`, author:
    ```usda
    over "follower_joint" (
        prepend apiSchemas = ["MjcJointAPI", "NewtonMimicAPI", "MjcEqualityJointAPI"]
    )
    {
        float drive:angular:physics:damping = 0
        float drive:angular:physics:stiffness = 0
        uniform double[] mjc:solimp = [0.95, 0.99, 0.001, 0.5, 2]
        uniform double[] mjc:solref = [0.005, 1]
        float newton:mimicCoef0 = 0
        float newton:mimicCoef1 = 1
        bool newton:mimicEnabled = 1
        rel newton:mimicJoint = </Robot/joints/leader_joint>
    }
    ```
  - **Ordering, sign, and unit conventions**:
    - `NewtonMimicAPI` + `MjcEqualityJointAPI` are applied on a **1-DOF scalar follower joint** (`PhysicsRevoluteJoint` or `PhysicsPrismaticJoint`; `joint1` in MJCF `<equality><joint>`), and `rel newton:mimicJoint` targets a **1-DOF scalar leader joint** (`joint2` in MJCF) that is actuated (directly, via a fixed tendon, or via an acyclic mimic chain rooted at an actuated joint).
    - The enforced polynomial is $q_{\text{follower}} = c_0 + c_1 q_{\text{leader}} + c_2 q_{\text{leader}}^2 + \dots$ with a non-zero effective coupling coefficient consumed by the applied schema (`newton:mimicCoef1` taking precedence over legacy `mjc:coef1`, and higher-order `mjc:coef2..4` consumed only when `MjcEqualityJointAPI` is applied). Note that PhysX `PhysxMimicJointAPI` uses the homogeneous form $q_{\text{follower}} + \text{gearing} \cdot q_{\text{leader}} + \text{offset} = 0$, so a PhysX `gearing` of `-1` (with identical joint frame axes) corresponds to `newton:mimicCoef1 = +1` (or match the verified `newton:mimicCoef1` in `runnables/physics/newton.usda` when both layers share the same `body0`/`body1` joint frame orientation).
    - `newton:mimicCoef0` is authored in the follower joint's USD position units: **degrees** for revolute joints ($\text{deg}(\text{polycoef}[0])$) and stage distance units (meters) for prismatic joints. `newton:mimicCoef1` is dimensionless.
  - **Do not author a competing `MjcActuator` or non-zero USD drive spring on mimic followers**:
    - A mimic follower receives force through the equality constraint (`mjc:solref` / `mjc:solimp`) and must not have its own independent position `MjcActuator` targeting `0`.
    - If the neutral layer (`payloads/Physics/physics.usda`) authors non-zero raw `drive:<axis>:physics:stiffness` or `damping` on a follower joint (e.g., `174.53` on OnRobot RG2/RG6 follower joints), explicitly override `drive:<axis>:physics:stiffness = 0` and `drive:<axis>:physics:damping = 0` on the follower joint in `runnables/physics/mujoco.usda` so no residual spring fights the leader joint.
- **Closed-Loop 4-Bar / Parallel Linkages (`DJ.011`, `MUJOCO.DJ.001`, `MUJOCO.DJ.002`)**:
  - In a closed kinematic loop (such as 4-bar grippers like `Robotiq 2F-85` and `Yahboom/Dofbot`, or industrial arm parallel linkages `J2_link -(P1)-> P1_link -(P2)-> P2_link -(P2_01)-> J3_link`), the articulation subgraph (`physics:excludeFromArticulation = false`) must be a directed tree from parent (`body0`) to child (`body1`), and the loop-closing joint (`P2_01`, or spherical/fixed equality connect joints) must set `uniform bool physics:excludeFromArticulation = 1`.
  - In `runnables/physics/mujoco.usda`:
    1. On the loop-closing joint (`P2_01`), author `uniform bool physics:excludeFromArticulation = 1` and **do not** apply `MjcJointAPI` (only non-excluded articulation joints take `MjcJointAPI`).
    2. When a closed-loop linkage has an actuated primary joint on the loop (such as `finger_joint` in `Robotiq 2F-85`, `Finger_*_01_RevoluteJoint` in `Yahboom/Dofbot`, or `J3` in a 4-bar linkage) and holding the loop's actuated joint(s) leaves zero free passive motion dimensions under the excluded closure joint (`physics:excludeFromArticulation = true`), passive loop-only branch joints along that same loop keep `MjcJointAPI`, zero out any residual neutral `drive:<axis>:physics:stiffness = 0` and `damping = 0`, and require no dedicated `MjcActuator`.
    3. Do **not** prescribe affine `NewtonMimicAPI` / `MjcEqualityJointAPI` constraints (`q_follower = c0 + c1 * q_leader`) for general closed-loop linkages: a general non-parallelogram four-bar has a nonlinear kinematic relation between driver and passive branch angles, so adding a constant-ratio mimic constraint fights loop closure. Only author `NewtonMimicAPI` / `MjcEqualityJointAPI` when the source mechanism specification or a verified constant-ratio mechanism establishes that exact affine relation.
- **Fixed-Tendon Actuation (`MjcTendon`)**:
  - When a single motor drives symmetric coupled joints through a fixed tendon (such as `MjcTendon "split"` in `robotiq_2f85_v4`), author `def MjcTendon` with `uniform token mjc:type = "fixed"`, `rel mjc:path` listing the driven 1-DOF `MjcJointAPI` joints, `uniform int[] mjc:path:indices` (or omit / author `[]` to select all `mjc:path` entries in order), and `uniform double[] mjc:path:coef` with non-zero effective coefficients matching the selected entries (or omit / author `[]` for unit `1.0` coefficients), and point the `MjcActuator`'s `rel mjc:target` at the `MjcTendon` prim.

## Feature Guidance

- Repair only the requirements listed by the selected `CAP022_DrivenJoints.MuJoCo` manifest and its dependencies.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature (except the documented `NewtonMimicAPI` base inherited by `MjcEqualityJointAPI` and `NewtonCollisionAPI` base inherited by `MjcCollisionAPI`).
- Do not delete standard `UsdPhysics` joint topology or MuJoCo robot multibody data when repairing the current version; `CAP022_DrivenJoints.MuJoCo.0-1-0` depends on `CAP004_Multibody.RobotMuJoCo.0-1-0`.
- Do not delete `PhysicsDriveAPI` or joint-state schemas unless the selected validation report or user request explicitly asks for a MuJoCo-only overlay, but do zero out residual `drive:<axis>:physics:stiffness = 0` and `damping = 0` on mimic follower joints in `runnables/physics/mujoco.usda` when the neutral layer carries non-zero gains that would oppose the leader.
- Report missing MuJoCo runtime/tooling evidence as a validation limitation instead of claiming a runtime pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact contract ID, for example `CAP022_DrivenJoints.MuJoCo.0-1-0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact capability skill or user/runtime evidence needed. |
