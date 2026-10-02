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
"""The scene the FET006 material tests share.

One room, one light rig and one camera framing, so a difference between two
tests comes from the material rather than from the setup. No diagnostic
material is applied anywhere in this family: the material is what is under
test, and a diagnostic one would replace it.
"""

from simready_benchmark_kit_suite.fet006_materials import surfaces

# A mid grey room. White was the first choice and it separates badly at the
# light end: an OpenPBR surface with no authored base_color renders at the
# nodedef default of 0.8 grey, which is nearly the wall. Black separates badly
# at the dark end, and the MDL surface on the reference toaster is close to
# black. Mid grey keeps both ends visible.
#
# Nothing is measured against this colour. Every measurement is restricted to
# the asset's own silhouette, so the room is free to be chosen for contrast
# rather than to suit a mask -- which matters here, because under a pinned
# ["mtlx"] or ["mdl"] the room declares no surface and renders on Kit's default
# material.
ROOM_COLOR = (0.35, 0.35, 0.35)

SCENE_DEFAULTS = {
    "settle_frames": 8,
    "camera_padding": 1.2,
    "asset_load_timeout": 30,
    # Silhouette pixels the asset needs before coverage means anything. Below
    # this the ratio is denominated in noise. A rendered object covers a large
    # share of the frame -- the reference toaster measures around 294,000 of
    # the 1,048,576 in a 1024x1024 frame, the joystick around 66,000 -- so this
    # sits well below either rather than just above nothing.
    "min_silhouette_pixels": 5000,
    # How the silhouette is cut out of the frame in which the control material
    # has painted the asset flat magenta. The floor rejects the dim magenta
    # bounce the object throws across the room; the object itself is saturated
    # and bright.
    "mask_dominance_ratio": 1.5,
    "mask_dominance_floor": 0.20,
    # The reported frame is re-captured until two consecutive captures agree
    # this closely on mean RGB, or until the attempts below run out.
    #
    # Materials are not resident the moment a stage is attached, and nothing in
    # the test API reports when they are. Measured on Isaac Sim 5.0: the first
    # asset of a run captured its MDL pass at a mean of (0.344, 0.344, 0.344)
    # and the same frame later in the same session at (0.159, 0.156, 0.159) --
    # the untextured object and then the real one. Every later asset in that
    # run agreed to within 0.007 between passes, so this catches a cold start
    # rather than a steady-state difference.
    #
    # Only the reported frame needs it. Coverage is measured from the two
    # control passes, and the control is a flat colour that is resident
    # immediately, so an asset that is slow to load still shows the control
    # exactly where it binds nothing.
    "frame_settle_tolerance": 0.01,
    "frame_settle_attempts": 4,
    # Share of the asset's silhouette that must be shaded by materials it
    # authored for the context under test, measured against a magenta control
    # bound weaker than the asset's own bindings.
    #
    # This is a floor against an asset that is largely unshaded, not a
    # conformance threshold. VM.MAT.001 counts Gprims and is exact; this counts
    # pixels, so it reports how much of what a viewer sees is the asset's own
    # material.
    #
    # Measured on Isaac Sim 6.0.1 across the 20 sample assets with geometry to
    # measure, all three surface tests:
    #
    #     19 conformed sample assets            1.00000  (0 uncovered pixels,
    #                                                     every asset, every test)
    #     two equal cubes, one of them unbound  0.42419 - 0.43200
    #     TEST/minimal.usd, 3 Gprims, no
    #       material bound anywhere             0.00000
    #
    # Nothing lands between 0.43 and 1.0. Conformed assets do not merely clear
    # the floor, they leave no pixel uncovered at all, so the number this has to
    # sit above is the measurement's own error rather than any asset's result.
    # That error is the two passes framing on separate stages: on minimal.usd it
    # counted 71 to 113 more uncovered pixels than the 406,000 pixel silhouette
    # they are divided by, under 0.03%, which is why coverage is clamped at zero
    # before it is reported. 0.98 leaves more than sixty times that margin.
    "min_material_coverage": 0.98,
}


def asset_root(ctx):
    """The stage path of the loaded asset, or None if it cannot be determined.

    Everything scoped to the asset uses this. The room the test builds is a
    sibling on the same stage and is deliberately left alone.

    ``AssetHandle`` exposes the path as ``prim_path``. It has no ``GetPath``;
    assuming it does silently yields None, which widens every traversal to the
    whole stage and quietly takes the room with it.
    """
    asset = getattr(ctx.scene, "asset", None)
    if asset is not None:
        path = getattr(asset, "prim_path", None)
        if path:
            return path
    # The scene handle keeps the same path for its own bbox work.
    return getattr(ctx.scene, "_asset_root_path", None)


async def build_scene(ctx):
    """Load the asset into the shared room and frame it.

    Framing uses auto_frame_camera rather than ensure_object_framed: that
    helper confirms visibility by looking for the diagnostic colour, which
    this family deliberately never applies.

    auto_frame_camera computes a bbox from composed geometry and Kit composes
    references asynchronously, so a single settle can return before the
    geometry is there. An empty bbox collapses the camera to near the origin
    and the capture is an empty room, so settle across more than one pass
    before framing.
    """
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(*ROOM_COLOR)
    room.hide_ground()

    ctx.scene.lighting.add_directional(direction=(45.0, 0.0, 90.0), intensity=3000.0)
    ctx.scene.lighting.add_dome(intensity=150.0)

    await ctx.settle(count=2)
    ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
    await ctx.settle()


def report_surface_inventory(ctx, stage, root, prefix):
    """Record which contexts each of the asset's materials declares."""
    inventory = surfaces.describe_surfaces(stage, root)
    for context in surfaces.SURFACE_CONTEXTS:
        count = sum(1 for contexts in inventory.values() if context in contexts)
        name = context or "universal"
        ctx.add_metric(f"{prefix}_materials_with_{name}", count)
    ctx.add_metric(f"{prefix}_materials_total", len(inventory))
    return inventory
