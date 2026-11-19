# lidar_point_cloud  (FET036 RTX Sensors)

| Property     | Value                          |
|--------------|--------------------------------|
| Test name    | lidar_point_cloud              |
| Feature(s)   | FET036_Lidar.RTX         |
| Engine       | Kit / Isaac Sim (>=2024.2.0)   |
| Test version | 0.1.0                          |

## Running with simready-evaluate

This test ships in `simready-foundation-tier-sensors`, under the Python package
`simready.foundation.sensors.runtime_tests`.
Run it against an asset:

```bash
simready-evaluate --assets path/to/asset.usd --features FET036
```

The test skips automatically if no `OmniLidar` prim with `OmniSensorGenericLidarCoreAPI` is found, if no LiDAR sensor can be initialized, or if all LiDAR buffers are empty after the scan (environment limitation — GPU driver >= 576.x required for RTX LiDAR CUDA 12.9 support in Isaac Sim 6.0.1).

## Summary

Loads the asset, builds a scaled sarcophagus enclosure around each OmniLidar
prim, steps the simulation for one full LiDAR scan cycle, and confirms that each
prim produces a non-empty point cloud whose range values match the enclosure
geometry within 2% (per-return ray-box check).

## What Pass Guarantees

A reviewer, PM, or OEM can trust that the OmniLidar prim is correctly typed
and configured (using `OmniSensorGenericLidarCoreAPI` as required by LI.001)
so that Isaac Sim can initialize the sensor and produce range data that is
geometrically consistent with the surrounding scene. The asset
is ready for use in mapping, obstacle avoidance, or synthetic data generation
pipelines that depend on LiDAR output.

## What It Checks

Each OmniLidar prim is processed in its own isolated simulation cycle. After stepping the simulation for `scan_frames` (default 120) frames:

- **Point count:** the `GenericModelOutput` buffer must be non-empty (at least one point). If every sensor's buffer is empty, this is treated as an environment limitation and the test is skipped, not failed. If some sensors produce data and others do not, the empty sensors are a failure.
- **Range accuracy:** each return's measured range (`gmo.z`) is compared with the expected distance to the nearest enclosure wall, computed by ray-box intersection from the return's azimuth and elevation. A return is out of tolerance if its relative error exceeds 2%. Returns within 0.5° of an octant-boundary azimuth (multiples of 45°) are excluded from the error count but still count toward the total.
- **Failure threshold:** the sensor fails if the percentage of out-of-tolerance returns exceeds 1% when there are at least 100 returns, or 10% when there are fewer than 100.

The test does not check `min_range_m` and does not separately check for NaN or Inf values. If the asset has multiple OmniLidar prims, all are checked independently.

Key thresholds from `config_defaults`:

- `scan_frames`: 120 (frames run — RTX rendering needs more warmup than physics sensors)

## How It Works

The test uses `prim.GetMetadata("apiSchemas").GetAppliedItems()` alongside `prim.GetTypeName() == "OmniLidar"` to find all conforming LiDAR prims. If none are found, the test is skipped.

A sarcophagus enclosure of 16 axis-aligned cubes is created around each sensor's world position. Its size is scaled from the sensor's near and far range so that every direction has a unique, analytically known wall distance.

Each prim is wrapped with `Lidar(prim_path)` from `isaacsim.sensors.experimental.rtx` and a `LidarSensor` with a custom `GenericModelOutput` Writer is attached **before** simulation starts — the RTX pipeline requires early attachment.

Physics is driven using **direct API calls** (`omni.physx.get_physx_interface().start_simulation()` + `omni.timeline.get_timeline_interface().play()` + raw `next_update_async()` calls) rather than the framework's `ctx.physics_step()`. This is necessary because `ctx.physics_step()` pauses the timeline after the first frame to prevent multi-frame auto-advancement, which stops RTX sensor scan updates. RTX LiDAR sensors require the timeline to remain continuously playing to fire their scan callbacks.

The Writer collects the `GenericModelOutput` for each scan frame. After `scan_frames` frames the data is copied to numpy arrays and the sensor is destroyed. If all buffers are empty (GPU driver limitation), the test is skipped. Otherwise the per-return range check is applied to each sensor with data.

## Failure Cases

| Symptom | Likely cause |
|---|---|
| Range check failed (more than the allowed fraction of returns exceed 2% range error) | The emitter azimuth/elevation arrays are mis-authored, `numberOfEmitters` does not match the array lengths (see LI.002), or the sensor wiring is corrupted so returns do not match the enclosure geometry. Also check GPU driver >= 576.x. |
| One sensor produced no point cloud while sibling sensors did | A sensor-specific problem, not the shared GPU-driver limitation. Check that sensor's `nearRangeM`/`farRangeM`, emitter configuration, and placement. |
| All sensors empty (test skipped) | Environment limitation: GPU driver >= 576.x is required for RTX LiDAR CUDA 12.9 support in Isaac Sim 6.0.1. |
| No sensor could be initialized (test skipped) | RTX rendering may be unavailable in the environment. |
| Test skipped (not applicable) | No `OmniLidar` prim with `OmniSensorGenericLidarCoreAPI` was found. The asset does not contain a conforming LiDAR sensor. |

## How to Fix

If the range check fails, verify that the emitter azimuth and elevation arrays
(`omni:sensor:Core:emitterState:*:azimuthDeg` and `elevationDeg`) are correctly
authored, and that `omni:sensor:Core:numberOfEmitters` matches every array
length (LI.002).

If a single sensor produces no point cloud while others do, check its
`nearRangeM` and `farRangeM` and its placement relative to scannable geometry.

If a sensor returns no points, or every range is far off, check that the USDA
declares `metersPerUnit = 1` in its layer header. Without it, USD falls back
to 0.01 m/unit, which places the test enclosure out of sensor range and
produces zero returns. This applies to both rotary and solid-state sensors,
which are both wrapped with `Lidar(prim_path)`.

## Expected Result

The test saves an azimuth-vs-elevation scatter plot PNG to the run output
directory for each OmniLidar prim. The horizontal axis is azimuth (left =
leftmost beam, right = rightmost beam) and the vertical axis is elevation (top =
highest beam, bottom = lowest beam). Each dot is one LiDAR return, colored by
range (blue = near, red = far). The visual appearance depends on the sensor
type:

### Solid-state sensor (`OmniLidarSolidStateRTXPass.usda`)

![lidar-point-cloud solid-state expected result](../_images/lidar-point-cloud-solid-state.png)

A solid-state lidar fires a fixed rectangular grid of emitters. The result is a
fully-filled 2D rectangle — the sensor's complete scan pattern with no gaps.
The color gradient reflects varying distances to the sarcophagus walls placed
around the sensor during the test.

### Rotary sensor (`OmniLidarCheckerPass.usda`)

![lidar-point-cloud rotary expected result](../_images/lidar-point-cloud-rotary.png)

A rotary lidar sweeps 360° in azimuth at one or a small number of fixed
elevation angles. The result is one or more horizontal bands spanning the full
width of the image — one band per emitter elevation row. The color gradient
reflects varying distances to the sarcophagus walls at different azimuths.
