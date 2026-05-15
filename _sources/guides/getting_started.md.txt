# SimReady Foundation

## Introduction

### What is SimReady Foundation?

Training a robot to grasp objects, generating synthetic data for perception
models, or building a digital twin of a warehouse all depend on the same thing:
simulation-ready 3D content. Today that content is fragile — an asset authored
for one physics engine often breaks in another, collision geometry is missing or
inconsistent, and there is no reliable way to know whether a USD file will
actually work before you load it into a simulator.

SimReady Foundation fixes this. It is an open specification layer on top of
OpenUSD that defines exactly what a simulation-ready asset must contain —
physics colliders, materials, joint structures, semantic labels — and ships two
frameworks to act on those definitions:

1. **Rules** — machine-checkable validation rules that verify whether an asset
  satisfies each requirement. Run them before any simulator touches the file to
   catch missing colliders, bad joint hierarchies, or incorrect material
   bindings early.
2. **Feature Adapters** — a conversion framework that transforms an asset from
  one profile to another (e.g. Neutral → PhysX) by applying only the
   mutations needed for features that differ between the two profiles.

Everything else in the foundation is specification: versioned **features** (each
backed by concrete **requirements** and rules), **capabilities** (the USD
properties each requirement checks), and **profiles** that compose features
into a complete simulation scenario (e.g. `Prop-Robotics-PhysX`,
`Robot-Core`). The spec is modular and extensible — new domains such as
deformable bodies, fluid interactions, or sensor models plug in as additional
features without breaking existing ones.

### Is SimReady Foundation useful to me?

SimReady operates entirely on **OpenUSD content** — every rule inspects USD
prims, attributes, and APIs; every feature adapter reads and writes USD stages;
every profile describes a set of USD-native capabilities. If your workflow
touches `.usd`, `.usda`, or `.usdc` files for simulation, the foundation
applies.


| If you are a…                                               | SimReady helps you…                                                                                                                                                                                                                                         |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Roboticist / Robot Software Engineer**                    | Run validation rules against your OpenUSD assets to confirm correct `CollisionAPI`, `RigidBodyAPI`, joint hierarchies, and mass properties before loading into a simulation application such as NVIDIA Isaac Sim — catch USD-level problems before runtime. |
| **3D Asset Creator / Technical Artist**                     | Author OpenUSD content against a base profile, run rules to validate USD structure and material bindings, and use feature adapters to produce runtime-specific USD variants without manual rework.                                                          |
| **AI / Simulation Engineer (Synthetic Data, World Models)** | Validate every USD asset in a pipeline with the rules framework so that composed USD stages for domain randomization and scene generation behave consistently at scale.                                                                                     |
| **Pipeline / Integration Engineer**                         | Structure CAD-to-OpenUSD conversion around SimReady features and run rule validation to guarantee that output USD files meet spec before entering production.                                                                                               |
| **Researcher / Domain Specialist**                          | Define new features and rules for emerging simulation domains and use them to evaluate whether OpenUSD content (or AI-generated USD output) meets the spec.                                                                                                 |


## Core specification concepts

SimReady Foundation is built on three concepts:

- **Capabilities** define *what OpenUSD properties* an asset must have. A
capability groups related requirements — each requirement has a unique ID
(e.g. `RB.COL.001`) and a machine-checkable rule that inspects USD prims,
attributes, or APIs (e.g. "every rigid shape must carry a `CollisionAPI`").
- **Features** define *what use case or behavior* an asset should produce in
simulation (e.g. "rigid-body physics," "grasp-ready colliders"). A feature
lists the capability requirements it needs, giving every rule a traceable
purpose. Features are versioned independently.
- **Profiles** combine required features into a named, versioned set that
represents a complete simulation scenario (e.g. `Prop-Robotics-PhysX`).
Validating an asset against a profile checks every feature — and therefore
every requirement and rule — in one pass.

### Why is the foundation structured this way?

Simulation content has a natural layering problem. At the bottom you need to
know *what USD properties an asset must carry*. In the middle you need to know
*why* those properties matter — they serve a use case such as "this object can
be grasped by a robot gripper." At the top you need to know *which collection
of use cases* a particular simulation scenario demands — a robotics prop scene
requires physics, grasp support, and semantic labels, but not articulated
joints.

Without explicit layers these concerns blur together and assets silently break
across pipelines. See each concept in depth:
[Features](features/features.md) |
[Capabilities](../capabilities/capabilities.md) |
[Profiles](profiles/profiles.md)

Each layer references the one below it, so any failure traces to the exact USD
property at fault — and new layers extend the spec without breaking existing
profiles.

To understand how new capabilities, features, and profiles move from an idea to
an accepted part of the specification, see the
[SimReady Acceptance Workflow](acceptance_workflow.md).

### Problems SimReady Foundation solves


| Problem                                                                                                                                              | Solution                                                                                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Validation fails with "asset invalid" — no way to trace *which* USD property is wrong.                                                               | Profile → Feature → Requirement → Rule. Every failure traces to the exact USD property at fault.                                          |
| Adding a new domain (e.g. deformable bodies) risks breaking unrelated profiles.                                                                      | New domains are added as new features. Existing profiles that do not reference them are unaffected.                                       |
| Two runtimes need mostly the same asset but differ on one aspect (e.g. neutral colliders vs. PhysX SDF). Maintaining separate assets is impractical. | Profiles share features and differ only where needed. Feature adapters convert the delta.                                                 |
| Updating a single rule forces a version bump on every profile that uses it.                                                                          | Capabilities, features, and profiles version independently. Update a rule without bumping profiles; pin a profile version for production. |


## Should I care about SimReady?

