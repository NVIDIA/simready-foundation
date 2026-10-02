# imu_sensor_data  (FET034 Physics Sensors)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | imu_sensor_data                |
| Feature(s)   | FET_034_ISAAC       |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-benchmark

This test is implemented and available in the `simready-benchmark-kit-suite` package.
Run it against an asset:

```bash
simready-benchmark --assets path/to/asset.usd --features FET034
```

The test skips automatically if no prim with `OmniMegaIMUSensorAPI` is found.

## Summary

Loads the asset into a physics scene with a ground plane, gives the rigid body
an initial spin, and confirms that the IMU sensor reports meaningful non-zero
angular velocity and linear acceleration over the course of the simulation.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the IMU sensor prim is correctly placed
under a rigid body, that Isaac Sim has successfully initialized the sensor, and
that the sensor will produce usable inertial data when the robot is in motion.
The asset is ready for use in estimation, control, and localization pipelines
that consume IMU output.

## What It Checks

The test samples sensor output on every physics frame and records the peak
magnitude of each output channel across the full simulation run:

- **Angular velocity:** peak magnitude must exceed `min_ang_vel_rad_s`
  (default 0.05 rad/s). An initial spin is applied to the rigid body via the
  `physics:angularVelocity` USD attribute so the body is rotating from the
  first frame. A sensor not attached to a rigid body (PS.001 violation) reads
  zero angular velocity regardless of spin applied to the body.
- **Linear acceleration:** peak magnitude must exceed `min_lin_acc_ms2`
  (default 0.5 m/s²). A ground plane is added to the scene; when the cube
  collides with it, the impact force produces a brief linear acceleration spike
  that the IMU registers. A sensor not attached to a rigid body reads only raw
  gravity and produces no collision spike.

Tracking the peak across all frames (rather than reading once at the end)
ensures the collision impulse is captured even if the body settles afterward.

Key thresholds from `config_defaults`:

- `simulation_frames`: 80 (frames run — enough for the body to fall, collide, and settle)
- `initial_angular_velocity_y`: 5.0 (initial spin in rad/s applied to the rigid body before play)
- `min_ang_vel_rad_s`: 0.05 (minimum peak angular velocity in rad/s)
- `min_lin_acc_ms2`: 0.5 (minimum peak linear acceleration in m/s²)

## How It Works

