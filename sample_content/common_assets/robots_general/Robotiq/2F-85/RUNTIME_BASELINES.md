# Robotiq 2F-85 runtime baselines

This document records reproducible FET022 and FET028 runtime baselines for the
SimReady 2F-85 asset. Generated reports and videos belong under `_testing/` and
must not be committed.

## Asset under test

Use the asset interface at:

```text
sample_content/common_assets/robots_general/Robotiq/2F-85/simready_usd/2F-85.usda
```

Run benchmarks serially (`--max-concurrent 1`) so the videos and joint telemetry
can be compared without cross-test GPU contention.

## PhysX reference baseline

```powershell
simready-benchmark.exe `
  --foundations-path C:\simready\simready_foundations `
  --assets C:\simready\simready_foundations\sample_content\common_assets\robots_general\Robotiq\2F-85\simready_usd `
  --features FET022 FET028 `
  --tests drive_gain_validation effort_limit full_range_sweep ik_target_reach jacobian_ik mimic_joint multi_joint_coordination state_accuracy velocity_limit gripper_close_lift_cube gripper_close_lift_sphere `
  --runtime isaac_sim `
  --max-concurrent 1 `
  --output-dir C:\simready\simready_foundations\_testing\physx_2f85_fet022_fet028_baseline `
  --no-stamp --format both
```

Expected FET022 reference behavior:

- `full_range_sweep` passes and reaches/holds both endpoints.
- `mimic_joint` passes.
- `drive_gain_validation`, `effort_limit`, `state_accuracy`, and
  `velocity_limit` pass.
- `ik_target_reach` and `jacobian_ik` skip because this is a standalone gripper,
  not an arm with an end-effector target.
- `multi_joint_coordination` skips because only one independently driven joint
  remains after mimic followers are excluded.

The FET028 cube and sphere results are retained as regression evidence even
when they fail. Their videos must show the complete open, descend, close, lift,
shake, and release sequence; a green verdict without that behavior is invalid.

## Newton comparison baseline

Use the same command with:

```text
--runtime isaac_sim_newton
--output-dir C:\simready\simready_foundations\_testing\newton_2f85_fet022_fet028_baseline
```

`full_range_sweep` must fail when `finger_joint` cannot reach and hold an
endpoint. The endpoint rest check is fatal by default. In the release-2026.07.1
baseline, Newton reported 36 violations in 36 hold frames at the upper target
while PhysX passed the same test. This difference is a real runtime/asset
behavior difference and must not be downgraded to a warning.

## Newton reference asset comparison

The public Newton asset `newton-physics/newton-assets/robotiq_2f85_v4` is useful
as a topology and tuning reference, but it is not directly FET022/FET028-ready:

- it uses an `MjcActuator` and fixed tendon rather than `PhysicsDriveAPI`, so the
  current Benchmark drive adapter classifies all six joints as passive;
- it does not author `isaac:robotType` or a FET028 gripper site;
- consequently FET022 full-range and both FET028 grasp tests skip without a
  SimReady adapter layer.

Its mechanical model also differs materially from the SimReady sample. The
Newton reference uses two driver joints coupled by one `NewtonMimicAPI`, passive
spring/follower joints, explicit loop-closure constraints, and a tendon
actuator. The SimReady sample currently couples five followers directly to one
master through linear mimic coefficients. The reference therefore indicates
that matching PhysX motion requires a topology/coupling revision, not another
round of stiffness and damping changes.

Do not copy the reference values blindly: its nested-body hierarchy, joint
frames, masses, inertias, and actuator contract differ from the flat SimReady
asset. Any adopted topology change must be staged as an asset revision and
revalidated against both runtimes.
