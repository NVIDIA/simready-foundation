# Benchmark Reference

This section documents every benchmark in the bundled FET suite: what each
test checks, what a passing result guarantees, how the test works, the failure modes, and how to fix a failing asset. Tests are organized by feature: each
family page lists the tests that validate that feature.

## What the Framework Does

Benchmarking runs as a pipeline: the planner selects the tests an asset is
eligible for, the runner executes them in the engine and captures frames and
logs, the stamper records the outcome on the asset, and the reporter aggregates
results into an HTML and JSON report. Refer to
[Pipeline and Stages](../pipeline.md) for the full pipeline, and to
[Running Tests](../running.md) to set up and run the tool.

## How to Read a Test Result

Each feature in a report carries one state. A feature is PASS when at least one
of its tests passed or was skipped and none failed; a feature whose applicable
tests are all skipped, such as a world-anchored asset, is reported as PASS. A
feature is FAIL when any of its tests failed. A feature is NEUTRAL when it is validated but has no benchmark
to run. A feature is VALIDATION_FAILED when it did not pass static validation, so
no benchmark was run for it. Refer to [Reading Reports](../reading-reports.md)
to interpret a full report.

## Test Families

:::{list-table}
:header-rows: 1
:widths: 20 80

* - Family
  - Validates
* - [FET001 Visual](fet001-visual.md)
  - Visual presence, surface normals, back-face culling, lighting response, and pivot placement.
* - [FET003 Physics](fet003-physics.md)
  - Rigid-body ground drop, slope drop, and resting stability.
* - [FET004 Multibody](fet004-multibody.md)
  - Multibody articulation and joint movement.
* - [FET005 Grasp](fet005-grasp.md)
  - Grasp, lift, shake, and release.
* - [FET022 Driven Joints](fet022-driven-joints.md)
  - Driven joint range, velocity, effort, mimic behavior, coordination, and inverse kinematics.
:::

```{toctree}
:maxdepth: 1
:hidden:

FET001 Visual <fet001-visual>
FET003 Physics <fet003-physics>
FET004 Multibody <fet004-multibody>
FET005 Grasp <fet005-grasp>
FET022 Driven Joints <fet022-driven-joints>
```
