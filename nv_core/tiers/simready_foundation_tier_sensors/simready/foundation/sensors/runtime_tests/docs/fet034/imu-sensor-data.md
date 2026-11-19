# imu_sensor_data  (FET034 Physics Sensors)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | imu_sensor_data                |
| Feature(s)   | FET034_ImuSensor.Isaac       |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-evaluate

This test ships in `simready-foundation-tier-sensors`, under the Python package
`simready.foundation.sensors.runtime_tests`.
Run it against an asset:

```bash
simready-evaluate --assets path/to/asset.usd --features FET034
```

The test skips automatically if no typed `IsaacImuSensor` prim is found.

## Summary

Loads the asset into a physics scene with a ground plane, gives the rigid body
an initial spin, and confirms that the IMU sensor reports meaningful non-zero
angular velocity and linear acceleration over the course of the simulation.

## What Pass Guarantees

Each discovered sensor initialized and returned at least one finite three-component
sample for each required channel during this run. The pooled peaks across all
sensors and frames met the angular-velocity and linear-acceleration criteria.
This is evidence for the tested stimulus and sampling window; it does not
establish accuracy, continuous availability, or suitability for every control
or localization workload. Static validation separately checks PS.001 wiring.

## What It Checks

The test samples sensor output on every physics frame. Each required sensor must
provide finite, non-empty three-component angular-velocity and linear-acceleration
samples somewhere in the current sampling window. Startup gaps are allowed;
missing, empty, or non-finite samples are unavailable evidence, not measured zero.
Channel vectors must have shape `(3,)` and real numeric components; strings,
objects, booleans, complex values, mappings, and other shapes do not establish
measurement availability. The same qualified numeric sample supplies availability,
peak calculations, and CSV values, so malformed frames remain blank if valid
measurements arrive later in the window.
If either channel remains unavailable for any sensor, the test reports an
execution error without asserting an asset violation.

Once channel availability is established, the test compares the peak magnitude
of each channel pooled across all sensors and frames:

- **Angular velocity:** peak magnitude must be at least 0.05 rad/s.
  An initial spin is authored through `physics:angularVelocity` before play.
- **Linear acceleration:** peak magnitude must be at least 0.5 m/s².
  The test adds gravity and a ground plane to exercise the physics response.
  It does not isolate collision acceleration from other contributions.

Tracking the peak across all frames (rather than reading once at the end)
ensures the collision impulse is captured even if the body settles afterward.

Configuration defaults and fixed criteria:

- `simulation_frames`: 80 (frames run — enough for the body to fall, collide, and settle)
- `initial_angular_velocity_y`: 5.0 (initial spin in rad/s applied to the rigid body before play; converted to deg/s for the USD attribute)
- Fixed angular-velocity criterion: 0.05 rad/s (sensor readback)
- Fixed linear-acceleration criterion: 0.5 m/s² (sensor readback)

## How It Works

The test traverses the stage for prims whose `GetTypeName()` is
`IsaacImuSensor`. If none are found, the test is skipped.

A ground plane is added via `ctx.scene.enable_ground_plane()`. An initial angular
velocity of `initial_angular_velocity_y` rad/s (default 5.0) around the Y axis
is converted to degrees/s, the unit UsdPhysics defines for `physics:angularVelocity`,
and written to that attribute on the nearest rigid-body ancestor before simulation
starts. Sensor angular-velocity readback is in radians/s.

An `IMUSensor` is instantiated on every discovered path. A constructor or required
setup/readback exception propagates with its cause as an execution error. Physics
is driven via `ctx.scene.add_physics()`, `physics.play()`, and repeated
`await ctx.step_one()` calls.

On each frame, `imu_sensor.get_data()` is called and the peak magnitudes of `"angular_velocity"` and `"linear_acceleration"` are updated. After `simulation_frames` frames, the peaks are compared against the thresholds.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Finite measured peak below threshold, including zero | The observed response did not meet the criterion. Inspect wiring, authored physics, and run diagnostics; the value alone does not establish the cause. |
| Required channel unavailable throughout the window | Execution error: measurement is incomplete. Inspect sensor/backend initialization and readback diagnostics before diagnosing the asset. |
| Setup or readback API exception | Execution error retaining the original cause; no measured asset verdict is established. |
| Test skipped | No typed `IsaacImuSensor` prim was found. |
| Static validation failed | The asset did not pass PS.001 (IMU prim not under a rigid body). Fix the static issue first. |

## How to Fix

For a measured low response, inspect whether the typed `IsaacImuSensor` is a
child or descendant of a prim with
`PhysicsRigidBodyAPI` applied. The rigid body must be dynamic (`physics:rigidBodyEnabled = 1`,
`physics:kinematicEnabled = 0`) so it responds to the initial spin and gravity.

If the linear acceleration peak is below the threshold, verify that the rigid
body has a realistic positive mass so it falls and collides with the ground plane.

## Expected Result

The evaluation writes one CSV file to the run output directory:
`imu_sensor_recording.csv`

The file has one row per sensor per simulation frame with these columns:

| Column | Description |
|---|---|
| `timecode` | Simulation frame index (0-based) |
| `sensor_prim` | Full USD path of the IMU sensor prim |
| `lin_accel_x/y/z` | Linear acceleration (m/s²) at this frame |
| `ang_vel_x/y/z` | Angular velocity (rad/s) at this frame |

Unavailable channel samples are blank in the CSV. Finite measured zero remains
`0.0`, so missing data cannot be mistaken for a stationary measurement.

A sample excerpt (single sensor, 80 frames at 60 fps):

```
timecode,sensor_prim,lin_accel_x,lin_accel_y,lin_accel_z,ang_vel_x,ang_vel_y,ang_vel_z
0,/World/AssetRoot/Asset/Cube/Imu_Sensor,2.384185791015625e-07,0.0,-9.5367431640625e-07,0.0,4.987510681152344,0.0
1,/World/AssetRoot/Asset/Cube/Imu_Sensor,-2.384185791015625e-07,0.0,9.5367431640625e-07,0.0,4.9833550453186035,0.0
...
79,/World/AssetRoot/Asset/Cube/Imu_Sensor,-0.00011531701602507383,-0.00012200344644952565,-9.809983253479004,0.0013220375403761864,0.00015256500046234578,-4.417340733198216e-06
```

A reference artifact from the pass fixture is bundled alongside this document:
{download}`pass_imu_sensor_recording.csv <../_artifacts/pass_imu_sensor_recording.csv>`

## Notes and Caveats

An initial angular velocity is set via the `physics:angularVelocity` USD
attribute before simulation starts. The configured rad/s value is converted to
degrees/s, the attribute's unit. If no rigid-body ancestor exists, there is no
stimulus target; PS.001 is checked by static validation. A write exception on
an existing target is an execution error.

Sensor output is sampled on every frame and peak values are tracked across the
full simulation run. This ensures the collision impulse — which is brief — is
captured even if the body settles into a lower-acceleration state before the
simulation ends.

The `timeline.play()` driven update loop is required because the `IMUSensor`
extension subscribes to physics step callbacks that are only fired during an
active timeline session. Stepping the physics engine directly via the PhysX
interface alone does not trigger sensor output.
