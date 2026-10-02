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
"""FET_036 LiDAR point cloud check (LI.001).

WHAT: Verifies that OmniLidar prims on the asset produce a non-empty point
      cloud with geometrically plausible range values after one RTX scan cycle.

  1. Traverse the stage for OmniLidar prims with OmniSensorGenericLidarCoreAPI.
     Skip if none found.

  2. For each sensor, build a scaled sarcophagus enclosure (16 axis-aligned
     cubes in 4 quadrant groups) centered on the sensor's world position.
     The sarcophagus geometry is adapted from the Isaac Sim RTX sensor test
     suite (isaacsim.sensors.experimental.rtx/tests/common.py). Asymmetric
     wall distances per quadrant make the per-return range check analytically
     unique in every direction.

  3. Wrap each OmniLidar prim with Lidar() from
     isaacsim.sensors.experimental.rtx (no config= arg — wraps the existing
     authored prim). Attach a LidarSensor with a custom GMO Writer. The
     Writer's write() is called event-driven for every scan output frame,
     eliminating the polling/frame-drop problem of the deprecated
     LidarRtx.get_current_frame() approach.

  4. Run the simulation for scan_frames (default 120) frames with the
     timeline continuously playing. RTX sensor scan callbacks require an
     unpaused timeline; ctx.physics_step() is not used because it pauses
     the timeline after the first frame.

  5. For each sensor: parse the collected GenericModelOutput buffer with
     parse_generic_model_output_data. Perform a per-return range check via
     ray-box intersection against the sarcophagus geometry. Require fewer than
     1% of returns to exceed 2% range error.

PASS/FAIL/SKIP:
  - PASS: every initialized sensor returns a non-empty point cloud whose
          returns land within 2% of the expected sarcophagus wall distance
          (≥99% of non-edge returns).
  - FAIL: a sensor returns data but the range distribution is geometrically
          implausible (>1% of returns exceed 2% error), indicating
          misconfigured emitter state or corrupted sensor wiring.
  - SKIP: no qualifying OmniLidar prims, or all GMO buffers empty after
          scan_frames (environment limitation — GPU driver >= 576.x
          required for RTX LiDAR CUDA 12.9 support in Isaac Sim 6.0.1).
"""
import os

import numpy as np
from simready_benchmark.core.decorator import test

# ---------------------------------------------------------------------------
# Point cloud image artifact
# ---------------------------------------------------------------------------


def _save_point_cloud_image(gmo_np, prim_name, output_dir):
    """Save an azimuth-vs-elevation scatter plot of the GMO data as a PNG.

    X axis = azimuth (degrees), Y axis = elevation (degrees, top=up).
    Each dot is one LiDAR return, colored by range (blue=near, red=far).
    For a solid-state sensor the result is a filled rectangle — the complete
    scan pattern. For a rotary sensor it is a horizontal band (full 360°
    azimuth sweep at the emitter elevation angles).

    The image is written to ``output_dir`` if provided; the path is returned.
    Returns None on failure (PIL unavailable, empty data, write error).
    """
    try:
        from PIL import Image

        az_deg = gmo_np["x"]
        el_deg = gmo_np["y"]
        r = gmo_np["z"]

        if len(r) == 0:
            return None

        IMG_SIZE = 512
        margin = 24
        draw_size = IMG_SIZE - 2 * margin

        az_span = (az_deg.max() - az_deg.min()) or 1.0
        el_span = (el_deg.max() - el_deg.min()) or 1.0

        ix = np.clip(
            ((az_deg - az_deg.min()) / az_span * draw_size + margin).astype(int),
            0,
            IMG_SIZE - 1,
        )
        iy = np.clip(
            ((el_deg.max() - el_deg) / el_span * draw_size + margin).astype(int),
            0,
            IMG_SIZE - 1,
        )

        r_norm = (r - r.min()) / (r.max() - r.min() + 1e-6)
        colors = np.stack(
            [
                (r_norm * 255).astype(np.uint8),
                (np.sin(r_norm * np.pi) * 200).astype(np.uint8),
                ((1 - r_norm) * 255).astype(np.uint8),
            ],
            axis=1,
        )

        img = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                rows = np.clip(iy + dy, 0, IMG_SIZE - 1)
                cols = np.clip(ix + dx, 0, IMG_SIZE - 1)
                img[rows, cols] = colors

        safe_name = prim_name.strip("/").replace("/", "_")
        filename = "lidar_point_cloud_%s.png" % safe_name
        path = os.path.join(output_dir, filename)
        Image.fromarray(img, "RGB").save(path)
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sarcophagus geometry constants
# ---------------------------------------------------------------------------
# Adapted from the Isaac Sim RTX sensor test suite (common.py).
# Each tuple (l, h1, h2) defines one XY quadrant group of the enclosure.
# All values are at unit scale (wall_dist / 10.0 = 1.0); multiply by the
# computed scale to adapt to the sensor's actual near/far range.
_SARCOPHAGUS_DIMS = [(10, 5, 7), (15, 9, 11), (20, 13, 15), (25, 17, 19)]

