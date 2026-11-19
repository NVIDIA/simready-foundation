# SimReady Evaluate Overview

Evaluation goes beyond schema validation. It opens a SimReady asset in
the target engine, NVIDIA Kit, or NVIDIA Isaac Sim, exercises it, and records
what happens. Schema validation, through the [SimReady Validation Workflow](../validate_workflow.md),
checks an asset against the SimReady requirements for a profile without running
the engine. Evaluation catches behavior that schema validation cannot detect
before the asset reaches a production pipeline.

## The Tool and the Tests

Evaluation is driven by the `simready-evaluate` tool. The bundled FET test
families are part of the SimReady Foundation and target NVIDIA Kit and NVIDIA
Isaac Sim. An installed Foundation tier advertises its catalogs and bundled
runtime-test package through the `simready.tier` entry point. During source
development, `--foundations-path` selects a Foundation checkout; `--tests-path`
is reserved for adding an independent unpublished test package.
[Running Tests](running.md) shows each workflow.

Core owns the PhysX runtime procedures. The separately installed Newton tier
owns Newton drop, multibody and driven-joint procedures; see
[Newton Runtime Tests](../../../../tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/runtime_tests/docs/runtime-tests.md) for its installation,
coverage, timing and backend limitations. Configuring a Newton engine alone
does not install that test provider, and Newton gripper close/lift contracts
are not currently provided.

## Test Families

Each asset runs only the tests selected by each caller-supplied, resolved
profile target.

The bundled suite groups tests into families by feature, as shown in the following table:

Family labels such as `FET001` are compact reporting groups and CLI filter
prefixes, not feature manifest IDs. Foundation 2 attributes runtime results
through each selected feature manifest's exact `<provider>:<test-name>`
`runtime_tests` bindings. Its dotted ID includes the contract version;
Foundation 1 instead matches legacy decorator IDs such as `FET_001_STANDARD`
and their version constraints. A family may span several runtime variants,
so never derive contract ownership from the family label alone.

:::{list-table}
:header-rows: 1
:widths: 12 88

* - Family
  - Validates
* - [FET001](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet001-visual.md)
  - Visual presence, normals, back-face culling, and lighting.
* - [FET003](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet003-physics.md)
  - Independent ground drop, sampled ground stability, and slope drop for Standard, PhysX, and Newton rigid bodies.
* - [FET004](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet004-multibody.md)
  - Multi-body and joint discovery and movement.
* - [FET005](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet005-grasp.md)
  - Grasp and lift, where a gripper grasps the asset and raises it.
* - [FET011](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet011-semantic-labels.md)
  - Semantic-label behavior in the RTX segmentation pipeline.
* - [FET022](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet022-driven-joints.md)
  - Driven joints: range, velocity, mimic behavior, coordination, and inverse kinematics (IK).
* - [FET028](../../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/runtime_tests/docs/fet028-gripper.md)
  - Gripper close, lift, shake, and drop.
:::

Only enabled tests registered by the bundled tier suite are documented here.
Use `simready-evaluate --list-tests` to inspect the tests available in the
current environment, including tests contributed by other installed tiers or
independent test packs.

## Relationship to Features and Profiles

Evaluations are selected from resolved feature and profile targets. This
is the same vocabulary used throughout the SimReady specification. A profile bundles
features, and each feature maps to the runtime tests that confirm it. Refer to
[Pipeline and Stages](pipeline.md) for how those declarations become a test plan.

## Next Steps

- [Pipeline and Stages](pipeline.md): how features and profiles become a test plan
- [Running Tests](running.md): set up `simready-evaluate`, configure the engine, and run tests
- [Reading Reports](reading-reports.md): interpret results, exit codes, and [verify a clean run](reading-reports.md#verify-a-clean-run)
