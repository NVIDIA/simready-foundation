# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The FET001 visibility preflight must identify pixels caused by the asset."""

from types import SimpleNamespace
import importlib

import pytest
from PIL import Image

from simready.foundation.tier_core.runtime_tests.fet001_visual._asset_visibility import (
    asset_diagnostic_pixel_count,
    ensure_asset_visible,
)


def _image(path, color, *, square=None):
    image = Image.new("RGB", (40, 40), color)
    if square is not None:
        for x in range(10, 25):
            for y in range(10, 25):
                image.putpixel((x, y), square)
    image.save(path)
    return str(path)


@pytest.mark.parametrize("scene_color", [(140, 30, 10), (230, 51, 0)])
def test_unchanged_diagnostic_scene_cannot_prove_asset_visibility(tmp_path, scene_color):
    background = _image(tmp_path / "background.png", scene_color)
    visible = _image(tmp_path / "visible.png", scene_color)
    assert asset_diagnostic_pixel_count(visible, background) == 0


def test_changed_diagnostic_surface_proves_asset_visibility(tmp_path):
    background = _image(tmp_path / "background.png", (140, 30, 10))
    visible = _image(tmp_path / "visible.png", (140, 30, 10), square=(230, 51, 0))
    assert asset_diagnostic_pixel_count(visible, background) == 225


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("square", "expected_visible", "expected_pixels"),
    [(None, False, 0), ((230, 51, 0), True, 225)],
)
async def test_asset_pair_controls_visibility_and_restores_scene(tmp_path, square, expected_visible, expected_pixels):
    background = _image(tmp_path / "background.png", (140, 30, 10))
    visible = _image(tmp_path / "visible.png", (140, 30, 10), square=square)
    events = []

    async def framed(**_kwargs):
        return True

    async def settle():
        events.append("settle")

    async def capture_frame(**kwargs):
        events.append("capture:" + kwargs["label"])
        return visible if kwargs["label"].endswith("visible") else background

    ctx = SimpleNamespace(
        ensure_object_framed=framed,
        settle=settle,
        capture_frame=capture_frame,
        scene=SimpleNamespace(
            hide_asset=lambda: events.append("hide"),
            show_asset=lambda: events.append("show"),
        ),
        add_metric=lambda name, value: events.append((name, value)),
    )
    assert await ensure_asset_visible(ctx, padding=1.2) is expected_visible
    assert events.index("hide") < events.index("show")
    assert ("visibility_asset_pixels", expected_pixels) in events


@pytest.mark.asyncio
async def test_visibility_capture_error_restores_asset_and_remains_error(tmp_path):
    visible = _image(tmp_path / "visible.png", (230, 51, 0))
    events = []
    failure = OSError("hidden capture unavailable")

    async def framed(**_kwargs):
        return True

    async def settle():
        return None

    async def capture_frame(**kwargs):
        if kwargs["label"].endswith("hidden"):
            raise failure
        return visible

    ctx = SimpleNamespace(
        ensure_object_framed=framed,
        settle=settle,
        capture_frame=capture_frame,
        scene=SimpleNamespace(
            hide_asset=lambda: events.append("hide"),
            show_asset=lambda: events.append("show"),
        ),
    )
    with pytest.raises(OSError) as caught:
        await ensure_asset_visible(ctx, padding=1.2)
    assert caught.value is failure
    assert events == ["hide", "show"]


@pytest.mark.asyncio
async def test_visibility_cleanup_error_preserves_original_capture_error(tmp_path, caplog):
    visible = _image(tmp_path / "visible.png", (230, 51, 0))
    failure = OSError("hidden capture unavailable")
    retired = []

    async def framed(**_kwargs):
        return True

    async def settle():
        return None

    async def capture_frame(**kwargs):
        if kwargs["label"].endswith("hidden"):
            raise failure
        return visible

    def show_asset():
        raise RuntimeError("show failed")

    ctx = SimpleNamespace(
        ensure_object_framed=framed,
        settle=settle,
        capture_frame=capture_frame,
        scene=SimpleNamespace(hide_asset=lambda: None, show_asset=show_asset),
        _engine_session=SimpleNamespace(record_required_cleanup_failure=retired.append),
    )
    with pytest.raises(OSError) as caught:
        await ensure_asset_visible(ctx, padding=1.2)
    assert caught.value is failure
    assert "Asset visibility restoration also failed" in caplog.text
    assert len(retired) == 1
    assert "visibility" in retired[0].lower()


