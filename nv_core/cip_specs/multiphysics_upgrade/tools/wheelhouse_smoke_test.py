# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Prove a built wheelhouse works with no repository checkout available.

Installs the wheelhouse into a throwaway target directory with ``--no-index``,
then runs each sidecar in a subprocess whose ``PYTHONPATH`` contains only that
target. A repository import would make the check meaningless, so the isolated
environment is asserted rather than assumed.

The two sidecars are exercised as a chain, the same way a host application uses
them: multiphysics transforms the fixture, then metadata conforms the result.
That proves both bundled entry points work and that the metadata step preserves
the runtime payloads the multiphysics step produced.

Usage::

    python tools/wheelhouse_smoke_test.py _build/wheelhouse
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

MANIFEST_NAME = "wheelhouse.json"

_TOOLS_DIR = Path(__file__).resolve().parent
_FIXTURE_SCRIPT = _TOOLS_DIR / "make_fixture_asset.py"
_REPO_MARKERS = ("nv_core", "simready_foundations")

_RUNTIME_PAYLOADS = ("physx.usda", "newton.usda", "mujoco.usda")

# Provenance strings a caller must supply; the physical fields and the Q-Code are
# derived from the fixture.
_FIXTURE_METADATA = {
    "author": "SimReady Wheelhouse Smoke Test",
    "asset_name": "sm_fixture_prop_01",
    "asset_type": "prop",
    "asset_license": "Apache-2.0",
    "category": "prop",
    "source_file": "sm_fixture_prop_01.blend",
    "usd_date_generated": "2026-01-01",
}


class SmokeTestError(RuntimeError):
    """Raised when the built wheelhouse does not work in isolation."""


def load_manifest(wheelhouse: Path) -> dict[str, Any]:
    manifest_path = wheelhouse / MANIFEST_NAME
    if not manifest_path.is_file():
        raise SmokeTestError(f"missing manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify_manifest_hashes(wheelhouse: Path, manifest: dict[str, Any]) -> None:
    wheels_dir = wheelhouse / manifest.get("wheels_dir", "wheels")
    for distribution in manifest["distributions"]:
        wheel = wheels_dir / distribution["filename"]
        if not wheel.is_file():
            raise SmokeTestError(f"manifest lists a missing wheel: {wheel}")
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if digest != distribution["sha256"]:
            raise SmokeTestError(f"hash mismatch for {wheel.name}")


def install_wheelhouse(wheelhouse: Path, manifest: dict[str, Any], target: Path) -> None:
    wheels_dir = wheelhouse / manifest.get("wheels_dir", "wheels")
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--find-links",
        str(wheels_dir),
        "--target",
        str(target),
    ]
    command += [str(wheels_dir / dist["filename"]) for dist in manifest["distributions"]]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SmokeTestError(
            f"offline install failed (exit {completed.returncode}):\n{completed.stdout}\n{completed.stderr}"
        )


def isolated_environment(target: Path) -> dict[str, str]:
    """Return an environment whose only importable extra path is ``target``."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(target)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("SIMREADY_TIER_CORE_ROOT", None)
    return env


def _run_isolated(target: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        capture_output=True,
        text=True,
        env=isolated_environment(target),
        cwd=str(target),
    )


def assert_no_repository_imports(target: Path) -> None:
    probe = (
        "import json, simready.multiphysics_upgrade as m, "
        "simready.asset_transformer as t, pxr;"
        "print(json.dumps({'multiphysics': m.__file__, 'transformer': t.__file__, 'pxr': pxr.__file__}))"
    )
    completed = _run_isolated(target, ["-c", probe])
    if completed.returncode != 0:
        raise SmokeTestError(f"isolated import failed:\n{completed.stdout}\n{completed.stderr}")
    locations = json.loads(completed.stdout.strip().splitlines()[-1])
    for label, location in locations.items():
        resolved = Path(location).resolve()
        if target.resolve() not in resolved.parents:
            raise SmokeTestError(f"{label} resolved outside the wheelhouse install: {resolved}")
        if any(marker in resolved.parts for marker in _REPO_MARKERS):
            raise SmokeTestError(f"{label} resolved into a repository checkout: {resolved}")


def resolve_sidecar(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    """Look up one sidecar entry, falling back to the legacy single-sidecar keys."""
    for sidecar in manifest.get("sidecars") or ():
        if isinstance(sidecar, dict) and sidecar.get("name") == name:
            return sidecar
    if name == "multiphysics" and manifest.get("sidecar_module"):
        return {
            "name": name,
            "module": manifest["sidecar_module"],
            "protocol_version": manifest["protocol_version"],
        }
    raise SmokeTestError(f"manifest declares no sidecar named {name!r}")


def run_sidecar(
    target: Path, sidecar: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", sidecar["module"]],
        input=json.dumps({"protocol_version": sidecar["protocol_version"], **request}),
        check=False,
        capture_output=True,
        text=True,
        env=isolated_environment(target),
        cwd=str(target),
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise SmokeTestError(
            f"{sidecar['name']} sidecar emitted {len(lines)} stdout lines, "
            f"expected 1:\n{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(lines[0])


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_thumbnail(path: Path, size: int = 4) -> Path:
    """Write a valid grayscale PNG using only the standard library."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x80" * size for _ in range(size))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
    return path


