# Benchmark Reference

This section documents every benchmark in the bundled FET suite: what each
test checks, what a passing result guarantees, how the test works, what failure modes to expect, and how to fix a failing asset. Tests are organized by feature: each
family page lists the tests that validate that feature.

## Family Labels and Feature Manifest IDs

Names such as `FET001`, `FET003`, and `FET004` identify benchmark families.
They are compact reporting groups and accepted CLI filter prefixes; they are
not canonical Foundation feature manifest IDs.

A family can map to one or more runtime-specific feature variants:

:::{list-table}
:header-rows: 1
:widths: 20 80

* - Benchmark family
  - Example canonical feature manifest IDs
* - `FET001`
  - `FET_001_STANDARD`
* - `FET003`
  - `FET_003_STANDARD`, `FET_003_PHYSX`, `FET_003_NEWTON`
* - `FET004`
  - `FET_004_STANDARD`, `FET_004_PHYSX`, `FET_004_NEWTON`
:::

The executable association is declared by each test's
`@test(features=[...])` metadata. Planning and audit tools must resolve those
exact canonical IDs and version constraints against the feature catalog. They
must not construct a manifest ID from a family heading, directory, or filename.
For example, `FET001` correctly resolves to the `FET_001_STANDARD` manifests;
no manifest with the bare ID `FET001` is expected.

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
  - Rigid-body ground drop with settling, and slope drop.
* - [FET004 Multibody](fet004-multibody.md)
  - Multibody articulation and joint movement.
* - [FET005 Grasp](fet005-grasp.md)
  - Grasp, lift, shake, and release.
* - [FET011 Semantic Labels](fet011-semantic-labels.md)
  - Labelled and stripped semantic-segmentation evidence.
* - [FET022 Driven Joints](fet022-driven-joints.md)
  - Driven joint range, velocity, effort, mimic behavior, coordination, and inverse kinematics.
* - [FET028 Gripper](fet028-gripper.md)
  - Gripper close, lift, shake, and release.
:::

This reference lists enabled tests discovered from the bundled suite. Experimental
or disabled test implementations are not shipped coverage and are intentionally
omitted.

## Maintainer Documentation

- [Authoring SimReady Foundation runtime tests](authoring.md)
- [Experimental and disabled runtime tests](experimental.md)

```{toctree}
:maxdepth: 1
:hidden:

FET001 Visual <fet001-visual>
FET003 Physics <fet003-physics>
FET004 Multibody <fet004-multibody>
FET005 Grasp <fet005-grasp>
FET011 Semantic Labels <fet011-semantic-labels>
FET022 Driven Joints <fet022-driven-joints>
FET028 Gripper <fet028-gripper>
Authoring runtime tests <authoring>
Experimental and disabled tests <experimental>
```
