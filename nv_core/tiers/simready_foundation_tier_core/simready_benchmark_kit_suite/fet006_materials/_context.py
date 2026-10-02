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
"""Choosing which surface Kit evaluates, without editing the material.

A SimReady material declares up to three surface outputs on one prim, and Kit
decides between them with the ordered list in
``/persistent/app/hydra/material/renderContexts``. It walks that list and
takes the first output the material actually has. The shipped order is
``["mdl", "mtlx", ""]``, so a material with both an OmniPBR and an OpenPBR
surface renders the OmniPBR one, and a test that only asks whether something
rendered passes without the OpenPBR network ever being evaluated.

An earlier version of these tests solved that by disconnecting the surface
outputs it was not testing. That works, and it is the wrong trade: it mutates
the material network under test, and it removed the room's material along with
the asset's until the traversal was scoped.

Writing the list instead leaves every material exactly as authored.

A SINGLE-ENTRY LIST IS NOT "NO FALLBACK"
----------------------------------------
It reads as though it should be, and the docstring here used to say so. USD
falls back to the *universal* render context when the pinned context has no
output, whatever the list says. Measured on the rig, on a toaster with its
``outputs:mtlx:surface`` stripped: under ``["mtlx"]`` it rendered
(0.0826, 0.0800, 0.0826) and under ``[""]`` (0.0822, 0.0796, 0.0822) -- the same
picture. It did not take the MDL surface it still declares, and it did not get
Kit's default material.

That is what makes the surface tests' comparison sound. Pinning ``["mtlx"]``
and pinning ``[""]`` are the same render unless the MaterialX surface resolved,
so a difference between the two frames is the surface under test and nothing
else. ``_surface_test`` measures exactly that.

Kit's default material is what a material with no universal output falls to. On
a toaster stripped to MDL alone, both ``["mtlx"]`` and ``[""]`` rendered flat
red at (0.7378, 0.1596, 0.1596), agreeing with each other to within 0.0004 --
so that case fails the comparison rather than passing it.

TIMING
------
Kit resolves the list when the stage is attached, which is what the warning in
Preferences means. ``execute_single_test`` calls ``new_stage_async`` before the
test function body runs, so a value set inside a test lands after the stage
that would have read it. The setting has to be followed by a new stage, and
that is what ``pin`` does.

PRIVATE FRAMEWORK STATE
-----------------------
Creating a second stage inside a test leaves the framework's own handles
pointing at the discarded one, and there is no public call to re-seat them. Four
touches are load-bearing:

``ctx.scene._stage``
    ``KitSceneHandle`` caches the stage it was constructed with and every
    method reads that field. Left stale, the test authors its room and asset
    into a stage nobody is rendering, and the capture is an empty scene.

``ctx.scene._lighting``
    ``LightingManager`` caches the stage the same way, so the lights land in
    the discarded stage and the frame renders black.

``ctx._engine_session._viewport_ready``
``ctx._engine_session._viewport_camera``
    ``KitEngineProxy._ensure_viewport`` skips rebinding when it believes the
    viewport already holds the right camera at the right resolution. After a
    second stage the binding refers to a camera prim that no longer exists;
    without clearing both, capture raises ``'NoneType' object has no attribute
    'GetCamera'`` and returns a blank frame.

If the framework renames or restructures any of these, these tests break at
that point rather than silently mismeasuring -- a stale ``_stage`` produces an
empty room, and the viewport pair produces an exception. That is the cost of
this approach, and it is accepted here in exchange for not editing the asset's
materials. No supported alternative exists today: the render-context key
appears nowhere in the framework, the Kit launch arguments in
``command_builder`` are a fixed list built once per session rather than per
test, and one Kit session runs tests that need different contexts. A per-test
engine option, or a framework hook that runs between stage creation and the
test body, would remove all four touches.

PERSISTENCE
-----------
The key is under ``/persistent``, so Kit writes it to
``user.config.json`` on shutdown. ``reset_render_settings`` restores the
framework's own defaults and never unsets a key a test added, so a pinned value
outlives the test, the session and the process. That is how this test family
first produced three identical false passes. A caller snapshots ``read_order``
before its first ``pin`` and hands that snapshot to ``restore`` in a
``finally``, once, however many times it pinned in between.
"""

