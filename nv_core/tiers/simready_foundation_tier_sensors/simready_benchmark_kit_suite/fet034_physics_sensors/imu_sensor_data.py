# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""FET_034 IMU sensor data check (PS.001).

WHAT: Verifies that IsaacImuSensor prims on the asset produce meaningful
      non-zero output during physics simulation.

  1. Traverse the stage for IsaacImuSensor typed prims.
     Skip if none found.

  2. Add a collision ground plane and start physics. Before play(),
     set an initial angular velocity on each sensor's parent rigid body
     so the angular_velocity channel has a signal from the first frame.

  3. Sample each IMUSensor every frame for simulation_frames steps,
     tracking the peak magnitude of angular_velocity and
     linear_acceleration across all sensors and all frames.

PASS/FAIL:
  - PASS: peak |angular_velocity| >= 0.05 rad/s AND
          peak |linear_acceleration| >= 0.5 m/s² (collision impulse).
  - FAIL: either signal is below threshold.
  - SKIP: no IsaacImuSensor prims found.

THRESHOLDS: 0.05 rad/s angular / 0.5 m/s² linear are conservative
            values well below the observed pass-fixture outputs
            (~0.09 rad/s and ~0.94 m/s²), leaving headroom for
            variation across assets and simulation environments.
"""
import csv
import math
import os

import numpy as np
from simready_benchmark.core.decorator import test

_MIN_ANG_VEL_RAD_S = 0.05
_MIN_LIN_ACC_MS2 = 0.5


def _save_imu_csv(sensor_prims, all_recordings, output_dir):
    """Write one CSV artifact containing IMU sensor time-series data.

    Columns: timecode, sensor_prim, lin_accel_x, lin_accel_y, lin_accel_z,
             ang_vel_x, ang_vel_y, ang_vel_z

    all_recordings: dict {sensor_index: [(ang_vel, lin_acc), ...]} per frame.
    Returns the written file path, or None on failure.
    """
    try:
        path = os.path.join(output_dir, "imu_sensor_recording.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timecode", "sensor_prim",
                "lin_accel_x", "lin_accel_y", "lin_accel_z",
                "ang_vel_x", "ang_vel_y", "ang_vel_z",
            ])
            for i, sensor_prim in enumerate(sensor_prims):
                prim_path = sensor_prim.GetPath().pathString
                for t, (ang, lin) in enumerate(all_recordings.get(i, [])):
                    lx, ly, lz = lin if lin else (0.0, 0.0, 0.0)
                    ax, ay, az = ang if ang else (0.0, 0.0, 0.0)
                    writer.writerow([t, prim_path, lx, ly, lz, ax, ay, az])
        return path
    except Exception:
        return None


def _find_imu_prims(stage):
    return [p for p in stage.Traverse() if p.GetTypeName() == "IsaacImuSensor"]


def _find_rigid_body_ancestor(prim):
    parent = prim.GetParent()
    while parent and parent.IsValid() and parent.GetPath().pathString not in ("/", ""):
        if "PhysicsRigidBodyAPI" in parent.GetAppliedSchemas():
            return parent
        parent = parent.GetParent()
    return None


def _vec_norm(vec):
    if vec is None:
        return 0.0
    try:
        return float(np.linalg.norm(np.array(vec, dtype=float)))
    except Exception:
        return 0.0


def _all_finite(vec):
    if vec is None:
        return False
    try:
        return all(math.isfinite(float(v)) for v in vec)
    except Exception:
        return False


@test(
    features=[{"id": "FET_034_ISAAC", "version": ">=0.1.0"}],
    name="imu_sensor_data",
    description=(
        "Simulates the asset under gravity with a ground plane and an initial "
        "angular velocity, then verifies that each IsaacImuSensor prim "
        "reports non-zero angular velocity and linear acceleration — confirming "
        "the sensor is correctly wired to a rigid body and the physics pipeline "
        "is functional."
    ),
    expected_video=(
        "No video output. A CSV artifact (imu_sensor_recording.csv) is saved to "
        "the run output directory with one row per sensor per simulation frame. "
        "Columns: timecode, sensor_prim, lin_accel_x, lin_accel_y, lin_accel_z, "
        "ang_vel_x, ang_vel_y, ang_vel_z."
    ),
    version="0.1.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "simulation_frames": 80,
        "initial_angular_velocity_y": 5.0,
    },
)
async def test_imu_sensor_data(ctx):
    """IMU sensor runtime data check — PS.001."""
    import omni.usd
    from isaacsim.sensors.experimental.physics import IMUSensor
    from pxr import Gf

    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    await ctx.settle()

    stage = omni.usd.get_context().get_stage()
    imu_prims = _find_imu_prims(stage)

    if not imu_prims:
        ctx.skip(
            "No IsaacImuSensor prims found. "
            "This test only runs on assets that declare an IMU sensor."
        )
        return

    ctx.log("Found %d IMU sensor prim(s): %s" % (len(imu_prims), ", ".join(p.GetPath().pathString for p in imu_prims)))
    ctx.add_metric("imu_sensor_count", len(imu_prims))

    # Ground plane gives the rigid body geometry to collide with, producing a
    # linear_acceleration spike when the asset falls and hits the floor.
    physics = ctx.scene.add_physics(gravity=9.81, fps=60.0)
    ctx.scene.enable_ground_plane(friction=0.5)
    await ctx.settle()

    # Set initial angular velocity on each sensor's parent rigid body so the
    # angular_velocity channel has a non-zero signal from the first frame,
    # independent of the falling duration.
    ang_vel_y = float(ctx.config["initial_angular_velocity_y"])
    for imu_prim in imu_prims:
        rb = _find_rigid_body_ancestor(imu_prim)
        if rb is not None:
            try:
                rb.GetAttribute("physics:angularVelocity").Set(Gf.Vec3f(0.0, ang_vel_y, 0.0))
            except Exception:
                pass  # attribute not typed — prim has no PhysicsRigidBodyAPI

    # Instantiate IMUSensor objects BEFORE simulation starts.
    sensors = []
    for imu_prim in imu_prims:
        try:
            sensors.append(IMUSensor(imu_prim.GetPath().pathString))
        except Exception as exc:
            ctx.log("Could not initialize IMUSensor at %s: %s" % (imu_prim.GetPath().pathString, exc))

    if not sensors:
        ctx.skip("No IMU sensors could be initialized.")
        return

    ctx.step("Running physics simulation (%d frames)" % ctx.config["simulation_frames"])
    physics.play()

    max_ang_vel = 0.0
    max_lin_acc = 0.0
    simulation_frames = int(ctx.config["simulation_frames"])
    # Per-sensor recording: list of (ang_vel, lin_acc) tuples per frame.
    recordings = {i: [] for i in range(len(sensors))}

    for _ in range(simulation_frames):
        await ctx.step_one()
        for i, sensor in enumerate(sensors):
            frame = sensor.get_data()
            ang = frame.get("angular_velocity")
            lin = frame.get("linear_acceleration")
            recordings[i].append((
                tuple(float(v) for v in ang) if ang is not None and _all_finite(ang) else None,
                tuple(float(v) for v in lin) if lin is not None and _all_finite(lin) else None,
            ))
            if ang is not None and _all_finite(ang):
                max_ang_vel = max(max_ang_vel, _vec_norm(ang))
            if lin is not None and _all_finite(lin):
                max_lin_acc = max(max_lin_acc, _vec_norm(lin))

    ctx.add_metric("imu_peak_angular_velocity_rad_s", round(max_ang_vel, 4))
    ctx.add_metric("imu_peak_linear_acceleration_ms2", round(max_lin_acc, 4))
    ctx.log("Peak |angular_velocity| = %.4f rad/s, peak |linear_acceleration| = %.4f m/s²" % (max_ang_vel, max_lin_acc))

    out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
    path = _save_imu_csv(imu_prims, recordings, out_dir)
    if path:
        ctx.log("Saved IMU recording: %s" % path)

    failed = False

    if max_ang_vel < _MIN_ANG_VEL_RAD_S:
        ctx.fail(
            "IMU sensor angular_velocity too small (%.4f rad/s < %.2f rad/s).\n\n"
            "How to fix:\n"
            "- Verify the IsaacImuSensor prim is a descendant of a prim with "
            "PhysicsRigidBodyAPI applied (PS.001).\n"
            "- Check that the sensor prim path is correctly wired in the asset USD." % (max_ang_vel, _MIN_ANG_VEL_RAD_S)
        )
        failed = True

    if max_lin_acc < _MIN_LIN_ACC_MS2:
        ctx.fail(
            "IMU sensor linear_acceleration too small (%.4f m/s² < %.2f m/s²).\n\n"
            "How to fix:\n"
            "- Verify the rigid body ancestor has a collision mesh "
            "(UsdPhysics.CollisionAPI) so the ground collision impulse is transmitted "
            "to the sensor.\n"
            "- Verify the IsaacImuSensor prim is a descendant of the rigid body root."
            % (max_lin_acc, _MIN_LIN_ACC_MS2)
        )
        failed = True

    if not failed:
        ctx.log("IMU sensor data PASSED.")
