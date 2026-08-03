# SimReady Benchmark Overview

Benchmarking goes beyond schema validation. It opens a SimReady asset in
the target engine, NVIDIA Kit, or NVIDIA Isaac Sim, exercises it, and records
what happens. Schema validation, through the [SimReady Validation Workflow](../validate_workflow.md),
checks an asset against the SimReady requirements for a profile without running
the engine. Benchmarking catches behavior that schema validation cannot detect
before the asset reaches a production pipeline.

## The Tool and the Tests

Benchmarking is driven by the `simready-benchmark` tool. The bundled FET test
families are part of the SimReady Foundation and target NVIDIA Kit and NVIDIA
Isaac Sim. The `simready-benchmark` command discovers them from the foundation
automatically, so you do not need to install a separate test suite.

## Test Families

Each asset runs only the tests that its features and profiles call for.

The bundled suite groups tests into families by feature, as shown in the following table:

:::{list-table}
:header-rows: 1
:widths: 12 88

* - Family
  - Validates
* - [FET001](../../features/FET_001-minimal.md)
  - Visual presence, normals, back-face culling, and lighting.
* - [FET003](../../features/FET_003-rigid_body_physics.md)
  - Physics ground and slope drop, and resting stability.
* - [FET004](../../features/FET_004-simulate_multi_body_physics.md)
  - Multi-body and joint discovery and movement.
* - [FET005](../../features/FET_005-simulate_grasp_physics.md)
  - Grasp and lift, where a gripper grasps the asset and raises it.
* - [FET022](../../features/FET_022-driven_joints.md)
  - Driven joints: range, velocity, mimic behavior, coordination, and inverse kinematics (IK).
:::

## Relationship to Features and Profiles

Benchmarks are selected from the features and profiles an asset declares. This
is the same vocabulary used throughout the SimReady specification. A profile bundles
features, and each feature maps to the benchmarks that confirm it. Refer to
[Pipeline and Stages](pipeline.md) for how those declarations become a test plan.

## Next Steps

- [Pipeline and Stages](pipeline.md): how features and profiles become a test plan
- [Running Tests](running.md): set up `simready-benchmark`, configure the engine, and run tests
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [verify a clean pass](reading-reports.md#verify-a-clean-pass)
