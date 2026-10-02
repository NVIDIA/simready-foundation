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
"""FET_037 Joint sensor data check (PS.002).

WHAT: Verifies that IsaacJointStateSensor prims on the asset report valid
      joint positions after the articulation drive has had time to move.

  1. Traverse the stage for IsaacJointStateSensor typed prims.
     JointStateSensor is constructed on the same prim (the articulation
     root) because IsaacJointStateSensor carries PhysicsArticulationRootAPI.
     Skip if none found.

  2. Start physics simulation. The authored drive target positions
     (physicsD6Drive:angular:targetPosition or equivalent) move each
     joint toward its target over settle_frames frames at 60 fps.

  3. After settling, read JointStateSensor.get_data():
     - is_valid must be True (requires PhysicsArticulationRootAPI).
     - max |position| must exceed 0.01 rad (~0.6 degrees) to confirm
       the drive is functional.

PASS/FAIL:
  - PASS: all sensors report is_valid=True and at least one joint
          has moved more than 0.01 rad.
  - FAIL: sensor is invalid (missing ArticulationRootAPI), or joint
          did not move (drive not configured or stiffness=0).
  - SKIP: no IsaacJointStateSensor prims found.
"""
import csv
import math
import os

from simready_benchmark.core.decorator import test

_MIN_MOVEMENT_RAD = 0.01


def _save_joint_csv(sensor_prims, all_recordings, all_dof_names, output_dir):
    """Write one CSV artifact containing joint sensor time-series data.

    One row per sensor per DOF per simulation frame.
    Columns: timecode, sensor_prim, dof_name, position_rad, velocity_rad_s

    all_recordings: dict {prim_path: [(positions, velocities), ...]} per frame.
    all_dof_names:  dict {prim_path: [name, ...]} DOF names per sensor.
    Returns the written file path, or None on failure.
    """
    try:
        path = os.path.join(output_dir, "joint_sensor_recording.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timecode", "sensor_prim", "dof_name", "position_rad", "velocity_rad_s"])
            for sensor_prim in sensor_prims:
                prim_path = sensor_prim.GetPath().pathString
                dof_names = all_dof_names.get(prim_path, [])
                for t, (pos, vel) in enumerate(all_recordings.get(prim_path, [])):
                    pos_list = list(pos) if pos else []
                    vel_list = list(vel) if vel else []
                    for j, dof in enumerate(dof_names):
                        p = pos_list[j] if j < len(pos_list) else ""
                        v = vel_list[j] if j < len(vel_list) else ""
                        writer.writerow([t, prim_path, dof, p, v])
        return path
    except Exception:
        return None


def _find_joint_sensor_prims(stage):
    return [p for p in stage.Traverse() if p.GetTypeName() == "IsaacJointStateSensor"]


