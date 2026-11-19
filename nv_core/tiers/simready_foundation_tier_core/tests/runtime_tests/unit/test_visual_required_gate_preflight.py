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
"""Required visual gates use the official decorator, runtime context and status route."""

import asyncio
import importlib
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from simready.evaluate.cli.modes import _parse_value
from simready.evaluate.core import decorator
from simready.evaluate.runner.test_context import RunContext
from simready.evaluate_engine_kit.execution import (
    _merge_config,
    _result_status_and_message,
)
from simready.foundation.tier_core.runtime_tests._visual_readback import validate_visual_config
from simready.foundation.tier_core.runtime_tests.fet011_semantics import _seg_common

REGISTRATIONS = [
    ("fet001_visual.presence", "min_diff_ratio"),
    ("fet001_visual.pivot", "pass_score_threshold"),
    ("fet001_visual.culling_x", "different_ratio_threshold"),
    ("fet001_visual.culling_z", "different_ratio_threshold"),
    ("fet001_visual.culling_xz", "different_ratio_threshold"),
    ("fet001_visual.light_response", "min_variation_ratio"),
    ("fet001_visual.normals_x", "max_problem_ratio"),
    ("fet001_visual.normals_z", "max_problem_ratio"),
    ("fet001_visual.normals_xz", "max_problem_ratio"),
    ("fet010_standard.display_color_response", "min_response_ratio"),
    ("fet010_standard.display_color_response", "max_control_ratio"),
    ("fet010_standard.display_color_response", "min_opacity_response_ratio"),
    ("fet011_semantics.seg_labelled", "on_coverage_min"),
    ("fet011_semantics.seg_stripped", "off_coverage_max"),
    ("fet012_gaussian_splat.presence", "min_splat_coverage"),
]


def _definition(monkeypatch, module_name):
    monkeypatch.setattr(decorator, "_REGISTRY", [])
    registered = []
    original = decorator.test

    def capture(**metadata):
        apply = original(**metadata)

        def declaration(function):
            function = apply(function)
            registered.append(
                SimpleNamespace(
                    func=function,
                    name=metadata["name"],
                    version=metadata["version"],
                    config_defaults=metadata["config_defaults"],
                    features=[SimpleNamespace(id=feature["id"]) for feature in metadata["features"]],
                )
            )
            return function

        return declaration

    monkeypatch.setattr(decorator, "test", capture)
    module = importlib.import_module("simready.foundation.tier_core.runtime_tests." + module_name)
    importlib.reload(module)
    # Disabled X/Z experiments remain disabled; capture their source metadata
    # without adding a provider registration or inventing a test procedure.
    return registered[-1]


def _context(definition, overrides):
    return RunContext(
        asset_path="asset.usda",
        asset_rel_path="asset.usda",
        output_dir="unused-output",
        test_name=definition.name,
        test_version=definition.version,
        feature_id=definition.features[0].id,
        engine_name="kit",
        engine_version="6.1.0",
        session_id="visual-preflight-regression",
        scene=None,
        config=_merge_config(definition.config_defaults, overrides),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name,key", REGISTRATIONS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, False, "0.1", -0.1, 1.1])
async def test_invalid_acceptance_gate_errors_before_scene_work(monkeypatch, module_name, key, value):
    definition = _definition(monkeypatch, module_name)
    if isinstance(value, float) and np.isnan(value):
        value = json.loads(json.dumps(_parse_value("nan")))
    ctx = _context(definition, {key: value})
    with pytest.raises(RuntimeError, match="Invalid visual measurement configuration: " + key) as caught:
        await definition.func(ctx)
    status, message = _result_status_and_message(ctx, test_exception=caught.value)
    assert status == "error" and key in message
    assert not ctx.failed


@pytest.mark.parametrize("ratio", [1.5, 100.0, 1e12])
def test_color_dominance_ratio_is_positive_not_a_unit_fraction(ratio):
    validate_visual_config({"mask_dominance_ratio": ratio}, positive=("mask_dominance_ratio",))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_name,overrides",
    [
        ("pivot", {"steps": 0}),
        ("pivot", {"video_capture_interval": 0}),
        ("light_response", {"steps": 1}),
        *[("normals_" + axis, {"steps": 1, "min_problem_frames": 2}) for axis in ("x", "z", "xz")],
        *[("culling_" + axis, {"steps": 0}) for axis in ("x", "z", "xz")],
    ],
)
async def test_impossible_visual_capacity_errors_before_scene_work(monkeypatch, module_name, overrides):
    definition = _definition(monkeypatch, "fet001_visual." + module_name)
    ctx = _context(definition, overrides)
    with pytest.raises(RuntimeError, match="Invalid visual measurement configuration") as caught:
        await definition.func(ctx)
    assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["pivot_height_tolerance", "penetration_tolerance", "orbital_tolerance"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, True, "0.1"])
