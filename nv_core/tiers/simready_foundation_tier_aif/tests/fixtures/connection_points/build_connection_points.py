# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Generate the six equipment connection-point layers from values.json.

Run with a USD Python runtime. Without --write this reports the intended
outputs. The source records fictional operating points and their rationale;
it must not be treated as OEM engineering data.
"""
import argparse
import json
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
# Four complete equipment assets are published samples and live outside the
# test tree. A path written "samples/..." resolves there.
SAMPLES = Path(__file__).resolve().parents[6] / "sample_content" / "aif"


def resolve(rel):
    """Resolve an asset path written relative to the fixtures tree."""
    return SAMPLES / rel[len("samples/"):] if rel.startswith("samples/") else FIXTURES / rel


def load_values():
    return json.loads((HERE / 'values.json').read_text())


def layer_text(asset_name):
    asset = load_values()[asset_name]
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, '/' + asset['root_prim'])
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(stage, 'Z')
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    scope = root.GetPath().AppendChild('ConnectionPoints')
    UsdGeom.Scope.Define(stage, scope)
    for name, source in asset['ports'].items():
        frame = UsdGeom.Xform.Define(stage, scope.AppendChild(name))
        frame.CreatePurposeAttr('guide')
        # A right-handed rigid frame: +Z faces out of the equipment, local
        # X/Y span the interface. Dimensions live in properties, never scale.
        normal = Gf.Vec3d(*source['normal']).GetNormalized()
        vertical = Gf.Vec3d(0, 0, 1) if abs(normal[2]) < .9 else Gf.Vec3d(0, 1, 0)
        horizontal = Gf.Cross(vertical, normal).GetNormalized()
        vertical = Gf.Cross(normal, horizontal).GetNormalized()
        matrix = Gf.Matrix4d(1)
        for i, axis in enumerate((horizontal, vertical, normal)):
            matrix.SetRow(i, Gf.Vec4d(*axis, 0))
        matrix.SetRow(3, Gf.Vec4d(*source['position'], 1))
        frame.AddTransformOp().Set(matrix)
        for prop, (type_name, value, _) in source['properties'].items():
            if value is None:
                raise ValueError(f'Missing value: {asset_name}/{name}/{prop}')
            frame.GetPrim().CreateAttribute(prop, Sdf.ValueTypeNames.Find(type_name), custom=True).Set(value)
    return stage.GetRootLayer().ExportToString()


def main(write=False):
    for name, asset in load_values().items():
        target = resolve(asset['layer'])
        text = layer_text(name)
        if write:
            # Preserve the existing filename/format, including binary .usd.
            layer = Sdf.Layer.CreateAnonymous()
            if not layer.ImportFromString(text):
                raise ValueError(f'Invalid generated layer: {name}')
            layer.Export(str(target))
        print(f'{name}: {len(asset["ports"])} ports -> {asset["layer"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    main(parser.parse_args().write)