def read_nested_metadata(target: Path, asset_usd: Path) -> dict[str, Any]:
    """Read SimReady_Metadata using only the wheelhouse install's USD."""
    probe = (
        "import json, sys; from pxr import Sdf; "
        "layer = Sdf.Layer.FindOrOpen(sys.argv[1]); "
        "data = dict(layer.customLayerData) if layer else {}; "
        "meta = dict(data.get('SimReady_Metadata', {})); "
        "print(json.dumps({k: str(v) for k, v in meta.items()}))"
    )
    completed = _run_isolated(target, ["-c", probe, str(asset_usd)])
    if completed.returncode != 0:
        raise SmokeTestError(
            f"could not read metadata from {asset_usd}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def run_smoke_test(wheelhouse: Path) -> int:
    """Install and exercise ``wheelhouse``; return a process exit code."""
    wheelhouse = wheelhouse.expanduser().resolve()
    try:
        manifest = load_manifest(wheelhouse)
        verify_manifest_hashes(wheelhouse, manifest)

        with tempfile.TemporaryDirectory(prefix="wheelhouse_smoke_") as tmp:
            root = Path(tmp)
            target = root / "runtime"
            install_wheelhouse(wheelhouse, manifest, target)
            assert_no_repository_imports(target)

            fixture_package = root / "asset" / "staging"
            fixture = _run_isolated(target, [str(_FIXTURE_SCRIPT), str(fixture_package)])
            if fixture.returncode != 0:
                raise SmokeTestError(
                    f"fixture creation failed:\n{fixture.stdout}\n{fixture.stderr}"
                )
            source_usd = Path(fixture.stdout.strip().splitlines()[-1])

            intermediate = root / "asset" / "multiphysics_out"
            response = run_sidecar(
                target,
                resolve_sidecar(manifest, "multiphysics"),
                {
                    "op": "neutral_to_runtimes",
                    "source_usd": str(source_usd),
                    "output_folder": str(intermediate),
                    "replace_existing": True,
                },
            )
            if not response.get("ok"):
                raise SmokeTestError(
                    f"multiphysics sidecar failed: {json.dumps(response, indent=2)}"
                )
            _assert_runtime_payloads(intermediate, source_usd.name)

            # Second phase: conform the multiphysics result, exactly as a host
            # application chains the two sidecars before one final promotion.
            output = root / "asset" / "simready_usd"
            thumbnail = write_thumbnail(root / "renders" / "thumb.png")
            transformed_usd = _transformed_usd(intermediate, source_usd.name)
            response = run_sidecar(
                target,
                resolve_sidecar(manifest, "metadata"),
                {
                    "op": "metadata_conform",
                    "source_usd": str(transformed_usd),
                    "output_folder": str(output),
                    "metadata": dict(_FIXTURE_METADATA),
                    "thumbnail_source": str(thumbnail),
                    "replace_existing": True,
                },
            )
            if not response.get("ok"):
                raise SmokeTestError(
                    f"metadata sidecar failed: {json.dumps(response, indent=2)}"
                )

            _assert_runtime_payloads(output, transformed_usd.name)
            target_thumbnail = (
                output / ".thumbs" / "256x256" / f"{transformed_usd.name}.png"
            )
            if not target_thumbnail.is_file():
                raise SmokeTestError(
                    f"conformed package is missing the SR.002 thumbnail: "
                    f"{target_thumbnail}"
                )
            metadata = read_nested_metadata(target, output / transformed_usd.name)
            missing_fields = [
                field
                for field in (
                    *_FIXTURE_METADATA,
                    "qcode",
                    "rigid_body_count",
                    "asset_extents",
                    "mass",
                )
                if field not in metadata
            ]
            if missing_fields:
                raise SmokeTestError(
                    f"conformed package is missing SR.003 fields: {missing_fields}"
                )
    except SmokeTestError as exc:
        print(f"[smoke-test] FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        "[smoke-test] wheelhouse installs, transforms, and conforms in isolation",
        flush=True,
    )
    return 0


def _transformed_usd(package: Path, source_name: str) -> Path:
    """Locate the transformed root USD, which may be re-rooted to .usda."""
    candidate = package / source_name
    if candidate.is_file():
        return candidate
    stem = Path(source_name).stem
    for suffix in (".usda", ".usd", ".usdc"):
        alternate = package / f"{stem}{suffix}"
        if alternate.is_file():
            return alternate
    raise SmokeTestError(f"transformed package is missing a root USD for {stem}")


def _assert_runtime_payloads(package: Path, source_name: str) -> None:
    payloads = package / "runnables" / "physics"
    missing = [
        name for name in _RUNTIME_PAYLOADS if not (payloads / name).is_file()
    ]
    if missing:
        raise SmokeTestError(f"{package.name} is missing runtime payloads: {missing}")
    _transformed_usd(package, source_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheelhouse", type=Path, help="Directory holding wheelhouse.json")
    args = parser.parse_args(argv)
    return run_smoke_test(args.wheelhouse)


if __name__ == "__main__":
    raise SystemExit(main())