async def test_pivot_geometry_tolerances_require_finite_nonnegative_values(monkeypatch, key, value):
    definition = _definition(monkeypatch, "fet001_visual.pivot")
    with pytest.raises(RuntimeError, match=key):
        await definition.func(_context(definition, {key: value}))


@pytest.mark.parametrize("value", [0.0, 1.5, 100.0])
def test_geometry_tolerances_keep_valid_zero_and_unbounded_ratio_policy(value):
    validate_visual_config({"tolerance": value}, nonnegative=("tolerance",))


def _render_context(monkeypatch, definition, frames):
    """Run the actual registered procedure and image-analysis body without Kit."""
    from simready.evaluate_engine_kit.kit_engine_proxy import KitEngineProxy

    # Each context models a fresh healthy worker. A prior independent test may
    # have deliberately retired its native worker; do not inherit that state.
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", False, raising=False)
    ctx = _context(definition, {})
    room = SimpleNamespace(
        auto_size=lambda *args: None,
        set_color=lambda *args: None,
        hide_ground=lambda: None,
        show_ground=lambda **kwargs: None,
    )
    light = SimpleNamespace(set_direction=lambda *args: None)
    ctx.scene = SimpleNamespace(
        asset=object(),
        load_asset=lambda *args, **kwargs: None,
        add_room=lambda: room,
        lighting=SimpleNamespace(add_dome=lambda **kwargs: None, add_directional=lambda **kwargs: light),
        apply_diagnostic_material=lambda **kwargs: None,
        set_double_sided=lambda value: None,
        rotate_asset=lambda *args: None,
        rotate_asset_multi=lambda *args: None,
        auto_frame_camera=lambda **kwargs: None,
        reset_asset_transform=lambda: None,
        hide_asset=lambda: None,
        show_asset=lambda: None,
    )
    iterator = iter(frames)

    async def framed(**kwargs):
        return True  # The precheck succeeded; later captured frames still need qualification.

    async def settle():
        return None

    async def capture(**kwargs):
        return next(iterator)

    monkeypatch.setattr(ctx, "set_settle_frames", lambda *args: None)
    monkeypatch.setattr(ctx, "ensure_object_framed", framed)
    # These cases exercise sweep coverage after a successful asset-specific
    # visibility preflight; its paired capture is tested separately.
    module = sys.modules[definition.func.__module__]
    if hasattr(module, "ensure_asset_visible"):
        monkeypatch.setattr(module, "ensure_asset_visible", lambda *_args, **_kwargs: framed())
    monkeypatch.setattr(ctx, "settle", settle)
    monkeypatch.setattr(ctx, "capture_frame", capture)
    monkeypatch.setattr(ctx, "encode_video", lambda *args, **kwargs: "diagnostic.mp4")
    monkeypatch.setattr(
        ctx,
        "compare_object_pixels",
        lambda *args, **kwargs: KitEngineProxy.compare_object_pixels(None, *args, **kwargs),
    )
    return ctx