# Per-octant half-dimensions (x, y, z) at unit scale, derived from
# _SARCOPHAGUS_DIMS. Each octant row maps to one of the 8 sign combinations
# (+/-X, +/-Y, +/-Z). See test_lidar_sensor.py in the isaac-sim repo.
_OCTANT_DIMS_UNIT = np.array(
    [
        (10, 10, 5),  # +X +Y +Z
        (10, 10, 7),  # +X +Y -Z
        (25, 25, 17),  # +X -Y +Z
        (25, 25, 19),  # +X -Y -Z
        (15, 15, 9),  # -X +Y +Z
        (15, 15, 11),  # -X +Y -Z
        (20, 20, 13),  # -X -Y +Z
        (20, 20, 15),  # -X -Y -Z
    ],
    dtype=np.float64,
)

# Exclude returns whose azimuth is within this many degrees of an octant
# boundary (45° multiples) to avoid edge artefacts in the range check.
_NEAR_EDGE_DEG = 0.5

# Writer class is registered once per Kit process.
_WRITER_REGISTERED = False


# ---------------------------------------------------------------------------
# USD schema helpers
# ---------------------------------------------------------------------------


def _schema_applied(prim, schema_name):
    """Check for an applied API schema using raw USD metadata.

    GetAppliedSchemas() silently drops unregistered schemas in Kit's runtime.
    GetMetadata("apiSchemas").GetAppliedItems() reads the composed layer
    metadata directly and is always authoritative.
    """
    metadata = prim.GetMetadata("apiSchemas")
    if metadata is None:
        return False
    try:
        return schema_name in metadata.GetAppliedItems()
    except Exception:
        return False


def _find_lidar_prims(stage):
    return [
        p
        for p in stage.Traverse()
        if p.GetTypeName() == "OmniLidar" and _schema_applied(p, "OmniSensorGenericLidarCoreAPI")
    ]


def _read_sensor_ranges(prim):
    """Return (near_m, far_m) from OmniSensorGenericLidarCoreAPI.

    Checks array attributes first (rangesMinM / rangesMaxM), then falls back
    to scalar attributes (nearRangeM / farRangeM) used by sensors converted
    from JSON configs, then to hard-coded defaults (0.1, 30.0).
    """
    near, far = 0.1, 30.0

    # Array form (rangesMinM / rangesMaxM) — preferred
    for attr_name, is_near in [
        ("omni:sensor:Core:rangesMinM", True),
        ("omni:sensor:Core:rangesMaxM", False),
    ]:
        attr = prim.GetAttribute(attr_name)
        if attr:
            val = attr.Get()
            if val and len(val) > 0:
                if is_near:
                    near = float(val[0])
                else:
                    far = float(val[0])

    # Scalar fallback (nearRangeM / farRangeM) for JSON-derived sensors
    if near == 0.1:
        attr = prim.GetAttribute("omni:sensor:Core:nearRangeM")
        if attr:
            val = attr.Get()
            if val is not None:
                near = float(val)
    if far == 30.0:
        attr = prim.GetAttribute("omni:sensor:Core:farRangeM")
        if attr:
            val = attr.Get()
            if val is not None:
                far = float(val)

    return near, far


