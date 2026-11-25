# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The synthetic fixture generator derives SR.001 extents from scalar dimensions."""
import json
from pathlib import Path

import pytest
from pxr import Sdf


@pytest.mark.parametrize("vector", [None, [111.0, 222.0, 333.0]])
def test_fixture_extents_use_scalar_dimensions(tmp_path, monkeypatch, vector):
    source_dir = Path(__file__).parent / "fixtures" / "synthetic"
    monkeypatch.syspath_prepend(str(source_dir))
    import build_synthetic_fixtures as builder

    values = json.loads((source_dir / "sources" / "generic_ups.json").read_text())
    if vector is None:
        del values["aif:core:overallGeometryDimensions"]
    else:
        values["aif:core:overallGeometryDimensions"] = ["float3", vector]
    (tmp_path / "ups.json").write_text(json.dumps(values))
    classes = builder.load_classes(Path(__file__).resolve().parents[4])
    builder.emit(tmp_path, "ups", "Synthetic_UPS", "ups.json", builder.SAMPLES, classes, write=True)

    layer = Sdf.Layer.FindOrOpen(str(tmp_path / builder.SAMPLES / "Synthetic_UPS/asset/Synthetic_UPS.usda"))
    assert list(layer.customLayerData["SimReady_Metadata"]["asset_extents"]) == pytest.approx([2.4, 0.9, 2.0])
