# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Host regressions for the real Sensors procedures; native APIs are boundary doubles.

Optional Evaluate/USD dependencies are supplied by a runtime-qualified host env.
The base tooling-only environment can still collect this suite without them.
"""

import asyncio
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pxr.Usd")
pytest.importorskip("simready.evaluate.runner.test_context")
pytest.importorskip("simready.evaluate_engine_kit.execution")
# Optional dependencies must be qualified before these imports in the tooling suite.
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdRender  # noqa: E402
from simready.evaluate.runner.test_context import RunContext  # noqa: E402
from simready.evaluate_engine_kit.execution import (  # noqa: E402
    _result_status_and_message,
)

SUITE = (
    Path(__file__).resolve().parents[2]
    / "simready_foundation_tier_sensors"
    / "simready/foundation/sensors/runtime_tests"
)


async def _noop(*args, **kwargs):
    pass


def _raise(error):
    raise error


@pytest.fixture
def host(monkeypatch, tmp_path):
    def module(name):
        value = ModuleType(name)
        value.__path__ = []
        monkeypatch.setitem(sys.modules, name, value)
        if "." in name:
            parent, child = name.rsplit(".", 1)
            if parent not in sys.modules:
                module(parent)
            monkeypatch.setattr(sys.modules[parent], child, value, raising=False)
        return value

    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/Asset").GetPrim()
    stage.SetDefaultPrim(root)
    body = UsdGeom.Xform.Define(stage, "/Asset/Body").GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(body)
    UsdGeom.Camera.Define(stage, "/Asset/Camera")
    usd = module("omni.usd")
    usd.get_context = lambda: SimpleNamespace(get_stage=lambda: stage)
    commands = module("omni.kit.commands")
    commands.execute = lambda *a, **k: None
    rep = module("omni.replicator.core")
    native = module("isaacsim.sensors.experimental.physics")
    monkeypatch.setattr(Usd.Stage, "Open", lambda path: stage)

    attached = []

    class Writer:
        def attach(self, render_products):
            attached.append((self, render_products))

        def detach(self):
            attached[:] = [entry for entry in attached if entry[0] is not self]

    class Orchestrator:
        stopped = False
        steps = 0
        # Frames at the start of a run that the render product does not deliver.
        skip_frames = 0
        values = {}
        preview_async = staticmethod(_noop)

        async def step_async(self, *args, **kwargs):
            """Deliver one frame to every attached writer, as Replicator does for a rendered frame."""
            self.steps += 1
            if self.steps <= self.skip_frames:
                return
            for writer, render_products in list(attached):
                frame = {}
                for annotator in writer.annotators:
                    value = self.values[annotator.name]
                    if isinstance(value, Exception):
                        raise value
                    frame[annotator.name] = value() if callable(value) else value
                writer.write({"renderProducts": {path: frame for path in render_products}})

        def stop(self):
            self.stopped = True

    registry = {}
    rep.Writer = Writer
    rep.WriterRegistry = SimpleNamespace(
        get_writers=lambda: registry, register=lambda writer: registry.__setitem__(writer.__name__, writer)
    )
    rep.writers = SimpleNamespace(get=lambda name, init_params=None: registry[name](**(init_params or {})))
    rep.orchestrator = Orchestrator()
    rep.create = SimpleNamespace(render_product=lambda *a: SimpleNamespace(path="/Render/Runtime"))

    def load(relative):
        path = SUITE / (relative + ".py")
        spec = importlib.util.spec_from_file_location("_sensor_regression_" + path.stem, path)
        value = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, value)
        spec.loader.exec_module(value)
        assert Path(value.__file__).resolve() == path.resolve()
        return value

    def context(name):
        scene = SimpleNamespace(
            load_asset=lambda *a, **k: SimpleNamespace(prim_path="/Asset"),
            add_physics=lambda **k: SimpleNamespace(play=lambda: None),
            enable_ground_plane=lambda **k: None,
        )
        return RunContext(
            "fixture.usda",
            "fixture.usda",
            str(tmp_path),
            name,
            "0.1.0",
            "",
            "kit",
            "host",
            "host",
            scene,
            config={
                "asset_load_timeout": 30,
                "warmup_frames": 30,
                "max_capture_steps": 10,
                "simulation_frames": 80,
                "initial_angular_velocity_y": 5.0,
            },
            engine_session=SimpleNamespace(settle=_noop, step_one=_noop),
        )

    def render(kind, values):
        names = list(values)
        rp = UsdRender.Product.Define(stage, "/Render/Product")
        rp.CreateCameraRel().SetTargets([Sdf.Path("/Asset/Camera")])
        targets = []
        for i, name in enumerate(names):
            var = UsdRender.Var.Define(stage, f"/Render/Var{i}")
            var.CreateSourceNameAttr().Set(name)
            targets.append(var.GetPath())
        rp.CreateOrderedVarsRel().SetTargets(targets)

        rep.orchestrator.values = dict(values)
        if "SemanticSegmentation" in values:
            rep.orchestrator.values["semantic_segmentation"] = values["SemanticSegmentation"]
        rep.annotators = SimpleNamespace(get=lambda name: SimpleNamespace(name=name))
        mod = load("fet035_render_products/" + kind)
        return mod, context(kind)

    def imu(readings):
        for i in range(len(readings)):
            stage.DefinePrim(f"/Asset/Body/IMU{i}", "IsaacImuSensor")

        class Sensor:
            def __init__(self, path):
                self.value = readings[int(path.rsplit("IMU", 1)[1])]
                self.index = 0
                if isinstance(self.value, Exception):
                    raise self.value

            def get_data(self):
                value = self.value
                if isinstance(value, list):
                    value = value[min(self.index, len(value) - 1)]
                    self.index += 1
                if isinstance(value, Exception):
                    raise value
                return value

        native.IMUSensor = Sensor
        return load("fet034_physics_sensors/imu_sensor_data"), context("imu_sensor_data")

    return SimpleNamespace(stage=stage, rep=rep, render=render, imu=imu, tmp_path=tmp_path, attached=attached)


def _execute(mod, ctx):
    error = None
    try:
        asyncio.run(getattr(mod, "test_" + ctx.test_name)(ctx))
    except Exception as exc:
        error = exc
    status, message = _result_status_and_message(ctx, error)
    return status, message, error


def _assert_error(result, fragment):
    status, message, error = result
    assert status == "error", (status, message)
    assert fragment in message
    assert "How to fix" not in message
    assert error is not None
    return error


@pytest.mark.parametrize(
    "kind,name,operation",
    [
        (kind, name, operation)
        for kind, name in [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
        for operation in ["create", "lookup", "attach", "preview", "step", "read"]
        if operation != "preview" or kind == "render_product_output"
    ],
)
def test_required_render_acquisition_errors_are_errors_and_stop(host, monkeypatch, kind, name, operation):
    cause = RuntimeError("GPU acquisition unavailable")
    mod, ctx = host.render(kind, {name: cause if operation == "read" else np.zeros((2, 2), dtype=np.uint32)})
    if operation == "create":
        monkeypatch.setattr(host.rep.create, "render_product", lambda *a: _raise(cause))
    elif operation == "lookup":
        monkeypatch.setattr(host.rep.annotators, "get", lambda name: _raise(cause))
    elif operation == "attach":
        monkeypatch.setattr(
            host.rep.writers, "get", lambda *a, **k: SimpleNamespace(attach=lambda paths: _raise(cause))
        )
    elif operation in ("step", "preview"):

        async def fail_step():
            raise cause

        monkeypatch.setattr(host.rep.orchestrator, operation + "_async", fail_step)
    error = _assert_error(_execute(mod, ctx), "GPU acquisition unavailable")
    assert error is cause or error.__cause__ is cause
    assert host.rep.orchestrator.stopped
    assert not ctx.failed


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_stop_failure_cannot_replace_readback_cause(host, monkeypatch, kind, name):
    cause = RuntimeError("original readback cause")
    mod, ctx = host.render(kind, {name: cause})

    def stop():
        host.rep.orchestrator.stopped = True
        raise RuntimeError("secondary stop failure")

    monkeypatch.setattr(host.rep.orchestrator, "stop", stop)
    error = _assert_error(_execute(mod, ctx), "original readback cause")
    assert error is cause or error.__cause__ is cause
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize(
    "value",
    [None, [], np.array([]), {}, {"data": None}, {"info": {"idToLabels": {}}}, np.array([None]), "not image data"],
)
def test_semantic_unavailable_or_malformed_data_is_not_pass(host, value):
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": value})
    _assert_error(_execute(mod, ctx), "SemanticSegmentation")
    assert host.rep.orchestrator.stopped
    assert not list(host.tmp_path.glob("*.png"))


@pytest.mark.parametrize(
    "value",
    [np.zeros((2, 2), dtype=np.uint32), {"data": np.zeros((2, 2), dtype=np.uint32), "info": {"idToLabels": {}}}],
)
def test_semantic_real_zero_output_passes_and_publishes_image(host, value):
    pytest.importorskip("PIL")
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": value})
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["data_failures"]["value"] == 0
    assert (host.tmp_path / "Product_SemanticSegmentation.png").is_file()


@pytest.mark.parametrize("reserved", ["UNLABELLED", "unlabeled", "BACKGROUND"])
@pytest.mark.parametrize("nested", [False, True], ids=["string-labels", "semantic-type-labels"])
def test_semantic_preview_uses_labels_and_preserves_mapping(host, reserved, nested):
    Image = pytest.importorskip("PIL.Image")
    labels = {"0": "BACKGROUND", "7": reserved, "12": "qa_left_class", "20": "qa_other_class"}
    if nested:
        labels = {key: {"class": value} for key, value in labels.items()}
    pixels = np.array([[0, 12, 7, 20]], dtype=np.uint32)
    payload = {"data": pixels, "info": {"idToLabels": labels}}
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": payload})
    assert _execute(mod, ctx)[:2] == ("pass", "")
    with Image.open(host.tmp_path / "Product_SemanticSegmentation.png") as image:
        rgb = np.array(image)
    assert not rgb[0, 0].any()
    assert not rgb[0, 2].any(), "An unlabelled object must not look like a semantic class"
    assert rgb[0, 1].any() and rgb[0, 3].any()
    assert not np.array_equal(rgb[0, 1], rgb[0, 3])
    metadata = json.loads((host.tmp_path / "Product_SemanticSegmentation.json").read_text())
    assert metadata["idToLabels"] == labels
    assert metadata["unmappedIds"] == []
    for index, uid in enumerate(pixels[0]):
        assert metadata["idToColor"][str(uid)] == rgb[0, index].tolist()


@pytest.mark.parametrize("legacy", [False, True], ids=["writer-payload", "legacy-payload"])
def test_semantic_raw_aov_uses_label_aware_annotator(host, legacy):
    pytest.importorskip("PIL")
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": np.array([[2]], dtype=np.uint32)})
    metadata = {"idToLabels": {"2": {"class": "labelled_cube"}}}
    host.rep.orchestrator.values["semantic_segmentation"] = {
        "data": np.array([[2]], dtype=np.uint32),
        **({"info": metadata} if legacy else metadata),
    }
    assert _execute(mod, ctx)[:2] == ("pass", "")
    metadata = json.loads((host.tmp_path / "Product_SemanticSegmentation.json").read_text())
    assert metadata["idToLabels"] == {"2": {"class": "labelled_cube"}}
    assert metadata["idToColor"]["2"] != [0, 0, 0]


@pytest.mark.parametrize("info", [None, {}, {"idToLabels": {}}, {"idToLabels": {9: {"class": ""}}}])
def test_semantic_missing_labels_are_visible_diagnostics_not_invented_classes(host, monkeypatch, info):
    Image = pytest.importorskip("PIL.Image")
    payload = {"data": np.array([[0, 9]], dtype=np.uint32), "info": info}
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": payload})
    logs = []
    monkeypatch.setattr(ctx, "log", logs.append)
    assert _execute(mod, ctx)[:2] == ("pass", "")
    with Image.open(host.tmp_path / "Product_SemanticSegmentation.png") as image:
        assert not np.array(image).any()
    metadata = json.loads((host.tmp_path / "Product_SemanticSegmentation.json").read_text())
    assert metadata["unmappedIds"] == [9]
    assert any("WARN" in line and "no label metadata" in line for line in logs)


def test_semantic_preview_uses_metadata_from_captured_frame(host):
    Image = pytest.importorskip("PIL.Image")
    frames = iter([
        {"data": np.array([], dtype=np.uint32), "info": {"idToLabels": {1: {"class": "old_class"}}}},
        {"data": np.array([[1, 8]], dtype=np.uint32),
         "info": {"idToLabels": {1: {"class": "UNLABELLED"}, 8: {"class": "current_class"}}}},
    ])
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": lambda: next(frames)})
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert host.rep.orchestrator.steps == 2
    metadata = json.loads((host.tmp_path / "Product_SemanticSegmentation.json").read_text())
    assert metadata["idToLabels"] == {"1": {"class": "UNLABELLED"}, "8": {"class": "current_class"}}
    with Image.open(host.tmp_path / "Product_SemanticSegmentation.png") as image:
        assert image.getpixel((0, 0)) == (0, 0, 0)
        assert image.getpixel((1, 0)) != (0, 0, 0)


def test_semantic_diagnostic_write_error_warns_without_changing_verdict(host, monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    mod, ctx = host.render("semantic_aov_output", {"SemanticSegmentation": np.zeros((2, 2), dtype=np.uint32)})
    monkeypatch.setattr(Image.Image, "save", lambda *a, **k: _raise(OSError("diagnostic write failed")))
    logs = []
    monkeypatch.setattr(ctx, "log", logs.append)
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert any("WARN" in line and "diagnostic write failed" in line for line in logs)


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_optional_image_failure_does_not_invalidate_measurement(host, monkeypatch, kind, name):
    mod, ctx = host.render(kind, {name: np.ones((2, 2), dtype=np.uint32)})
    monkeypatch.setattr(mod.os, "makedirs", lambda *a, **k: _raise(OSError("disk unavailable")))
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert not list(host.tmp_path.glob("*.png"))


def test_healthy_annotator_cannot_hide_unavailable_sibling(host):
    mod, ctx = host.render(
        "render_product_output", {"LdrColor": np.ones((2, 2)), "normals": RuntimeError("second annotator unavailable")}
    )
    _assert_error(_execute(mod, ctx), "second annotator unavailable")


def test_finite_zero_geometry_remains_measured_failure(host):
    mod, ctx = host.render("render_product_output", {"normals": np.zeros((2, 2))})
    status, message, error = _execute(mod, ctx)
    assert status == "fail"
    assert "all-zero" in message
    assert error is None


def test_reference_geometry_setup_error_does_not_become_measured_failure(host, monkeypatch):
    mod, ctx = host.render("render_product_output", {"normals": np.zeros((2, 2))})
    cause = RuntimeError("reference geometry setup unavailable")
    monkeypatch.setattr(UsdGeom.Cube, "Define", lambda *a: _raise(cause))
    error = _assert_error(_execute(mod, ctx), "reference geometry setup unavailable")
    assert error is cause or error.__cause__ is cause
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_stop_failure_without_primary_error_is_execution_error(host, monkeypatch, kind, name):
    mod, ctx = host.render(kind, {name: np.ones((2, 2), dtype=np.uint32)})
    cause = RuntimeError("required stop unavailable")
    monkeypatch.setattr(host.rep.orchestrator, "stop", lambda: _raise(cause))
    assert _assert_error(_execute(mod, ctx), "required stop unavailable") is cause


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_scene_setup_exception_still_stops_replicator(host, kind, name):
    mod, ctx = host.render(kind, {name: np.ones((2, 2), dtype=np.uint32)})
    cause = RuntimeError("asset setup unavailable")
    ctx.scene.load_asset = lambda *a, **k: _raise(cause)
    assert _assert_error(_execute(mod, ctx), "asset setup unavailable") is cause
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize("value", [None, [], {"data": None}, {"info": [1, 2]}, np.array([None])])
def test_render_unavailable_output_is_execution_error(host, value):
    mod, ctx = host.render("render_product_output", {"LdrColor": value})
    _assert_error(_execute(mod, ctx), "LdrColor")
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_output_that_arrives_after_a_few_frames_is_waited_for(host, kind, name):
    def output():
        return np.ones((2, 2), dtype=np.uint32) if host.rep.orchestrator.steps > 3 else np.array([])

    mod, ctx = host.render(kind, {name: output})
    status, message, error = _execute(mod, ctx)
    assert status == "pass", (status, message)
    assert host.rep.orchestrator.steps == 4


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_steps_that_deliver_no_frame_are_waited_past(host, kind, name):
    mod, ctx = host.render(kind, {name: np.ones((2, 2), dtype=np.uint32)})
    host.rep.orchestrator.skip_frames = 3
    status, message, error = _execute(mod, ctx)
    assert status == "pass", (status, message)
    assert host.rep.orchestrator.steps == 4
    assert ctx.metrics["max_frames_to_data"]["value"] == 4


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_render_product_that_never_delivers_a_frame_is_execution_error(host, kind, name):
    mod, ctx = host.render(kind, {name: np.ones((2, 2), dtype=np.uint32)})
    host.rep.orchestrator.skip_frames = 100
    _assert_error(_execute(mod, ctx), "None returned) after 10 frames")


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_output_that_never_arrives_reports_the_frames_waited(host, kind, name):
    mod, ctx = host.render(kind, {name: lambda: np.array([])})
    _assert_error(_execute(mod, ctx), "after 10 frames")


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
@pytest.mark.parametrize("fails", [False, True], ids=["pass", "error"])
def test_render_product_is_destroyed_after_check(host, monkeypatch, kind, name, fails):
    destroyed = []
    monkeypatch.setattr(
        host.rep.create,
        "render_product",
        lambda *a: SimpleNamespace(path="/Render/Runtime", destroy=lambda: destroyed.append(1)),
    )
    mod, ctx = host.render(kind, {name: RuntimeError("readback broke") if fails else np.ones((2, 2), dtype=np.uint32)})
    status, message, error = _execute(mod, ctx)
    assert status == ("error" if fails else "pass"), (status, message)
    assert destroyed == [1]
    assert not host.attached


_AOV_PROCEDURES = [
    ("render_product_output", "LdrColor"),
    ("render_product_output", "normals"),
    ("semantic_aov_output", "SemanticSegmentation"),
]


@pytest.mark.parametrize("kind,name", _AOV_PROCEDURES)
@pytest.mark.parametrize("wrapped", [False, True], ids=["array", "dict-data"])
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(np.full((2, 2), np.nan), id="all-nan"),
        pytest.param(np.full((2, 2), np.inf), id="all-pos-inf"),
        pytest.param(np.full((2, 2), -np.inf), id="all-neg-inf"),
        pytest.param(np.array([[np.nan, np.inf], [-np.inf, np.nan]]), id="mixed-no-finite"),
    ],
)
def test_numeric_aov_without_finite_samples_is_execution_error(host, kind, name, wrapped, value):
    payload = {"data": value, "info": {"description": "not measurement"}} if wrapped else value
    mod, ctx = host.render(kind, {name: payload})
    _assert_error(_execute(mod, ctx), "no finite samples")
    assert not ctx.failed
    assert host.rep.orchestrator.stopped
    assert not list(host.tmp_path.glob("*.png"))
    assert "data_failures" not in ctx.metrics


@pytest.mark.parametrize("kind,name", _AOV_PROCEDURES)
@pytest.mark.parametrize("wrapped", [False, True], ids=["array", "dict-data"])
@pytest.mark.parametrize("finite_value", [0.0, 1.0])
def test_mixed_numeric_aov_retains_existing_content_checks(host, kind, name, wrapped, finite_value):
    value = np.array([[finite_value, np.nan], [np.inf, -np.inf]])
    mod, ctx = host.render(kind, {name: {"data": value} if wrapped else value})
    # Geometry's existing any-nonzero check still accepts mixed nonfinite data;
    # sample availability does not impose a new finite-pixel content criterion.
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["data_failures"]["value"] == 0
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize(
    "kind,name,want",
    [("render_product_output", "normals", "fail"), ("semantic_aov_output", "SemanticSegmentation", "pass")],
)
@pytest.mark.parametrize("wrapped", [False, True], ids=["array", "dict-data"])
def test_finite_sample_availability_preserves_zero_aov_verdicts(host, kind, name, want, wrapped):
    value = np.zeros((2, 2), dtype=np.uint32)
    mod, ctx = host.render(kind, {name: {"data": value} if wrapped else value})
    assert _execute(mod, ctx)[0] == want
    assert host.rep.orchestrator.stopped


@pytest.mark.parametrize(
    "kind,name", [("render_product_output", "LdrColor"), ("semantic_aov_output", "SemanticSegmentation")]
)
def test_stop_failure_preserves_unavailable_numeric_aov_cause(host, monkeypatch, kind, name):
    mod, ctx = host.render(kind, {name: np.full((2, 2), np.nan)})
    monkeypatch.setattr(host.rep.orchestrator, "stop", lambda: _raise(RuntimeError("secondary stop failure")))
    result = _execute(mod, ctx)
    error = _assert_error(result, "no finite samples")
    assert "secondary stop failure" not in result[1]
    assert isinstance(error.__cause__, RuntimeError)
    assert "no finite samples" in str(error.__cause__)


GOOD = {"angular_velocity": (0.0, 0.09, 0.0), "linear_acceleration": (0.0, 0.94, 0.0)}


@pytest.mark.parametrize(
    "frame",
    [
        None,
        {},
        {"angular_velocity": (), "linear_acceleration": ()},
        {"angular_velocity": (float("nan"), 0, 0), "linear_acceleration": (1, 0, 0)},
        {"angular_velocity": (1, 0, 0), "linear_acceleration": (float("inf"), 0, 0)},
        {"angular_velocity": (1, 0, 0)},
        {"linear_acceleration": (1, 0, 0)},
    ],
)
def test_unavailable_imu_channels_do_not_become_measured_zeros(host, frame):
    mod, ctx = host.imu([frame])
    _assert_error(_execute(mod, ctx), "IMU")
    assert not ctx.failed
    assert "imu_peak_angular_velocity_rad_s" not in ctx.metrics
    assert "imu_peak_linear_acceleration_ms2" not in ctx.metrics


MALFORMED_IMU_VECTORS = [
    pytest.param("111", id="scalar-string"),
    pytest.param(("0", "0.09", "0"), id="string-components"),
    pytest.param((True, True, True), id="bool-components"),
    pytest.param((0.0, True, 0.0), id="mixed-bool-components"),
    pytest.param(np.array([0.0, 0.94, 0.0], dtype=object), id="object-dtype"),
    pytest.param(np.array([0.0, 0.94, 0.0], dtype=complex), id="complex-dtype"),
    pytest.param(np.array([[0.0], [0.94], [0.0]]), id="column-shape"),
    pytest.param({1: 1, 2: 1, 3: 1}, id="numeric-key-mapping"),
]


@pytest.mark.parametrize("vector", MALFORMED_IMU_VECTORS)
def test_malformed_imu_vector_cannot_establish_channel_evidence(host, vector):
    mod, ctx = host.imu([{"angular_velocity": vector, "linear_acceleration": vector}])
    _assert_error(_execute(mod, ctx), "IMU")
    assert not ctx.failed
    assert "imu_peak_angular_velocity_rad_s" not in ctx.metrics
    assert "imu_peak_linear_acceleration_ms2" not in ctx.metrics
    assert not (host.tmp_path / "imu_sensor_recording.csv").exists()


@pytest.mark.parametrize("vector", MALFORMED_IMU_VECTORS)
def test_malformed_imu_frame_is_blank_until_real_samples_arrive(host, vector):
    mod, ctx = host.imu([[{"angular_velocity": vector, "linear_acceleration": vector}, GOOD]])
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["imu_peak_angular_velocity_rad_s"]["value"] == 0.09
    assert ctx.metrics["imu_peak_linear_acceleration_ms2"]["value"] == 0.94
    with (host.tmp_path / "imu_sensor_recording.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 80
    for column in ("lin_accel_x", "lin_accel_y", "lin_accel_z", "ang_vel_x", "ang_vel_y", "ang_vel_z"):
        assert rows[0][column] == ""
    assert rows[1]["ang_vel_y"] == "0.09"
    assert rows[1]["lin_accel_y"] == "0.94"


@pytest.mark.parametrize(
    "vector",
    [(1, 0, 0), np.array([1, 0, 0], dtype=np.uint32), np.array([1, 0, 0], dtype=np.float32), Gf.Vec3f(1, 0, 0)],
)
def test_real_numeric_imu_vector_formats_still_measure(host, vector):
    mod, ctx = host.imu([{"angular_velocity": vector, "linear_acceleration": vector}])
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["imu_peak_angular_velocity_rad_s"]["value"] == 1.0
    assert ctx.metrics["imu_peak_linear_acceleration_ms2"]["value"] == 1.0


@pytest.mark.parametrize("missing", [None, {}, {"angular_velocity": (), "linear_acceleration": ()}])
def test_imu_startup_gaps_are_qualified_over_full_window(host, missing):
    mod, ctx = host.imu([[missing, missing, GOOD, missing]])
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["imu_peak_angular_velocity_rad_s"]["value"] == 0.09
    with (host.tmp_path / "imu_sensor_recording.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 80
    assert rows[0]["ang_vel_y"] == ""
    assert rows[2]["ang_vel_y"] == "0.09"
    assert rows[0]["lin_accel_y"] == ""


@pytest.mark.parametrize(
    "readings",
    [
        [GOOD, {}],
        [GOOD, RuntimeError("partial sensor construction")],
        [RuntimeError("sensor construction unavailable")],
    ],
)
def test_each_required_imu_must_initialize_and_have_both_channels(host, readings):
    mod, ctx = host.imu(readings)
    error = _assert_error(_execute(mod, ctx), "IMU")
    if isinstance(readings[-1], Exception):
        assert error is readings[-1] or error.__cause__ is readings[-1]
    assert not ctx.skipped


@pytest.mark.parametrize("operation", ["read", "step", "spin"])
def test_required_imu_setup_and_acquisition_errors_preserve_cause(host, monkeypatch, operation):
    cause = RuntimeError("IMU required acquisition unavailable")
    mod, ctx = host.imu([[cause] if operation == "read" else GOOD])
    if operation == "step":

        async def step():
            raise cause

        ctx._engine_session.step_one = step
    elif operation == "spin":
        monkeypatch.setattr(Usd.Attribute, "Set", lambda *a: _raise(cause))
    error = _assert_error(_execute(mod, ctx), "IMU required acquisition unavailable")
    assert error is cause or error.__cause__ is cause


@pytest.mark.parametrize("angular,linear", [(0.0, 0.0), (0.01, 0.1), (0.049, 0.499)])
def test_finite_below_threshold_imu_data_remains_measured_failure(host, angular, linear):
    mod, ctx = host.imu([{"angular_velocity": (0, angular, 0), "linear_acceleration": (0, linear, 0)}])
    assert _execute(mod, ctx)[0] == "fail"
    assert ctx.metrics["imu_peak_angular_velocity_rad_s"]["value"] == angular
    assert ctx.metrics["imu_peak_linear_acceleration_ms2"]["value"] == linear


def test_imu_peaks_remain_pooled_across_required_sensors(host):
    mod, ctx = host.imu(
        [
            {"angular_velocity": (0, 0.09, 0), "linear_acceleration": (0, 0.1, 0)},
            {"angular_velocity": (0, 0.01, 0), "linear_acceleration": (0, 0.94, 0)},
        ]
    )
    assert _execute(mod, ctx)[:2] == ("pass", "")
    assert ctx.metrics["imu_peak_angular_velocity_rad_s"]["value"] == 0.09
    assert ctx.metrics["imu_peak_linear_acceleration_ms2"]["value"] == 0.94
    velocity = host.stage.GetPrimAtPath("/Asset/Body").GetAttribute("physics:angularVelocity").Get()
    # Config is rad/s; physics:angularVelocity is deg/s.
    assert velocity == Gf.Vec3f(0, math.degrees(5.0), 0)
    assert ctx.metrics["imu_initial_angular_velocity_rad_s"]["value"] == 5.0