Work through these five questions. Each answer tells you whether SimReady
applies to your situation and exactly where to go next.

---

### Q1 — Do you work with 3D content for simulation?

> *This includes physics simulation, synthetic data generation, digital twins,
> robot training environments, or any workflow where 3D assets must behave
> correctly at runtime — not just look correct.*

- **Yes** — continue to Q2.
- **No / Not sure** — SimReady is specifically for simulation-ready OpenUSD
  content. If your work is purely visualization or rendering with no simulation
  requirements, the foundation may not apply today. You can still browse the
  [capabilities](../capabilities/capabilities.md) to see if upcoming
  domains are relevant.

---

### Q2 — What format are your assets in today?


| Your situation                                    | What to do                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Already in OpenUSD** (`.usd`, `.usda`, `.usdc`) | You can validate immediately. Jump to Q3.                                                                                                                                                                                                                                                                                                                                                            |
| **URDF** (common in robotics)                     | Import into USD using the [URDF Importer Extension](https://github.com/isaac-sim/urdf-importer-extension). See the [UR10 sample](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usda) for the expected USD output, and [rigid-body creators guide](../capabilities/physics_bodies/physics_rigid_bodies/creators.md) for details. Convert first, then continue to Q3. |
| **MJCF** (MuJoCo)                                 | See the [UR10 URDF source](../../../../sample_content/common_assets/robots_general/ur10/urdf/urdf/ur10.urdf) alongside its [SimReady USD output](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usda) for the conversion pattern. Convert first, then continue to Q3.                                                                                                              |
| **CAD (STEP, Fusion 360, etc.)**                  | Export to OpenUSD via [Omniverse CAD Converter](https://docs.omniverse.nvidia.com/extensions/latest/ext_cad-converter.html) or [Blender USD export](https://docs.blender.org/manual/en/latest/files/import_export/usd.html). See the [geometry creators guide](../capabilities/visualization/geometry/creators_overview.md) for supported CAD paths. Convert first, then continue to Q3.             |
| **Other formats**                                 | Convert to OpenUSD. The foundation validates USD content — the source format does not matter as long as the USD output is well-structured. Continue to Q3.                                                                                                                                                                                                                                           |


---

### Q3 — What kind of asset are you building?


| Asset type                                                               | Recommended profile                                                                                                                                                                                             | What it covers                                                                                                                                                               |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A robot arm, mobile robot, or articulated agent**                      | [Robot-Body-Neutral](../profiles/robot-body-neutral.md) or [Robot-Body-Runnable](../profiles/robot-body-runnable.md)                                                                                                  | Rigid-body physics, articulation, driven joints, base hierarchy. See the [UR10 sample](../../../../sample_content/common_assets/robots_general/ur10/simready_usd/ur10.usda). |
| **A prop or object in a robotics scene** (box, shelf, tool, etc.)        | [Prop-Robotics-Neutral](../profiles/prop-robotics-neutral.md) or [Prop-Robotics-PhysX](../profiles/prop-robotics-physx.md)                                                                                      | Rigid-body physics, multi-body simulation, grasp-ready colliders.                                                                                                            |
| **A robot or prop targeting a specific runtime** (e.g. NVIDIA Isaac Sim) | [Robot-Body-Isaac](../profiles/robot-body-isaac.md) or [Prop-Robotics-Isaac](../profiles/prop-robotics-isaac.md)                                                                                                | Everything above plus runtime-specific composition and adaptation.                                                                                                           |
| **Something else** (vehicle, deformable, environment)                    | Start with the [full profile list](../profiles/profiles.md) to see if an existing profile fits. If not, the spec is extensible — see the [Features Guide](features/features.md) for how to define new features. |                                                                                                                                                                              |


---

### Q4 — What do you need to do with the asset?


| Your goal                                                               | Where to go                                                                                                                                                 |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Validate** that an existing USD asset meets a profile                 | SimReady learning workflow — includes setup, running the validator, and reading results.                                                                    |
| **Author** a new asset from scratch                                     | Study the sample assets in `sample_content/common_assets/` for structure, then validate against your target profile.                                        |
| **Convert** an asset from one profile to another (e.g. Neutral → PhysX) | [Feature Adapters Guide](feature_adapters/feature_adapters.md) — covers the adapter framework and the `workspace upgrade` command.                          |
| **Extend** the spec with new requirements or features                   | [SimReady Learning Workflow](SimReady_learning_workflow.md) — walks through adding a requirement, rule, and feature end-to-end.                             |
| **Integrate** SimReady validation into a pipeline or CI system          | Start with the [SimReady Learning Workflow](SimReady_learning_workflow.md) to understand the validator, then integrate the validation step into your build. |


---

### Q5 — How many assets or runtimes are you targeting?


| Your scale                                               | Why SimReady pays off                                                                                                                         |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Single asset, single runtime**                         | Validation rules catch USD-level mistakes before you discover them in the simulator. Even for one asset, that saves debugging time.           |
| **Multiple assets, single runtime**                      | Every asset validates against the same profile, so you get consistency across your scene or dataset without manual spot-checks.               |
| **Same assets, multiple runtimes**                       | Author against a base (Neutral) profile and use feature adapters to produce runtime-specific variants. One source of truth, multiple outputs. |
| **Large-scale pipelines** (synthetic data, world models) | Pin a profile version for your production pipeline. New features or rules extend the spec without breaking your validated asset set.          |


---

**Still not sure?** Browse the [full profile comparison](../profiles/profiles.md)
to see what the foundation covers today, or jump into the
[SimReady Learning Workflow](SimReady_learning_workflow.md) to try it hands-on
with the sample validator.

## Terminology & Concepts

- Refer to the [Guides](guides.md).