@pytest.fixture
def visual_images(tmp_path):
    from PIL import Image

    paths = {}
    for name, color in (("blank", "white"), ("orange", (230, 51, 0)), ("dark", "black")):
        path = tmp_path / (name + ".png")
        Image.new("RGB", (64, 64), color).save(path)
        paths[name] = str(path)
    return paths


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["normals", "culling"])
@pytest.mark.parametrize("axis", ["x", "z", "xz"])
async def test_default_sweep_with_no_object_denominator_is_error(monkeypatch, visual_images, family, axis):
    name = family + "_" + axis
    definition = _definition(monkeypatch, "fet001_visual." + name)
    count = definition.config_defaults["steps"] * (2 if family == "culling" else 1)
    ctx = _render_context(monkeypatch, definition, [visual_images["blank"]] * count)
    with pytest.raises(RuntimeError, match="coverage is incomplete") as caught:
        await definition.func(ctx)
    assert not ctx.failed and name + "_passed" not in ctx.metrics
    assert _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    assert ctx.metrics[name + "_omitted_indices"]["value"] == list(range(8))


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ["x", "z", "xz"])
@pytest.mark.parametrize("observed_breach", [False, True])
async def test_culling_gap_never_passes_but_keeps_observed_breach(monkeypatch, visual_images, axis, observed_breach):
    name = "culling_" + axis
    definition = _definition(monkeypatch, "fet001_visual." + name)
    # Seven unmeasured OFF references and one qualified pair at original angle 7.
    frames = [visual_images["blank"]] * 14 + [
        visual_images["orange"],
        visual_images["blank"] if observed_breach else visual_images["orange"],
    ]
    ctx = _render_context(monkeypatch, definition, frames)
    if observed_breach:
        await definition.func(ctx)
        assert ctx.failed and ctx.metrics[name + "_passed"]["value"] == 0
        assert ctx.metrics[name + "_worst_angle"]["value"] == 315.0
        assert _result_status_and_message(ctx)[0] == "fail"
    else:
        with pytest.raises(RuntimeError, match="coverage is incomplete"):
            await definition.func(ctx)
        assert not ctx.failed and name + "_passed" not in ctx.metrics
    assert ctx.metrics[name + "_coverage_complete"]["value"] == 0
    assert ctx.metrics[name + "_qualified_pairs"]["value"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["normals", "culling"])
async def test_fully_measured_orange_sweep_retains_default_pass(monkeypatch, visual_images, family):
    name = family + "_xz"
    definition = _definition(monkeypatch, "fet001_visual." + name)
    count = definition.config_defaults["steps"] * (2 if family == "culling" else 1)
    ctx = _render_context(monkeypatch, definition, [visual_images["orange"]] * count)
    await definition.func(ctx)
    assert not ctx.failed and ctx.metrics[name + "_passed"]["value"] == 1
    assert _result_status_and_message(ctx)[0] == "pass"


@pytest.mark.asyncio
@pytest.mark.parametrize("dark_frames,expect_failure", [(1, False), (2, True)])
async def test_normals_omit_edge_on_view_without_changing_problem_gate(
    monkeypatch, visual_images, dark_frames, expect_failure
):
    definition = _definition(monkeypatch, "fet001_visual.normals_xz")
    frames = (
        [visual_images["blank"]] + [visual_images["dark"]] * dark_frames + [visual_images["orange"]] * (7 - dark_frames)
    )
    ctx = _render_context(monkeypatch, definition, frames)
    await definition.func(ctx)
    assert ctx.failed is expect_failure
    assert ctx.metrics["normals_xz_qualified_frames"]["value"] == 7
    assert ctx.metrics["normals_xz_problem_frames"]["value"] == dark_frames
    assert ctx.metrics["normals_xz_avg_dark"]["value"] == round(dark_frames / 7, 6)


@pytest.mark.asyncio
async def test_normals_requires_enough_usable_frames_to_reach_gate(monkeypatch, visual_images):
    definition = _definition(monkeypatch, "fet001_visual.normals_xz")
    ctx = _render_context(monkeypatch, definition, [visual_images["orange"]] + [visual_images["blank"]] * 7)
    with pytest.raises(RuntimeError, match="at least min_problem_frames"):
        await definition.func(ctx)
    assert not ctx.failed and "normals_xz_passed" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("warning_failure", [False, True])
async def test_encoder_failure_cannot_mask_measured_normals_verdict(monkeypatch, visual_images, dark, warning_failure):
    definition = _definition(monkeypatch, "fet001_visual.normals_xz")
    ctx = _render_context(monkeypatch, definition, [visual_images["dark" if dark else "orange"]] * 8)

    def broken_encode(*args, **kwargs):
        raise OSError("encoder unavailable")

    ctx._engine_session = SimpleNamespace(encode_video=lambda *args, **kwargs: None)
    monkeypatch.setattr(ctx, "encode_video", RunContext.encode_video.__get__(ctx, RunContext))
    if warning_failure:
        monkeypatch.setattr(ctx, "warn", broken_encode)
    await definition.func(ctx)
    assert ctx.failed is dark
    assert _result_status_and_message(ctx)[0] == ("fail" if dark else "pass")
    if not warning_failure:
        assert any("encode_video returned None" in warning for warning in ctx.warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["engine", "unsafe", "escape"])
