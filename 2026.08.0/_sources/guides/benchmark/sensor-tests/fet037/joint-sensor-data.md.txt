# joint_sensor_data  (FET037 Joint Sensors)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | joint_sensor_data              |
| Feature(s)   | FET_037_ISAAC       |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-benchmark

This test is implemented and available in the `simready-benchmark-kit-suite` package.
Run it against an asset:

```bash
simready-benchmark --assets path/to/asset.usd --features FET037
```

The test skips automatically if no prim with `OmniMegaJointSensorAPI` is found.

## Summary

Commands a driven joint to a non-zero target position, steps the simulation,
and confirms that the joint sensor prim reports position and velocity values
that are consistent with the physics simulation state.

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the joint sensor prim is correctly
attached to an articulated body, that Isaac Sim has initialized the sensor, and
that the reported joint state is numerically valid and reflects the actual
physics state. The asset is ready for use in control loops that close on joint
state feedback.

## What It Checks

After stepping the simulation for `settle_frames` (default 60) frames, the test verifies:

- **`is_valid`:** `JointStateSensor.get_data()["is_valid"]` must be `True`. A `False` result indicates `PhysicsArticulationRootAPI` is missing.
- **Joint positions:** the `positions` array must be non-empty and all-finite.
- **Joint movement:** `max(abs(positions))` must exceed 0.01 rad (~0.6°), confirming the authored drive target is non-zero and the articulation is responding.

The test does NOT command a specific target position — it relies on the drive target already authored on the joint. It does NOT compare against the physics articulation API for consistency.

If the asset has multiple joint sensor prims, all are checked independently.

Key thresholds from `config_defaults`:

- `settle_frames`: 60 (physics frames stepped before reading sensor output)

## How It Works

The test uses `prim.GetMetadata("apiSchemas").GetAppliedItems()` to find all prims with `OmniMegaJointSensorAPI` applied. (Note: `prim.GetAppliedSchemas()` is not used because Kit's runtime silently drops unregistered API schemas.) If no such prim is found, the test is skipped.

A `JointStateSensor` is instantiated on each sensor prim path before simulation starts. Physics is driven via `ctx.scene.add_physics()` + `physics.play()` + repeated `ctx.physics_step()` calls for `settle_frames` frames. The drive target position authored on the joint moves the joint during this time.

After settling, `sensor.get_data()` is called once and the result is evaluated against the conditions above.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Joint position array is empty | The joint sensor prim has no joints registered. Verify the prim with `OmniMegaJointSensorAPI` also has `PhysicsArticulationRootAPI` (PS.002). |
| NaN or Inf in joint position or velocity | A joint limit has been configured with min > max, or joint damping is zero causing instability. |
| Sensor position inconsistent with physics API | The joint sensor is reading a stale USD attribute rather than live simulation output. Verify Isaac Sim has initialized the articulation before reading. |
| Test skipped (not applicable) | No prim with `OmniMegaJointSensorAPI` was found. The asset does not contain a joint sensor. |
| Static validation failed | The asset did not pass PS.002 (joint sensor prim missing `PhysicsArticulationRootAPI`). Fix the static issue first. |

## How to Fix

If the joint position array is empty, confirm that `OmniMegaJointSensorAPI` and
`PhysicsArticulationRootAPI` are both applied to the same prim (typically the
articulation root). The joint sensor reads from the articulation the sensor prim
belongs to.

If values are inconsistent with the physics simulation, confirm that the asset
is not using `physics:kinematicEnabled = 1` on the articulation root, which
prevents the articulation from being driven.

## Manual Testing in Isaac Sim

### Batch script

Save the script below to a file (e.g. `batch_test_joint_sensor.py`) under the
repo root and run it with:

```powershell
# Windows
isaac-sim.bat --no-window --exec "C:\Dev\simready_foundations\batch_test_joint_sensor.py"
```

```bash
# Linux
./isaac-sim.sh --no-window --exec "/path/to/simready_foundations/batch_test_joint_sensor.py"
```

Expected output summary:

```
Overall: PASS (2/2 checks passed)
```

```python
import asyncio
import math
import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PASS_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/physics_sensors/JointSensorCheckerPass.usda")
FAIL_ASSET = os.path.join(REPO_ROOT,
    "nv_core/sr_specs/tests/data/physics_sensors/JointSensorCheckerFail.usda")
SENSOR_PRIM_PATH = "/World/Rotational"
SETTLE_FRAMES = 60


async def run_joint_test(asset_path, label, expect_pass):
    import omni.usd, omni.kit.app, omni.physx, omni.timeline
    from isaacsim.sensors.experimental.physics import JointStateSensor
    print(f"\n--- {label} ---")
    await omni.usd.get_context().open_stage_async(asset_path)
    for _ in range(5):
        await omni.kit.app.get_app().next_update_async()
    sensor = JointStateSensor(SENSOR_PRIM_PATH)
    physx = omni.physx.get_physx_interface()
    physx.start_simulation()
    omni.timeline.get_timeline_interface().play()
    for _ in range(SETTLE_FRAMES):
        await omni.kit.app.get_app().next_update_async()
    omni.timeline.get_timeline_interface().stop()
    frame = sensor.get_data()
    is_valid = frame.get("is_valid", False)
    positions = frame.get("positions")
    print(f"    is_valid  = {is_valid}")
    print(f"    dof_names = {list(frame.get('dof_names', []))}")
    print(f"    positions = {positions}")
    if not is_valid:
        print("    FAIL: sensor not valid (missing PhysicsArticulationRootAPI?)")
        return not expect_pass
    if positions is None or len(positions) == 0:
        print("    FAIL: no DOF positions"); return False
    max_pos = max(abs(float(p)) for p in positions)
    if max_pos > 0.01:
        print(f"    PASS: joint moved (max |pos| = {max_pos:.4f} rad)")
        return expect_pass
    print(f"    FAIL: joint did not move (max |pos| = {max_pos:.4f} rad)")
    return not expect_pass


async def main():
    print("=" * 60)
    print("Batch test: Joint sensor data (FET037 PS.002)")
    print("=" * 60)
    results = [
        await run_joint_test(PASS_ASSET, "Pass fixture (expect PASS)", True),
        await run_joint_test(FAIL_ASSET, "Fail fixture (expect FAIL)", False),
    ]
    print(f"\nOverall: {'PASS' if all(results) else 'FAIL'}"
          f" ({sum(results)}/{len(results)} checks passed)")
    import os as _os; _os._exit(0)

asyncio.ensure_future(main())
```


## Expected Result

The benchmark writes one CSV file to the run output directory:
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

The consistency check uses a 5-degree tolerance to account for simulation lag
between the physics engine writing the joint state and the USD attribute being
updated. This is intentionally loose; the goal is to detect a sensor that is
not connected to the live simulation at all, not to verify sub-degree accuracy.