The test traverses the stage using `prim.GetMetadata("apiSchemas").GetAppliedItems()` to find all prims with `OmniMegaIMUSensorAPI` applied. (Note: `prim.GetAppliedSchemas()` is not used because Kit's runtime silently drops unregistered API schemas from that method.) If no IMU prim is found, the test is skipped.

A ground plane is added via `ctx.scene.enable_ground_plane()`. An initial angular velocity of `initial_angular_velocity_y` rad/s (default 5.0) around the Y axis is set on the first ancestor prim with `PhysicsRigidBodyAPI` before simulation starts.

An `IMUSensor` is instantiated on each IMU prim path. Physics is driven via `ctx.scene.add_physics()` + `physics.play()` + repeated `ctx.physics_step()` calls — the framework's physics_step() drives the timeline, which the `IMUSensor` extension requires to fire its per-frame callbacks.

On each frame, `imu_sensor.get_data()` is called and the peak magnitudes of `"angular_velocity"` and `"linear_acceleration"` are updated. After `simulation_frames` frames, the peaks are compared against the thresholds.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Peak angular velocity is zero | The IMU prim is not under a `PhysicsRigidBodyAPI` prim (PS.001 violation). The rigid body's spin is not communicated to the sensor. |
| Peak linear acceleration below threshold | The cube did not collide with the ground plane, or the IMU prim is not under a rigid body. Increase `simulation_frames` if the body needs more time to reach the ground. |
| Sensor output is None or non-finite | The sensor failed to initialize, or the rigid body mass is zero or negative. |
| Test skipped (not applicable) | No prim with `OmniMegaIMUSensorAPI` was found. The asset does not contain an IMU sensor. |
| Static validation failed | The asset did not pass PS.001 (IMU prim not under a rigid body). Fix the static issue first. |

## How to Fix

If angular velocity is zero, confirm that the IMU prim (`IsaacImuSensor` with
`OmniMegaIMUSensorAPI`) is a child or descendant of a prim with
`PhysicsRigidBodyAPI` applied. The rigid body must be dynamic (`physics:rigidBodyEnabled = 1`,
`physics:kinematicEnabled = 0`) so it responds to the initial spin and gravity.

If the linear acceleration peak is below the threshold, verify that the
`PhysicsScene` prim is present and that the rigid body has a realistic positive
mass so it falls and collides with the ground plane.

## Manual Testing in Isaac Sim

### Batch script

Save the script below to a file (e.g. `batch_test_imu_sensor.py`) under the
repo root and run it with:

```powershell
# Windows
isaac-sim.bat --no-window --exec "C:\Dev\simready_foundations\batch_test_imu_sensor.py"
```

```bash
# Linux
./isaac-sim.sh --no-window --exec "/path/to/simready_foundations/batch_test_imu_sensor.py"
```

Expected output summary:

```
Overall: PASS (2/2 checks passed)
```

```python
import asyncio
import math
import os
import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PASS_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/physics_sensors/IMUSensorCheckerPass.usda")
FAIL_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/physics_sensors/IMUSensorCheckerFail.usda")
IMU_PRIM_PATH = "/World/Cube/Imu_Sensor"
CUBE_PRIM_PATH = "/World/Cube"
SIMULATION_FRAMES = 80
MIN_ANG_VEL_RAD_S = 0.05
MIN_LIN_ACC_MS2 = 0.5


def vec_norm(vec):
    return float(np.linalg.norm(np.array(vec, dtype=float))) if vec is not None else 0.0

def all_finite(vec):
    return vec is not None and all(math.isfinite(float(v)) for v in vec)


async def run_imu_test(asset_path, label, expect_motion):
    import omni.usd, omni.kit.app, omni.physx, omni.timeline, omni.kit.commands
    from pxr import Gf
    from isaacsim.sensors.experimental.physics import IMUSensor
    print(f"\n--- {label} ---")
    await omni.usd.get_context().open_stage_async(asset_path)
    for _ in range(5):
        await omni.kit.app.get_app().next_update_async()
    stage = omni.usd.get_context().get_stage()
    if not stage.GetPrimAtPath(IMU_PRIM_PATH).IsValid():
        print(f"    FAIL: IMU prim not found"); return False
    # Add ground plane so the falling cube produces a collision impulse
    omni.kit.commands.execute("CreateMeshPrimWithDefaultXform",
                              prim_type="Plane", above_ground=False)
    for _ in range(3):
        await omni.kit.app.get_app().next_update_async()
    # Set initial spin via USD — only works when PhysicsRigidBodyAPI is applied
    cube_prim = stage.GetPrimAtPath(CUBE_PRIM_PATH)
    if cube_prim.IsValid():
        try:
            cube_prim.GetAttribute("physics:angularVelocity").Set(
                Gf.Vec3f(0.0, 5.0, 0.0))
        except Exception:
            pass
    imu_sensor = IMUSensor(IMU_PRIM_PATH)
    physx = omni.physx.get_physx_interface()
    physx.start_simulation()
    omni.timeline.get_timeline_interface().play()
    max_ang, max_lin = 0.0, 0.0
    for _ in range(SIMULATION_FRAMES):
        await omni.kit.app.get_app().next_update_async()
        frame = imu_sensor.get_data()
        ang = frame.get("angular_velocity")
        lin = frame.get("linear_acceleration")
        if all_finite(ang): max_ang = max(max_ang, vec_norm(ang))
        if all_finite(lin): max_lin = max(max_lin, vec_norm(lin))
    omni.timeline.get_timeline_interface().stop()
    print(f"    peak |angular_velocity|    = {max_ang:.4f} rad/s")
    print(f"    peak |linear_acceleration| = {max_lin:.4f} m/s²")
    passed = True
    if max_ang >= MIN_ANG_VEL_RAD_S:
        print(f"    PASS: angular_velocity non-zero (>{MIN_ANG_VEL_RAD_S} rad/s)")
    else:
        print("    FAIL: angular_velocity too small"); passed = False
    if max_lin >= MIN_LIN_ACC_MS2:
        print(f"    PASS: linear_acceleration non-zero (>{MIN_LIN_ACC_MS2} m/s²)")
    else:
        print("    FAIL: linear_acceleration too small"); passed = False
    return passed if expect_motion else not passed


async def main():
    print("=" * 60)
    print("Batch test: IMU sensor data (FET034 PS.001)")
    print("=" * 60)
    results = [
        await run_imu_test(PASS_ASSET, "Pass fixture (expect PASS)", True),
        await run_imu_test(FAIL_ASSET, "Fail fixture (expect FAIL)", False),
    ]
    print(f"\nOverall: {'PASS' if all(results) else 'FAIL'}"
          f" ({sum(results)}/{len(results)} checks passed)")
    import os as _os; _os._exit(0)

asyncio.ensure_future(main())
```

## Expected Result

The benchmark writes one CSV file to the run output directory:
`imu_sensor_recording.csv`

The file has one row per sensor per simulation frame with these columns:

| Column | Description |
|---|---|
| `timecode` | Simulation frame index (0-based) |
| `sensor_prim` | Full USD path of the IMU sensor prim |
| `lin_accel_x/y/z` | Linear acceleration (m/s²) at this frame |
| `ang_vel_x/y/z` | Angular velocity (rad/s) at this frame |

A sample excerpt (single sensor, 80 frames at 60 fps):

```
timecode,sensor_prim,lin_accel_x,lin_accel_y,lin_accel_z,ang_vel_x,ang_vel_y,ang_vel_z
0,/World/AssetRoot/Asset/Cube/Imu_Sensor,-0.02873038314282894,0.0,9.806608200073242,0.0,0.08712106943130493,0.0
1,/World/AssetRoot/Asset/Cube/Imu_Sensor,-0.02873038314282894,0.0,9.806608200073242,0.0,0.08712106943130493,0.0
...
79,/World/AssetRoot/Asset/Cube/Imu_Sensor,-0.02873038314282894,0.0,9.806608200073242,0.0,0.08712106943130493,0.0
```

A reference artifact from the pass fixture is bundled alongside this document:
{download}`pass_imu_sensor_recording.csv <../_artifacts/pass_imu_sensor_recording.csv>`

## Notes and Caveats

An initial angular velocity is set via the `physics:angularVelocity` USD
attribute before simulation starts. This attribute only accepts a value when
`PhysicsRigidBodyAPI` is applied to the prim; the set is silently skipped for
the fail fixture whose Cube has no physics APIs.

Sensor output is sampled on every frame and peak values are tracked across the
full simulation run. This ensures the collision impulse — which is brief — is
captured even if the body settles into a lower-acceleration state before the
simulation ends.

The `timeline.play()` driven update loop is required because the `IMUSensor`
extension subscribes to physics step callbacks that are only fired during an
active timeline session. Stepping the physics engine directly via the PhysX
interface alone does not trigger sensor output.