# The ordered list Kit resolves a material surface through.
RENDER_CONTEXTS_SETTING = "/persistent/app/hydra/material/renderContexts"

# Kit's shipped order, used only as the fallback when the live value cannot be
# read. Restoring is always done from the snapshot the caller took.
SHIPPED_ORDER = ["mdl", "mtlx", ""]


def read_order():
    """Kit's current ordered render-context list, or None outside Kit."""
    try:
        import carb.settings
    except ImportError:
        return None
    value = carb.settings.get_settings().get(RENDER_CONTEXTS_SETTING)
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


async def _new_stage(ctx):
    """Replace the stage and re-seat the framework handles that cached it."""
    import omni.kit.app
    import omni.usd
    from pxr import UsdGeom

    from simready_benchmark_engine_kit.lighting import LightingManager

    # Unbind the viewport from the camera prim that is about to stop existing.
    # execute_single_test does the same before its own new_stage_async; without
    # it the viewport holds a path that no longer resolves.
    try:
        import omni.kit.viewport.utility as viewport_utility

        viewport = viewport_utility.get_active_viewport()
        if viewport:
            viewport.camera_path = "/OmniverseKit_Persp"
    except Exception:
        pass

    ok, error = await omni.usd.get_context().new_stage_async()
    if not ok:
        raise RuntimeError(
            "Could not create the stage that reads the pinned render context: %s" % error
        )
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("Kit reported a new stage but returned none.")

    # Match what execute_single_test establishes for every other test, so the
    # scene this family builds sits in the same units and orientation.
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    ctx.scene._stage = stage
    ctx.scene._lighting = LightingManager(stage)
    # Nothing is built yet when pin() is called, so these are already None.
    # They are cleared anyway: a later change that pins after scene setup would
    # otherwise leave handles into a stage that has gone.
    ctx.scene._room_handle = None
    ctx.scene._room_prim = None
    ctx.scene._asset_handle = None
    ctx.scene._ground_plane_path = None
    ctx.scene._camera_follow_state = None
    ctx._engine_session._viewport_ready = False
    ctx._engine_session._viewport_camera = None

    app = omni.kit.app.get_app()
    for _ in range(3):
        await app.next_update_async()
    return stage


async def pin(ctx, order):
    """Write ``order`` to Kit's list and give it a stage that reads it.

    Returns the effective order, read back from carb after the stage exists, so
    it is what Kit actually holds rather than what was requested.

    A test calls this once per render pass. It does not snapshot: the caller
    takes one ``read_order`` before its first pin and restores that in a
    ``finally``, so a second pin cannot overwrite the snapshot with the first
    pin's value.
    """
    # override_render_settings both applies the value now and re-asserts it
    # before every capture, so a later scene reset cannot quietly drop it.
    ctx.override_render_settings({RENDER_CONTEXTS_SETTING: list(order)})
    await _new_stage(ctx)
    return read_order()


def restore(ctx, previous):
    """Put the render-context list back to the snapshot the caller took.

    Routed through ``override_render_settings`` so the restored value is in the
    enforced set when the framework's teardown runs. ``reset_render_settings``
    then rebuilds that set from the framework defaults, which do not include
    this key, and leaves carb holding the value restored here.

    ``previous`` is None when the key was absent before the test ran, which is a
    real snapshot rather than a missing one. ``override_render_settings`` offers
    no unset, so the key cannot be put back to absent and the shipped order is
    written instead. Kit resolves through that same order when the key is
    missing, so the behaviour matches; what it cannot avoid is leaving the key
    materialised where the test found none.
    """
    ctx.override_render_settings({RENDER_CONTEXTS_SETTING: list(previous or SHIPPED_ORDER)})