def _compute_wall_dist(near, far):
    """Derive enclosure wall distance from sensor near/far range."""
    wall_dist = max(near * 2.0, 0.5)
    wall_dist = min(wall_dist, far * 0.8)
    if wall_dist <= near:
        wall_dist = near + 0.1
    return wall_dist


# ---------------------------------------------------------------------------
# Sarcophagus scene geometry
# ---------------------------------------------------------------------------


def _create_sarcophagus(stage, sensor_pos, scale):
    """Create (or replace) the 16-cube sarcophagus at fixed prim paths.

    All sensors reuse the same 16 prim paths. Existing prims are removed
    before recreation so stale xform ops from the previous sensor do not
    accumulate and prior geometry never contaminates the next sensor's scan.

    Args:
        stage: Active USD stage.
        sensor_pos: World position of the sensor (Gf.Vec3d).
        scale: Sarcophagus scale factor = wall_dist / 10.0.
    """
    from pxr import Gf, UsdGeom

    sx = float(sensor_pos[0])
    sy = float(sensor_pos[1])
    sz = float(sensor_pos[2])
    thick = scale

    for i, (l_u, h1_u, h2_u) in enumerate(_SARCOPHAGUS_DIMS):
        wl = l_u * scale
        h1 = h1_u * scale
        h2 = h2_u * scale
        h = h1 + h2

        x_sign = -1 if 0 < i < 3 else 1
        y_sign = -1 if i > 1 else 1

        surfaces = [
            ([x_sign * (wl + thick / 2), y_sign * wl / 2, h1 - h / 2], [thick, wl, h]),
            ([x_sign * wl / 2, y_sign * (wl + thick / 2), h1 - h / 2], [wl, thick, h]),
            ([x_sign * wl / 2, y_sign * wl / 2, h1 + thick / 2], [wl, wl, thick]),
            ([x_sign * wl / 2, y_sign * wl / 2, -h2 - thick / 2], [wl, wl, thick]),
        ]

        for j, (rel, cs) in enumerate(surfaces):
            path = "/World/LidarSarc_%d_%d" % (i, j)
            if stage.GetPrimAtPath(path).IsValid():
                stage.RemovePrim(path)
            cube = UsdGeom.Cube.Define(stage, path)
            cube.GetSizeAttr().Set(1.0)
            xf = UsdGeom.Xformable(cube.GetPrim())
            xf.AddTranslateOp().Set(Gf.Vec3d(sx + rel[0], sy + rel[1], sz + rel[2]))
            xf.AddScaleOp().Set(Gf.Vec3f(*cs))


# ---------------------------------------------------------------------------
# Per-return range validation
# ---------------------------------------------------------------------------