async def test_actual_visual_caller_cannot_hide_required_encoder_errors(monkeypatch, visual_images, tmp_path, outcome):
    from simready.evaluate.core.output_layout import UnsafeEvidencePathError

    definition = _definition(monkeypatch, "fet001_visual.normals_xz")
    ctx = _render_context(monkeypatch, definition, [visual_images["orange"]] * 8)
    ctx.output_dir = str(tmp_path)
    original = OSError("unknown engine failure") if outcome == "engine" else UnsafeEvidencePathError("unsafe media")

    def encode(*args, **kwargs):
        if outcome == "escape":
            return "../escaped.mp4"
        raise original

    ctx._engine_session = SimpleNamespace(encode_video=encode)
    monkeypatch.setattr(ctx, "encode_video", RunContext.encode_video.__get__(ctx, RunContext))
    expected = ValueError if outcome == "escape" else type(original)
    with pytest.raises(expected) as caught:
        await definition.func(ctx)
    if outcome != "escape":
        assert caught.value is original
    assert not ctx.failed
    assert _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"


def test_optional_encoder_preserves_cancellation_and_retired_engine(monkeypatch):
    from simready.foundation.tier_core.runtime_tests._visual_diagnostics import encode_visual_video

    def cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    ctx = SimpleNamespace(encode_video=cancelled)
    with pytest.raises(asyncio.CancelledError):
        encode_visual_video(ctx, ["frame"])

    def unsafe(*args, **kwargs):
        raise RuntimeError("unsafe native engine")

    ctx.encode_video = unsafe
    monkeypatch.setattr(sys, "_simready_evaluate_kit_engine_retired", True, raising=False)
    with pytest.raises(RuntimeError, match="unsafe native engine"):
        encode_visual_video(ctx, ["frame"])


@pytest.mark.parametrize("value", [None, True, -1, 1.5, float("nan"), float("inf"), "100"])
def test_invalid_object_denominator_is_required_readback_error(value):
    from simready.foundation.tier_core.runtime_tests._visual_readback import (
        required_object_pixel_count,
    )

    with pytest.raises(RuntimeError, match="object-pixel count is invalid"):
        required_object_pixel_count(SimpleNamespace(object_pixel_count=value), "test")


@pytest.mark.asyncio
async def test_presence_nonfinite_observed_ratio_cannot_pass(monkeypatch, visual_images):
    definition = _definition(monkeypatch, "fet001_visual.presence")
    ctx = _render_context(monkeypatch, definition, [visual_images["blank"], visual_images["orange"]])
    monkeypatch.setattr(ctx, "compare_images", lambda *args, **kwargs: SimpleNamespace(different_ratio=float("nan")))
    with pytest.raises(RuntimeError, match="presence different_ratio"):
        await definition.func(ctx)
    assert not ctx.failed and "presence_passed" not in ctx.metrics


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", ["presence", "normals_xz"])
@pytest.mark.parametrize("frame_kind", ["missing", "corrupt", "blank"])
async def test_official_visibility_precheck_distinguishes_error_from_measured_absence(
    monkeypatch, visual_images, tmp_path, module_name, frame_kind
):
    from simready.evaluate_engine_kit.kit_engine_proxy import KitEngineProxy

    definition = _definition(monkeypatch, "fet001_visual." + module_name)
    ctx = _render_context(monkeypatch, definition, [])
    path = tmp_path / "visibility.png"
    if frame_kind == "blank":
        path = tmp_path / "blank.png"
    elif frame_kind == "corrupt":
        path.write_bytes(b"not a decodable captured image")
    ctx.output_dir = str(tmp_path)

    async def capture(**kwargs):
        return str(path)

    ctx._engine_session = SimpleNamespace(
        capture_frame=capture,
        check_object_visible=lambda *args, **kwargs: KitEngineProxy.check_object_visible(None, *args, **kwargs),
        remove_capture=lambda _path: None,
    )
    # Exercise the actual shared framing loop, not a substitute visibility test.
    monkeypatch.setattr(ctx, "ensure_object_framed", RunContext.ensure_object_framed.__get__(ctx, RunContext))
    if module_name == "normals_xz":
        from simready.foundation.tier_core.runtime_tests.fet001_visual._asset_visibility import ensure_asset_visible

        # _render_context bypasses the paired preflight for sweep-focused
        # cases. Restore it here to exercise the real visibility entry path.
        monkeypatch.setattr(sys.modules[definition.func.__module__], "ensure_asset_visible", ensure_asset_visible)
    if frame_kind == "blank":
        await definition.func(ctx)
        assert ctx.failed and _result_status_and_message(ctx)[0] == "fail"
    else:
        with pytest.raises(OSError) as caught:
            await definition.func(ctx)
        assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
    assert module_name + "_passed" not in ctx.metrics


