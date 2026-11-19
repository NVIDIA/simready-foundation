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

One room, one light rig and one camera framing. The loaded asset sits inside
a test-owned wrapper, so inherited probe bindings never replace a material
opinion on the asset root. The room remains outside the probe subtree.

An asset with no renderable geometry of its own -- a material published on its
own -- gets a test sphere per material, bound to that material, beside the asset
under the same wrapper. Those spheres are the only geometry the scene draws for it.
"""

import math

from pxr import Gf, Sdf, UsdGeom, UsdShade, Vt
from simready.foundation.tier_core.runtime_tests.fet006_materials import surfaces

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
PROBE_ASSET_PARENT = "/World/_SimReadySurfaceAsset"

# Where a material asset's materials are rendered. Beside the asset rather than
# under it: the asset root is the Material itself, and a Material's children are
# its shading network. Under the wrapper, so the probes bound there reach them.
TEST_SPHERES = PROBE_ASSET_PARENT + "/_SimReadyTestSpheres"
TEST_SPHERE_RADIUS = 0.5
# Latitude bands and longitude segments: enough that the silhouette reads as
# round and a texture lands on it without visible facets.
TEST_SPHERE_BANDS = 32
TEST_SPHERE_SEGMENTS = 64

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
    # Only the reported frame needs it. Coverage uses a strong magenta
    # silhouette and two weak-color probes. A pixel must follow both weak
    # colors to count as exposed control; this remains a color proxy.
    "frame_settle_tolerance": 0.01,
    "frame_settle_attempts": 4,
    # Required reported coverage from the two-color proxy with controls
    # bound weaker than asset bindings. Coverage does not prove shader
    # evaluation or the static binding/presence requirements.
    #
    # VM.MAT.001 counts Gprims and is exact; this counts pixels, so it reports
    # how much of what a viewer sees is the asset's own material. Unbound
    # geometry covering two percent or less of the silhouette passes. The
    # measurements behind 0.98 are in docs/fet006-materials.md, "The Coverage
    # Floor".
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


def _sphere(stage, path, center):
    """A UV sphere mesh with ``st`` texture coordinates, centred on ``center``.

    A mesh rather than ``UsdGeom.Sphere``, which has no texture coordinates:
    the materials' texture lookups read the ``st`` primvar. ``st`` runs 0 to 1
    around the sphere and from the bottom pole to the top one.
    """
    radius = TEST_SPHERE_RADIUS
    row = TEST_SPHERE_SEGMENTS + 1
    points, normals, st = [], [], []
    for band in range(TEST_SPHERE_BANDS + 1):
        v = band / TEST_SPHERE_BANDS
        ring, height = math.sin(math.pi * v), -math.cos(math.pi * v)
        for segment in range(row):
            u = segment / TEST_SPHERE_SEGMENTS
            normal = Gf.Vec3f(ring * math.cos(2.0 * math.pi * u), ring * math.sin(2.0 * math.pi * u), height)
            normals.append(normal)
            points.append(normal * radius)
            st.append(Gf.Vec2f(u, v))
    indices = []
    for band in range(TEST_SPHERE_BANDS):
        for segment in range(TEST_SPHERE_SEGMENTS):
            first = band * row + segment
            # Counter-clockwise seen from outside, so the faces point outward.
            indices.extend((first, first + 1, first + row + 1, first + row))

    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4] * (TEST_SPHERE_BANDS * TEST_SPHERE_SEGMENTS)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))
    mesh.CreateNormalsAttr(Vt.Vec3fArray(normals))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(-radius, -radius, -radius), Gf.Vec3f(radius, radius, radius)]))
    UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(
        Vt.Vec2fArray(st)
    )
    mesh.AddTranslateOp().Set(Gf.Vec3d(*center))
    return mesh


def add_test_spheres(stage, root):
    """Bind each material the asset publishes to a test sphere of its own.

    Returns ``(count, low, high)``: how many materials were bound, and the
    corners of the box the spheres fill. Returns None when ``root`` has no
    materials. The spheres stand on the ground in a grid facing the camera.

    They are authored on the disposable scene stage, beside the asset, so the
    asset's own layers are not edited. A binding the stage rejects raises: a
    sphere left on the default material would be measured as the asset's.
    """
    materials = surfaces.published_materials(stage, root)
    if not materials:
        return None
    columns = math.ceil(math.sqrt(len(materials)))
    rows = math.ceil(len(materials) / columns)
    spacing = 2.5 * TEST_SPHERE_RADIUS
    UsdGeom.Scope.Define(stage, TEST_SPHERES)
    for index, material in enumerate(materials):
        row, column = divmod(index, columns)
        center = (
            (column - (columns - 1) / 2.0) * spacing,
            0.0,
            TEST_SPHERE_RADIUS + (rows - 1 - row) * spacing,
        )
        sphere = _sphere(stage, f"{TEST_SPHERES}/Sphere_{index}", center)
        if not UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(UsdShade.Material(material)):
            raise RuntimeError(f"Required test sphere binding was rejected for material {material.GetPath()}")
    half_width = (columns - 1) * spacing / 2.0 + TEST_SPHERE_RADIUS
    low = Gf.Vec3d(-half_width, -TEST_SPHERE_RADIUS, 0.0)
    high = Gf.Vec3d(half_width, TEST_SPHERE_RADIUS, (rows - 1) * spacing + 2.0 * TEST_SPHERE_RADIUS)
    return len(materials), low, high


def _frame(ctx, low, high, padding):
    """Aim the camera at a box from the direction and lens ``auto_frame_camera`` uses for an asset.

    ``auto_frame_camera`` only measures meshes under the asset root, and the test
    spheres are outside it.
    """
    center = (low + high) * 0.5
    fov = 2.0 * math.atan(36.0 / (2.0 * 35.0))
    distance = max((high - low).GetLength() * padding / (2.0 * math.tan(fov * 0.5)), 0.1)
    eye = center + Gf.Vec3d(0.3, 0.8, 0.4).GetNormalized() * distance
    ctx.scene.set_camera(position=tuple(eye), target=tuple(center))


async def build_scene(ctx):
    """Load the asset into the shared room and frame it.

    Returns how many materials were rendered on test spheres: zero when the
    asset has renderable geometry of its own.

    Framing uses auto_frame_camera rather than ensure_object_framed: that
    helper confirms visibility by looking for the diagnostic colour, which
    is absent from the initial appearance/framing scene; probe controls
    are applied only after that scene has been framed.

    auto_frame_camera computes a bbox from composed geometry and Kit composes
    references asynchronously, so a single settle can return before the
    geometry is there. An empty bbox collapses the camera to near the origin
    and the capture is an empty room, so settle across more than one pass
    before framing. Whether the asset has geometry of its own is decided at
    the same point.
    """
    ctx.set_settle_frames(ctx.config["settle_frames"])
    ctx.scene.load_asset(ctx.asset_path, parent_xform=PROBE_ASSET_PARENT, timeout=ctx.config["asset_load_timeout"])

    room = ctx.scene.add_room()
    room.auto_size(ctx.scene.asset)
    room.set_color(*ROOM_COLOR)
    room.hide_ground()

    ctx.scene.lighting.add_directional(direction=(45.0, 0.0, 90.0), intensity=3000.0)
    ctx.scene.lighting.add_dome(intensity=150.0)

    await ctx.settle(count=2)
    stage, root = ctx.scene.stage, asset_root(ctx)
    spheres = None
    if root and next(surfaces.renderable_geometry(stage, root), None) is None:
        spheres = add_test_spheres(stage, root)
    if spheres:
        _frame(ctx, spheres[1], spheres[2], ctx.config["camera_padding"])
    else:
        ctx.scene.auto_frame_camera(padding=ctx.config["camera_padding"])
    await ctx.settle()
    return spheres[0] if spheres else 0


def report_surface_inventory(ctx, stage, root, prefix):
    """Record which contexts each of the asset's materials declares."""
    inventory = surfaces.describe_surfaces(stage, root)
    for context in surfaces.SURFACE_CONTEXTS:
        count = sum(1 for contexts in inventory.values() if context in contexts)
        name = context or "universal"
        ctx.add_metric(f"{prefix}_materials_with_{name}", count)
    ctx.add_metric(f"{prefix}_materials_total", len(inventory))
    return inventory