def _check_range(gmo_np, scale):
    """Validate GMO returns against the sarcophagus geometry.

    Accepts a plain dict {x, y, z, numElements} of numpy float64 arrays,
    copied from the GMO before the sensor was destroyed. Accessing Warp/CUDA
    arrays after _invalidate_sensor() causes a crash; the copy must happen
    first.

    gmo_np["x"] = azimuth (degrees), gmo_np["y"] = elevation (degrees),
    gmo_np["z"] = range (meters), all in world frame.

    Returns:
        (passed, pct_exceeding, num_returns)
    """
    n = int(gmo_np["numElements"])
    if n == 0:
        return False, 0.0, 0

    az = gmo_np["x"]
    el = gmo_np["y"]
    measured = gmo_np["z"]

    # Unit direction vectors (canonical Isaac Sim formula, then normalize)
    unit_vecs = np.stack(
        [np.cos(np.radians(az)), np.sin(np.radians(az)), np.sin(np.radians(el))],
        axis=1,
    )
    unit_vecs /= np.linalg.norm(unit_vecs, axis=1, keepdims=True)

    # Octant index: bit 2 = x<0, bit 1 = y<0, bit 0 = z<0
    octant = (
        (unit_vecs[:, 0] < 0).astype(int) * 4
        + (unit_vecs[:, 1] < 0).astype(int) * 2
        + (unit_vecs[:, 2] < 0).astype(int)
    )
    dims = _OCTANT_DIMS_UNIT[octant] * scale  # (N, 3)

    # Expected range = nearest wall via ray-box intersection
    with np.errstate(divide="ignore"):
        ratio = dims / np.abs(unit_vecs)
    expected = np.min(ratio, axis=1)

    # Exclude returns near octant-boundary azimuths (45° multiples)
    edges = np.arange(-180, 181, 45)
    az_diff = np.abs(az[:, None] - edges[None, :])
    near_edge = np.any(az_diff < _NEAR_EDGE_DEG, axis=1)
    check_mask = ~near_edge

    pct_diffs = np.abs(expected - measured) / np.maximum(expected, 1e-6)
    num_exceeding = int(np.sum(pct_diffs[check_mask] > 0.02))
    pct_exceeding = num_exceeding / n * 100.0
    valid_threshold = 1.0 if n >= 100 else 10.0

    return pct_exceeding <= valid_threshold, pct_exceeding, n


# ---------------------------------------------------------------------------
# Benchmark test
# ---------------------------------------------------------------------------


