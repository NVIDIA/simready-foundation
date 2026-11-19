# joint_sensor_data  (FET037 Joint Sensors)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | joint_sensor_data              |
| Feature(s)   | FET037_JointSensor.Isaac       |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-evaluate

This test ships in `simready-foundation-tier-sensors`, under the Python package
`simready.foundation.sensors.runtime_tests`.
Run it against an asset:

```bash
simready-evaluate --assets path/to/asset.usd --features FET037
```

The test skips automatically if no typed `IsaacJointStateSensor` prim is found.

## Summary

Loads the authored joint state, steps the simulation, records positions and
velocities, and checks the final sensor validity and finite, nonzero positions.
The procedure does not command targets or compare readback with an independent
physics-state measurement.

## What Pass Guarantees

The checked final readings have `is_valid=True`, non-empty finite positions,
and at least one absolute position above 0.01. Velocities are recorded but do
not have a separate validity or accuracy gate. An absolute final position does
not independently prove movement or agreement with live physics state.

The published `FET037_JointSensor.Isaac` feature promises live joint-state
output after drive target movement. This procedure provides the limited checks
above; it does not fully demonstrate that live movement/consistency promise.

## What It Checks

After stepping the simulation for `settle_frames` (default 60) frames, the test verifies:

- **`is_valid`:** `JointStateSensor.get_data()["is_valid"]` must be `True`. A `False` result requires investigation; PS.002 separately checks `PhysicsArticulationRootAPI`.
- **Joint positions:** the `positions` array must be non-empty and all-finite.
- **Nonzero position:** `max(abs(positions))` must exceed 0.01 (rad for angular DOFs, m for linear DOFs). This is an absolute-position gate, not a displacement or consistency comparison.

The test does NOT command a specific target position — it relies on the drive target already authored on the joint. It does NOT compare against the physics articulation API for consistency.

If the asset has multiple joint sensor prims, all are checked independently.

Key thresholds from `config_defaults`:

- `settle_frames`: 60 (physics frames stepped before reading sensor output)

## How It Works

The test traverses the stage for prims whose `GetTypeName()` is
`IsaacJointStateSensor`. If none are found, the test is skipped.

A `JointStateSensor` is instantiated on each sensor prim path before simulation
starts. Physics is driven via `ctx.scene.add_physics()`, `physics.play()`, and
repeated `await ctx.step_one()` calls for `settle_frames` frames. Any motion
depends on authored physics and drives; the procedure issues no target command.

The procedure records `sensor.get_data()` each frame, then reads a final frame
and evaluates it against the conditions above.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Joint position array is empty | No final DOF positions were returned; inspect sensor initialization and articulation wiring (PS.002). |
| NaN or Inf in final positions | The final position validity check failed; inspect physics and backend diagnostics. |
| Final absolute positions at or below 0.01 | The nonzero-position gate failed; inspect authored state and drives. |
| Test skipped | No typed `IsaacJointStateSensor` prim was found, or no sensor instance initialized. A construction skip is unavailable execution evidence, not proof that the feature is inapplicable. |
| Static validation failed | The asset did not pass PS.002 (joint sensor prim missing `PhysicsArticulationRootAPI`). Fix the static issue first. |

## How to Fix

If the joint position array is empty, confirm that the typed
`IsaacJointStateSensor` also carries `PhysicsArticulationRootAPI` (typically the
articulation root). The joint sensor reads from the articulation the sensor prim
belongs to.

For a low final absolute position, inspect the authored drive targets and
physics configuration. Establish live movement or readback consistency with
additional evidence; this test does not measure either independently.

## Expected Result

The evaluation writes one CSV file to the run output directory:
`joint_sensor_recording.csv`

The file has one row per sensor per DOF per simulation frame with these columns:

| Column | Description |
|---|---|
| `timecode` | Simulation frame index (0-based) |
| `sensor_prim` | Full USD path of the joint sensor prim |
| `dof_name` | Name of the DOF (matches the articulation drive target) |
| `position_rad` | Joint position (rad or m) at this frame |
| `velocity_rad_s` | Joint velocity (rad/s or m/s) at this frame |

A sample excerpt (single joint, 60 frames at 60 fps, target position ~π/2 rad):

```
timecode,sensor_prim,dof_name,position_rad,velocity_rad_s
0,/World/AssetRoot/Asset/JointStateSensor,articulatedRevoluteJoint1,0.3015534579753876,12.435399055480957
1,/World/AssetRoot/Asset/JointStateSensor,articulatedRevoluteJoint1,0.3015534579753876,12.435399055480957
...
59,/World/AssetRoot/Asset/JointStateSensor,articulatedRevoluteJoint1,0.3015534579753876,12.435399055480957
```

A reference artifact from the pass fixture is bundled alongside this document:
{download}`pass_joint_sensor_recording.csv <../_artifacts/pass_joint_sensor_recording.csv>`

## Notes and Caveats

There is no 5-degree consistency gate. A PASS establishes only the reported
final validity, finite positions, and absolute-position criterion for checked
sensors. Constructor failures are currently logged and omitted; inspect logs
for incomplete sensor coverage when more than one sensor is authored.