@pytest.mark.asyncio
async def test_visibility_cleanup_error_retires_session_without_capture_error(tmp_path):
    frame = _image(tmp_path / "frame.png", (230, 51, 0))
    retired = []

    async def framed(**_kwargs):
        return True

    async def settle():
        return None

    async def capture_frame(**_kwargs):
        return frame

    def show_asset():
        raise RuntimeError("show failed")

    ctx = SimpleNamespace(
        ensure_object_framed=framed,
        settle=settle,
        capture_frame=capture_frame,
        scene=SimpleNamespace(hide_asset=lambda: None, show_asset=show_asset),
        _engine_session=SimpleNamespace(record_required_cleanup_failure=retired.append),
    )
    with pytest.raises(RuntimeError, match="show failed"):
        await ensure_asset_visible(ctx, padding=1.2)
    assert len(retired) == 1
    assert "visibility" in retired[0].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("procedure", "expected"),
    [
        ("light_response", "fail"),
        ("culling_x", "fail"),
        ("culling_z", "fail"),
        ("culling_xz", "fail"),
        ("normals_x", "fail"),
        ("normals_z", "fail"),
        ("normals_xz", "fail"),
        ("pivot", "skip"),
    ],
)
@pytest.mark.parametrize("scene_color", [(140, 30, 10), (230, 51, 0)])
async def test_hidden_asset_reaches_documented_procedure_outcome(tmp_path, procedure, expected, scene_color):
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests.fet001_visual." + procedure)
    background = _image(tmp_path / "background.png", scene_color)
    visible = _image(tmp_path / "visible.png", scene_color)
    outcomes, metrics = [], {}
    room = SimpleNamespace(
        auto_size=lambda *_args: None,
        set_color=lambda *_args: None,
        hide_ground=lambda: None,
        show_ground=lambda **_kwargs: None,
    )

    async def framed(**_kwargs):
        return True

    async def settle():
        return None

    async def capture_frame(**kwargs):
        return visible if kwargs["label"].endswith("visible") else background

    def no_bounds(**_kwargs):
        pytest.fail("Hidden asset must be rejected before authored bounds are read")

    ctx = SimpleNamespace(
        asset_path="asset.usda",
        config={
            "camera_padding": 1.2,
            "asset_load_timeout": 30,
            "settle_frames": 5,
            "steps": 30,
            "max_blank_ratio": 0.5,
            "min_variation_ratio": 0.1,
            "pair_change_pixel_ratio": 0.05,
            "pair_change_threshold": 0.03,
            "different_ratio_threshold": 0.1,
            "dark_threshold": 0.15,
            "max_problem_ratio": 0.5,
            "min_problem_frames": 2,
            "pivot_height_tolerance": 0.1,
            "penetration_tolerance": 0.05,
            "orbital_tolerance": 0.1,
            "pass_score_threshold": 0.7,
            "video_capture_interval": 3,
        },
        scene=SimpleNamespace(
            asset=object(),
            load_asset=lambda *_args, **_kwargs: None,
            add_room=lambda: room,
            lighting=SimpleNamespace(
                add_directional=lambda **_kwargs: object(),
                add_dome=lambda **_kwargs: None,
            ),
            apply_diagnostic_material=lambda **_kwargs: None,
            set_double_sided=lambda *_args: None,
            hide_asset=lambda: None,
            show_asset=lambda: None,
        ),
        set_settle_frames=lambda *_args: None,
        ensure_object_framed=framed,
        settle=settle,
        capture_frame=capture_frame,
        get_asset_bounds=no_bounds,
        add_metric=lambda name, value: metrics.__setitem__(name, value),
        fail=lambda message: outcomes.append(("fail", message)),
        skip=lambda message: outcomes.append(("skip", message)),
    )
    await getattr(module, "test_" + procedure)(ctx)
    assert [status for status, _message in outcomes] == [expected]
    assert metrics["visibility_asset_pixels"] == 0
    if procedure in {"culling_x", "culling_z", "normals_x", "normals_z", "normals_xz"}:
        assert "Fewer than 100 asset-attributable" in outcomes[0][1]