@test(
    features=[{"id": "FET_036_RTX", "version": ">=0.1.0"}],
    name="lidar_point_cloud",
    description=(
        "Wraps each OmniLidar prim (OmniSensorGenericLidarCoreAPI required)"
        " with the experimental Lidar API, creates a scaled sarcophagus"
        " enclosure around the sensor, runs the simulation for a scan cycle,"
        " and validates that each sensor returns a non-empty point cloud"
        " whose range values match the enclosure geometry within 2% tolerance"
        " (per-return ray-box check)."
    ),
    expected_video=(
        "No video output. A PNG image artifact is saved to the run output"
        " directory: an azimuth-vs-elevation scatter plot of each sensor's"
        " GenericModelOutput data, colored by range (blue=near, red=far)."
        " For solid-state sensors the plot shows a filled rectangle (complete"
        " scan pattern); for rotary sensors a horizontal band (full 360°"
        " azimuth sweep). Point counts and range accuracy are also reported"
        " as metrics."
    ),
    version="0.2.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults={
        "asset_load_timeout": 30,
        "scan_frames": 120,
    },
)
async def test_lidar_point_cloud(ctx):
    """LiDAR RTX point cloud runtime check — LI.001."""
    global _WRITER_REGISTERED

    import omni.kit.app
    import omni.physx
    import omni.replicator.core as rep
    import omni.timeline
    import omni.usd
    from isaacsim.sensors.experimental.rtx import (
        Lidar,
        LidarSensor,
        parse_generic_model_output_data,
    )
    from omni.replicator.core import Writer
    from pxr import Usd, UsdGeom

    # Define and register the GMO collector Writer (once per process).
    # attach_writer() returns the writer instance in Isaac Sim 6.1+.
    # The writer populates _results[sensor_key] on each scan frame.
    class _LidarGmoCollector(Writer):
        # rep.writers.get() returns a singleton — dispatch by render-product
        # path so re-initialize() calls don't clobber the first sensor's key.
        def __init__(self, rp_to_key=None):
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get("GenericModelOutput")]
            self._results = {}
            self._rp_to_key = rp_to_key if rp_to_key is not None else {}

        def write(self, data):
            if "renderProducts" not in data:
                return
            for rp_path, rp_data in data["renderProducts"].items():
                # Replicator passes the RP basename in write() but we store
                # the full path — normalise to basename on both sides.
                rp_key = rp_path.rsplit("/", 1)[-1]
                key = self._rp_to_key.get(rp_key)
                if key is None:
                    continue
                raw = rp_data.get("GenericModelOutput")
                if isinstance(raw, dict):
                    raw = raw.get("data")
                gmo = parse_generic_model_output_data(raw)
                if gmo.numElements > 0:
                    self._results[key] = gmo

    if not _WRITER_REGISTERED:
        rep.WriterRegistry.register(_LidarGmoCollector)
        _WRITER_REGISTERED = True

    # Load asset and find lidar prims.
    timeout = ctx.config["asset_load_timeout"]
    ctx.scene.load_asset(ctx.asset_path, timeout=timeout)
    await ctx.settle()

    stage = omni.usd.get_context().get_stage()
    lidar_prims = _find_lidar_prims(stage)

    if not lidar_prims:
        ctx.skip(
            "No LiDAR sensor prims found (no OmniLidar prims with "
            "OmniSensorGenericLidarCoreAPI). "
            "This test only runs on assets that declare a conforming "
            "LiDAR sensor."
        )
        return

    prim_paths_str = ", ".join(p.GetPath().pathString for p in lidar_prims)
    ctx.log("Found %d LiDAR prim(s): %s" % (len(lidar_prims), prim_paths_str))
    ctx.add_metric("lidar_count", len(lidar_prims))

    xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    scan_frames = int(ctx.config["scan_frames"])

    all_passed = True
    all_empty = True
    total_points = 0
    any_initialized = False
    missing_sensors = []

    # Process each sensor in its own isolated simulation cycle.
    # Replicator only drives the last-registered render product when multiple
    # LidarSensor instances are active simultaneously. Sequential processing
    # avoids this limitation and ensures every sensor is validated.
    for prim in lidar_prims:
        prim_path = prim.GetPath().pathString
        world_xf = xf_cache.GetLocalToWorldTransform(prim)
        sensor_pos = world_xf.ExtractTranslation()
        near, far = _read_sensor_ranges(prim)
        wall_dist = _compute_wall_dist(near, far)
        scale = wall_dist / 10.0

        ctx.log("%s: near=%.3fm far=%.3fm wall_dist=%.3fm" % (prim_path, near, far, wall_dist))

        # Build sarcophagus for this sensor (replaces previous sensor's).
        _create_sarcophagus(stage, sensor_pos, scale)
        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        # Initialise ONLY this sensor for the upcoming simulation run.
        # Lidar(prim_path) works for both rotary and solid-state sensors
        # provided the asset declares correct USD metadata (metersPerUnit,
        # upAxis, startTimeCode/endTimeCode/timeCodesPerSecond). Without
        # those, USD falls back to 0.01 m/unit + Y-up when the file is
        # loaded via USD reference APIs, placing geometry out of sensor range.
        writer = None
        sensor = None
        try:
            lidar = Lidar(
                prim_path,
                attributes={
                    "omni:sensor:Core:outputFrameOfReference": "WORLD",
                },
            )
            sensor = LidarSensor(lidar, annotators=[])
            rp_key = sensor._hydra_texture.path.rsplit("/", 1)[-1]
            writer = sensor.attach_writer(
                "_LidarGmoCollector",
                rp_to_key={rp_key: 0},
            )
            any_initialized = True
        except Exception as exc:
            ctx.log("Could not initialize Lidar at %s: %s" % (prim_path, exc))
            continue

        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        ctx.step("Scanning %s (%d frames)" % (prim_path, scan_frames))
        omni.physx.get_physx_interface().start_simulation()
        omni.timeline.get_timeline_interface().play()
        for _ in range(scan_frames):
            await omni.kit.app.get_app().next_update_async()
        omni.timeline.get_timeline_interface().stop()

        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        # Copy GMO data to plain numpy arrays BEFORE destroying the sensor.
        # Warp/CUDA arrays returned by parse_generic_model_output_data become
        # dangling pointers once _invalidate_sensor() frees GPU resources.
        raw_gmo = writer._results.get(0) if writer is not None else None
        if raw_gmo is not None and raw_gmo.numElements > 0:
            gmo_np = {
                "x": np.asarray(raw_gmo.x, dtype=np.float64),
                "y": np.asarray(raw_gmo.y, dtype=np.float64),
                "z": np.asarray(raw_gmo.z, dtype=np.float64),
                "numElements": int(raw_gmo.numElements),
            }
        else:
            gmo_np = None

        # Destroy sensor before the next iteration.
        sensor._invalidate_sensor()
        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()

        if gmo_np is None:
            ctx.log(
                "LiDAR at %s: no data after %d frames " "(GPU driver >= 576.x required)." % (prim_path, scan_frames)
            )
            missing_sensors.append(prim_path)
            continue

        all_empty = False
        n = int(gmo_np["numElements"])
        total_points += n

        passed, pct_exceeding, _ = _check_range(gmo_np, scale)
        ctx.log("  %s: %d points, range_err=%.2f%%" % (prim_path, n, pct_exceeding))
        ctx.add_metric("lidar_%s_points" % prim_path.strip("/").replace("/", "_"), n)

        # Save azimuth-vs-elevation scatter plot as a run artifact.
        out_dir = getattr(ctx, "output_dir", None) or os.path.dirname(ctx.asset_path)
        img_path = _save_point_cloud_image(gmo_np, prim_path, out_dir)
        if img_path:
            ctx.log("  Saved point cloud image: %s" % img_path)

        if passed:
            ctx.log("  PASS: %s" % prim_path)
        else:
            ctx.fail(
                "LiDAR at %s: range check failed — "
                "%.1f%% of returns exceeded "
                "2%% range error (threshold: 1%%).\n\n"
                "How to fix:\n"
                "- Check emitter state azimuth/elevation arrays are "
                "correctly authored (LI.002 validates array lengths).\n"
                "- Verify omni:sensor:Core:numberOfEmitters matches "
                "all array lengths.\n"
                "- Confirm GPU driver >= 576.x for accurate RTX ray "
                "tracing." % (prim_path, pct_exceeding)
            )
            all_passed = False

    ctx.add_metric("lidar_total_points", total_points)

    if not any_initialized:
        ctx.skip(
            "No LiDAR sensors could be initialized. "
            "RTX rendering may be unavailable. "
            "GPU driver >= 576.x required for RTX LiDAR CUDA 12.9 support."
        )
        return

    if all_empty:
        ctx.skip(
            "All LiDAR buffers were empty after %d scan frames. "
            "Environment limitation — GPU driver >= 576.x required for "
            "RTX LiDAR CUDA 12.9 support in Isaac Sim 6.0.1." % scan_frames
        )
        return

    if missing_sensors:
        ctx.fail(
            "%d of %d LiDAR sensor(s) produced no point cloud after %d scan "
            "frames, while at least one other sensor on this asset did: "
            "%s.\n\n"
            "How to fix:\n"
            "- A sensor-specific gap while sibling sensors succeed is not "
            "the shared GPU-driver environment limitation (that would "
            "empty every sensor) — check this sensor's near/far range, "
            "emitter config, and placement relative to scannable geometry."
            % (len(missing_sensors), len(lidar_prims), scan_frames, ", ".join(missing_sensors))
        )
        all_passed = False

    if all_passed:
        ctx.log("LiDAR point cloud PASSED (total %d points)." % total_points)