@pytest.mark.parametrize("boundary", [0.0, 1.0])
def test_existing_fraction_boundaries_remain_valid(boundary):
    validate_visual_config({"threshold": boundary}, fractions=("threshold",))


@pytest.mark.parametrize("field", ["steps", "min_problem_frames", "min_silhouette_pixels", "render_subframes"])
@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1, 0, 1.5, "2"])
def test_required_measurement_counts_are_real_positive_integers(field, value):
    with pytest.raises(RuntimeError, match=field):
        validate_visual_config({field: value}, positive_counts=(field,))


@pytest.mark.parametrize(
    "array",
    [
        None,
        [],
        np.zeros((0, 2, 3)),
        np.zeros((2, 0, 3)),
        np.zeros((2, 2, 2)),
        np.zeros(3),
        np.zeros((1, 2, 2, 3)),
        np.ones((2, 2, 3), dtype=bool),
        np.full((2, 2, 3), np.nan),
        np.full((2, 2, 3), np.inf),
        np.full((2, 2, 3), -1),
        np.full((2, 2, 3), "0"),
        np.zeros((2, 2, 3), dtype=object),
        np.zeros((2, 2, 3), dtype=complex),
    ],
)
def test_invalid_required_segmentation_cannot_be_classified_as_blank(array):
    with pytest.raises(RuntimeError, match="Required semantic-segmentation AOV"):
        _seg_common.segmented_coverage(array)


@pytest.mark.parametrize(
    "array",
    [
        np.zeros((2, 2, 3), dtype=np.uint8),
        np.zeros((2, 2, 4), dtype=np.uint8),
        np.zeros((2, 2), dtype=np.uint32),
        np.zeros((2, 2, 3), dtype=np.float32),
    ],
)
def test_valid_measured_blank_aov_keeps_zero_coverage(array):
    assert _seg_common.segmented_coverage(array) == 0


def test_valid_nonblank_rgb_and_normalized_color_evidence_preserve_coverage():
    rgb = np.zeros((2, 2, 4), dtype=np.uint8)
    rgb[0, :, :3] = (255, 0, 0)
    assert _seg_common.segmented_coverage(rgb) == 0.5
    assert _seg_common.segmented_coverage(rgb.astype(float) / 255.0) == 0.5


@pytest.mark.parametrize("dtype", [np.uint16, np.uint64, np.float32, np.float64])
@pytest.mark.parametrize("channels", [None, 3, 4])
def test_raw_aov_identities_are_not_collapsed_by_presentation_quantization(dtype, channels):
    observed = np.array([1000] * 900 + [1001] * 99 + [2000], dtype=dtype).reshape(20, 50)
    if channels is not None:
        observed = np.repeat(observed[..., None], channels, axis=-1)
    assert _seg_common.segmented_coverage(observed) == 0.1
    # The displayed thumbnail may quantize identities. Its colors are not the
    # observations used by the stripped or labelled acceptance threshold.
    assert _seg_common.as_rgb8(observed).dtype == np.uint8


def test_native_uint64_ids_stay_distinct_without_float64_coercion():
    first = (1 << 64) - 103
    observed = np.array([first] * 900 + [first + 1] * 99 + [(1 << 64) - 1], dtype=np.uint64).reshape(20, 50)
    assert _seg_common.segmented_coverage(observed) == 0.1


def test_float_color_identities_remain_distinct_even_when_png_colors_match():
    observed = np.zeros((2, 2, 3), dtype=np.float64)
    observed[:, :, :] = 0.5
    observed[0, 0, 0] = np.nextafter(0.5, 1.0)
    assert _seg_common.segmented_coverage(observed) == 0.25


@pytest.mark.asyncio
@pytest.mark.parametrize("module_name", ["fet011_semantics.seg_labelled", "fet011_semantics.seg_stripped"])
@pytest.mark.parametrize("path", [None, "/Missing"])
async def test_semantic_entry_requires_a_loaded_scene_prim(monkeypatch, module_name, path):
    from pxr import Usd

    definition = _definition(monkeypatch, module_name)
    ctx = _context(definition, {})
    ctx.scene = SimpleNamespace(
        stage=Usd.Stage.CreateInMemory(),
        asset=SimpleNamespace(prim_path=path),
        load_asset=lambda *args, **kwargs: None,
    )
    with pytest.raises(RuntimeError, match="Required semantic scene asset") as caught:
        await definition.func(ctx)
    assert not ctx.failed and _result_status_and_message(ctx, test_exception=caught.value)[0] == "error"
