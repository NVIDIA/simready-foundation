# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared USD and PNG fixtures for metadata conformance tests."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Provenance strings a caller must supply; the physical fields and qcode come
# from the asset.
COMPLETE_METADATA = {
    "author": "Asset Team",
    "asset_name": "sm_test_prop_01",
    "asset_type": "prop",
    "asset_license": "Apache-2.0",
    "category": "prop",
    "source_file": "sm_test_prop_01.blend",
    "usd_date_generated": "2026-09-01",
}


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, width: int = 4, height: int = 4, value: int = 128) -> Path:
    """Write a valid 8-bit grayscale PNG without needing an imaging library."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes([value]) * width for _ in range(height))
    path.write_bytes(
        PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )
    return path


def corrupt_png(path: Path) -> Path:
    """Write a file with a PNG signature but a broken chunk CRC."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(">IIBBBBB", 4, 4, 8, 0, 0, 0, 0)
    good = _chunk(b"IHDR", header)
    path.write_bytes(PNG_SIGNATURE + good[:-4] + b"\x00\x00\x00\x00")
    return path


def write_metadata_package(
    package_root: Path,
    usd_name: str = "sm_test_prop_01.usda",
    *,
    mass: float | None = 2.5,
    qcode: str | None = "Q42177",
    with_geometry: bool = True,
) -> Path:
    """Write a minimal NP.005 package and return its root USD.

    Layout is ``<package_root>/simready_usd/<usd_name>``, which is what the
    conformance chain assumes when no explicit package root is given.
    """
    usd_dir = Path(package_root) / "simready_usd"
    usd_dir.mkdir(parents=True, exist_ok=True)
    usd_path = usd_dir / usd_name

    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())

    if with_geometry:
        mesh = UsdGeom.Mesh.Define(stage, "/RootNode/Geometry/mesh")
        # A closed tetrahedron, so the mass plausibility report has a volume.
        mesh.CreatePointsAttr(
            [
                Gf.Vec3f(0, 0, 0),
                Gf.Vec3f(1, 0, 0),
                Gf.Vec3f(0, 1, 0),
                Gf.Vec3f(0, 0, 1),
            ]
        )
        mesh.CreateFaceVertexCountsAttr([3, 3, 3, 3])
        mesh.CreateFaceVertexIndicesAttr(
            [0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, 3]
        )
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())

    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    mass_api = UsdPhysics.MassAPI.Apply(root.GetPrim())
    if mass is not None:
        mass_api.CreateMassAttr(float(mass))

    if qcode is not None:
        attr = root.GetPrim().CreateAttribute(
            "semantics:labels:wikidata_qcode",
            Sdf.ValueTypeNames.TokenArray,
            custom=False,
        )
        attr.Set([qcode])

    stage.GetRootLayer().Save()
    return usd_path


def add_unanchored_reference(
    asset_usd: Path, referenced_name: str = "part_01.usda"
) -> Path:
    """Add a package-local reference authored as a bare filename.

    The referenced layer is written into a subdirectory so the authored path
    cannot resolve until it is anchored, which is exactly the AA.001 case.
    """
    asset_usd = Path(asset_usd)
    parts_dir = asset_usd.parent / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    referenced = parts_dir / referenced_name
    part_stage = Usd.Stage.CreateNew(str(referenced))
    part_root = UsdGeom.Xform.Define(part_stage, "/Part")
    part_stage.SetDefaultPrim(part_root.GetPrim())
    part_stage.GetRootLayer().Save()
    del part_stage

    layer = Sdf.Layer.FindOrOpen(str(asset_usd))
    prim_spec = Sdf.CreatePrimInLayer(layer, Sdf.Path("/RootNode/Part"))
    prim_spec.specifier = Sdf.SpecifierDef
    prim_spec.referenceList.explicitItems = [Sdf.Reference(referenced_name, "/Part")]
    layer.Save()
    return referenced


def read_simready_metadata(asset_usd: Path) -> dict:
    """Read the nested SimReady_Metadata dictionary from a root layer."""
    layer = Sdf.Layer.FindOrOpen(str(Path(asset_usd)))
    if layer is None:
        return {}
    value = dict(layer.customLayerData).get("SimReady_Metadata", {})
    return dict(value) if value else {}