@test(
    features=[{"id": "FET_037_ISAAC", "version": ">=0.1.0"}],
    name="joint_sensor_data",
    description=(
        "Simulates the asset under physics and reads JointStateSensor data "
        "from each IsaacJointStateSensor prim, verifying that the sensor "
        "reports valid joint positions and that the articulation drive moves "
        "at least one joint by more than 0.01 rad."
    ),
    expected_video=(
        "No video output. A CSV artifact (joint_sensor_recording.csv) is saved to "
        "the run output directory with one row per sensor per DOF per simulation "
        "frame. Columns: timecode, sensor_prim, dof_name, position_rad, velocity_rad_s."
    ),
    version="0.1.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "settle_frames": 60,
    },
)
async def test_joint_sensor_data(ctx):
    """Joint sensor runtime data check — PS.002."""
    import omni.usd
    from isaacsim.sensors.experimental.physics import JointStateSensor

    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])
    await ctx.settle()

    stage = omni.usd.get_context().get_stage()
    sensor_prims = _find_joint_sensor_prims(stage)

    if not sensor_prims:
        ctx.skip(
            "No IsaacJointStateSensor prims found. "
            "This test only runs on assets that declare a joint sensor."
        )
        return

    ctx.log(
        "Found %d joint sensor prim(s): %s"
        % (len(sensor_prims), ", ".join(p.GetPath().pathString for p in sensor_prims))
    )
    ctx.add_metric("joint_sensor_count", len(sensor_prims))

    physics = ctx.scene.add_physics(gravity=9.81, fps=60.0)
    await ctx.settle()

    # Construct JointStateSensor on the prim BEFORE simulation starts.
    sensors = []
    for prim in sensor_prims:
        prim_path = prim.GetPath().pathString
        try:
            sensors.append((prim_path, JointStateSensor(prim_path)))
        except Exception as exc:
            ctx.log("Could not initialize JointStateSensor at %s: %s" % (prim_path, exc))

    if not sensors:
        ctx.skip("No joint sensors could be initialized.")
        return

    ctx.step("Running physics simulation (%d frames)" % ctx.config["settle_frames"])
    physics.play()

    settle_frames = int(ctx.config["settle_frames"])
    # Per-sensor recording: list of (positions, velocities) tuples per frame.
    recordings = {prim_path: [] for prim_path, _ in sensors}

    for _ in range(settle_frames):
        await ctx.step_one()
        for prim_path, sensor in sensors:
            frame = sensor.get_data()
            pos = frame.get("positions")
            vel = frame.get("velocities")
            recordings[prim_path].append((
                tuple(float(v) for v in pos) if pos is not None else None,
                tuple(float(v) for v in vel) if vel is not None else None,
            ))

    # Read final frame for all sensors; collect dof_names, then write one USDA.
    out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
    final_frames = {pp: s.get_data() for pp, s in sensors}
    all_dof_names = {pp: list(f.get("dof_names", [])) for pp, f in final_frames.items()}
    path = _save_joint_csv(sensor_prims, recordings, all_dof_names, out_dir)
    if path:
        ctx.log("Saved joint recording: %s" % path)

    valid_count = 0
    all_passed = True

    for prim_path, sensor in sensors:
        frame = final_frames[prim_path]
        is_valid = frame.get("is_valid", False)
        positions = frame.get("positions")
        dof_names = all_dof_names[prim_path]

        ctx.log("  %s: is_valid=%s, dof_names=%s, positions=%s" % (
            prim_path, is_valid, dof_names, positions))

        if not is_valid:
            ctx.fail(
                "JointStateSensor at %s returned is_valid=False.\n\n"
                "How to fix:\n"
                "- Verify PhysicsArticulationRootAPI is applied to the "
                "IsaacJointStateSensor prim (PS.002).\n"
                "- Confirm at least one revolute or prismatic joint connects the "
                "articulation root to a child body." % prim_path
            )
            all_passed = False
            continue

        valid_count += 1

        if positions is None or len(positions) == 0:
            ctx.fail("JointStateSensor at %s: no DOF positions in reading." % prim_path)
            all_passed = False
            continue

        all_finite = all(math.isfinite(float(p)) for p in positions)
        if not all_finite:
            ctx.fail("JointStateSensor at %s: positions contain NaN or Inf." % prim_path)
            all_passed = False
            continue

        max_pos = max(abs(float(p)) for p in positions)
        ctx.add_metric(
            "joint_sensor_%d_max_position_rad" % sensors.index((prim_path, sensor)),
            round(max_pos, 4),
        )

        if max_pos > _MIN_MOVEMENT_RAD:
            ctx.log("  PASS: %s — joint moved (max |position| = %.4f rad)." % (prim_path, max_pos))
        else:
            ctx.fail(
                "JointStateSensor at %s: joint did not move "
                "(max |position| = %.4f rad < %.2f rad).\n\n"
                "How to fix:\n"
                "- Verify the joint has a drive target (physicsD6Drive:angular:targetPosition "
                "or physicsRevoluteJoint:driveTargetAngle) set to a non-zero value.\n"
                "- Verify drive stiffness and damping are non-zero." % (prim_path, max_pos, _MIN_MOVEMENT_RAD)
            )
            all_passed = False

    ctx.add_metric("joint_sensor_valid_count", valid_count)

    if all_passed:
        ctx.log("Joint sensor data PASSED.")
