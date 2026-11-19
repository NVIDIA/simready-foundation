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
"""Helpers shared by the FET_035 render product tests.

Used by render_product_output and semantic_aov_output. This module defines no
tests; the evaluate framework imports it like any other file in the suite while
it looks for tests, and that happens outside Kit, so omni and pxr must only be
imported inside functions.
"""

import numpy as np

# Reasons annotator output is not usable yet. A render product that was just
# created may not deliver on its first frame, so these are worth stepping past.
_WAITING = ("None returned", "empty array", "no finite samples")
_MALFORMED = "malformed"


def composed_path(raw_path, default_prim_path, composed_root):
    """Map a prim path from the raw asset stage to the composed stage.

    load_asset() references the asset's defaultPrim at composed_root, so a
    prim's path relative to the defaultPrim is preserved. Mapping by full path
    rather than prim name keeps cameras that share a name under different
    parents (e.g. front_hawk/left/camera_left and back_hawk/left/camera_left)
    distinct. Returns None when the prim is outside the defaultPrim subtree.
    """
    if default_prim_path is None:
        return None
    prefix = str(default_prim_path)
    if raw_path == prefix:
        return composed_root
    if raw_path.startswith(prefix + "/"):
        return composed_root + raw_path[len(prefix) :]
    return None


def payload_array(payload):
    """Return annotator output as a numpy array, or None when it has no data.

    For dictionary payloads the array is read from "data", not from metadata.
    """
    if isinstance(payload, dict):
        payload = payload.get("data")
    if payload is None:
        return None
    return np.array(payload)


def availability_problem(arr):
    """Describe why annotator output is unavailable, or return None when it is usable."""
    if arr is None:
        return "None returned"
    if arr.size == 0:
        return "empty array"
    if arr.ndim == 0 or arr.dtype.kind in "OUS":
        return _MALFORMED
    if np.issubdtype(arr.dtype, np.number) and not np.isfinite(arr).any():
        return "no finite samples"
    return None


def availability_error(kind, problem, frames_used):
    """Build the error for annotator output that is unavailable after frames_used frames."""
    if problem == _MALFORMED:
        return RuntimeError(f"required {kind} data is malformed")
    frames = "frame" if frames_used == 1 else "frames"
    return RuntimeError(f"required {kind} data is unavailable ({problem}) after {frames_used} {frames}")


def waiting_for_data(arr):
    """True when output is absent in a way a later frame may fix (not when it is malformed)."""
    return availability_problem(arr) in _WAITING


_FRAME_WRITER = "SimReadyAnnotatorFrameWriter"


def _register_frame_writer(rep):
    """Register the writer that collects annotator output unless it already is."""
    if _FRAME_WRITER in rep.WriterRegistry.get_writers():
        return

    class SimReadyAnnotatorFrameWriter(rep.Writer):
        """Collect the annotator output of every frame the render product produces.

        Replicator calls write() once for each frame the orchestrator captures,
        so frames_written counts frames that were really rendered. Polling
        get_data() cannot tell a new frame from a cached one.
        """

        def __init__(self, annotator_names=()):
            self.version = "1.0.0"
            self.data_structure = "renderProduct"
            self.annotators = [rep.annotators.get(name) for name in annotator_names]
            self.frames_written = 0
            self.latest = {}

        def write_metadata(self):
            """Nothing is written to disk, so there is no metadata to write."""

        def write(self, data):
            for rp_data in data.get("renderProducts", {}).values():
                for name, payload in rp_data.items():
                    self.latest[name] = payload
            self.frames_written += 1

    rep.WriterRegistry.register(SimReadyAnnotatorFrameWriter)


def attach_frame_writer(rep, rp_path, annotator_names, label):
    """Attach a writer collecting the named annotators' output to a render product.

    Raises RuntimeError naming the annotator when one cannot be set up. label
    names the render product in errors.
    """
    _register_frame_writer(rep)
    for name in annotator_names:
        try:
            rep.annotators.get(name)
        except Exception as exc:
            raise RuntimeError(f"{label}: annotator '{name}' setup failed") from exc
    try:
        writer = rep.writers.get(_FRAME_WRITER, init_params={"annotator_names": list(annotator_names)})
        writer.attach([rp_path])
    except Exception as exc:
        raise RuntimeError(f"{label}: annotator writer setup failed") from exc
    return writer


async def step_until_ready(rep, writer, names, max_steps, label, is_ready):
    """Step Replicator until every annotator's output is ready, at most max_steps frames.

    A render product created during a test may not deliver on its first frame.
    A step counts only when the writer received a frame from it, so output from
    an earlier frame is never mistaken for a new one. is_ready(name, arr) says
    whether one annotator's output needs no more frames. A step failure raises
    RuntimeError immediately; it is not something more frames can fix. label
    names the render product in errors.

    Returns (arrays, frames_used). arrays maps each annotator name to its output
    on the last frame, which is None when no frame arrived and may still be
    unavailable if max_steps ran out.
    """
    arrays, frames_used = {name: None for name in names}, 0
    for frame in range(1, max_steps + 1):
        frames_used = frame
        written = writer.frames_written
        try:
            await rep.orchestrator.step_async()
        except Exception as exc:
            raise RuntimeError(f"{label}: Replicator step failed") from exc
        if writer.frames_written == written:
            continue
        arrays = {name: payload_array(writer.latest.get(name)) for name in names}
        if all(is_ready(name, arr) for name, arr in arrays.items()):
            break
    return arrays, frames_used


def release_render_product(ctx, label, rep_rp, writer):
    """Detach the writer and destroy the render product once it has been checked.

    Replicator render products stay alive and keep rendering until destroyed, so
    without this every product checked adds to the load on the ones after it.
    """
    if writer is not None:
        try:
            writer.detach()
        except Exception as exc:
            ctx.log("  WARN %s: annotator writer detach failed: %s" % (label, exc))
    try:
        rep_rp.destroy()
    except Exception as exc:
        ctx.log("  WARN %s: render product destroy failed: %s" % (label, exc))
