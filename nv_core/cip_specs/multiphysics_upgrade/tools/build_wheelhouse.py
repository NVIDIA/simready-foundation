# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build the offline wheelhouse that host applications install from.

Produces a self-contained directory holding every wheel needed to run the
SimReady sidecars on a target interpreter, the third-party license files
extracted from those wheels, and a manifest with versions and SHA-256 hashes.
Hosts install from it with ``pip install --no-index --find-links`` and verify
the manifest before trusting the install.

One bundle carries every sidecar. The multiphysics and metadata packages share
``usd-core`` and one install target, so shipping two wheelhouses would duplicate
the largest wheels and give a host two install states to keep in sync. The
manifest therefore lists each sidecar in ``sidecars``, and keeps the original
``sidecar_module`` / ``protocol_version`` keys pointing at multiphysics so a host
built against the single-sidecar manifest still works.

Usage::

    python tools/build_wheelhouse.py --output _build/wheelhouse
    python tools/build_wheelhouse.py --output _build/wheelhouse --skip-smoke-test
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Any, NamedTuple

MANIFEST_NAME = "wheelhouse.json"
MANIFEST_SCHEMA_VERSION = 1
WHEELS_DIRNAME = "wheels"
LICENSES_DIRNAME = "licenses"

SIDECAR_MODULE = "simready.multiphysics_upgrade.sidecar"

DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_ABI = "cp312"
DEFAULT_IMPLEMENTATION = "cp"
DEFAULT_PLATFORM = "win_amd64"

_TOOLS_DIR = Path(__file__).resolve().parent
_PACKAGE_ROOT = _TOOLS_DIR.parent
_CIP_SPECS = _PACKAGE_ROOT.parent
_TIER_ROOT = _CIP_SPECS.parent / "tiers" / "simready_foundation_tier_core"
_METADATA_ROOT = _CIP_SPECS / "metadata_conform"
_RUNTIME_REQUIREMENTS = _TOOLS_DIR / "requirements-runtime.txt"

_LOCAL_PROJECTS = (_PACKAGE_ROOT, _TIER_ROOT, _METADATA_ROOT)

_LICENSE_FILE_HINTS = ("license", "licence", "copying", "notice", "authors")


class Sidecar(NamedTuple):
    """One JSON sidecar entry point shipped in the bundle."""

    name: str
    module: str
    distribution: str
    protocol_path: Path


# ``name`` is the stable key a host looks the sidecar up by; adding a sidecar here
# does not change how any existing one is resolved.
SIDECARS = (
    Sidecar(
        name="multiphysics",
        module=SIDECAR_MODULE,
        distribution="simready-multiphysics-upgrade",
        protocol_path=(
            _PACKAGE_ROOT / "src" / "simready" / "multiphysics_upgrade" / "protocol.py"
        ),
    ),
    Sidecar(
        name="metadata",
        module="simready.metadata_conform.sidecar",
        distribution="simready-metadata-conform",
        protocol_path=(
            _METADATA_ROOT / "src" / "simready" / "metadata_conform" / "protocol.py"
        ),
    ),
)


class BuildError(RuntimeError):
    """Raised when the wheelhouse cannot be produced."""


def _run(command: list[str], *, description: str) -> None:
    print(f"[wheelhouse] {description}", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise BuildError(f"{description} failed with exit code {completed.returncode}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_protocol_version(sidecar: Sidecar) -> int:
    """Load a sidecar's protocol version without importing USD.

    ``protocol.py`` is loaded directly by path so this script works on build
    hosts that have no USD available.
    """
    spec = importlib.util.spec_from_file_location(
        f"_{sidecar.name}_protocol", sidecar.protocol_path
    )
    if spec is None or spec.loader is None:
        raise BuildError(f"could not load {sidecar.protocol_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(module.PROTOCOL_VERSION)


def _sidecar_entries() -> list[dict[str, Any]]:
    return [
        {
            "name": sidecar.name,
            "module": sidecar.module,
            "distribution": sidecar.distribution,
            "protocol_version": _read_protocol_version(sidecar),
        }
        for sidecar in SIDECARS
    ]


def _declared_license(metadata: Any) -> str:
    """Return a short license identifier, never an inlined license body.

    Older wheels put the full license text in the ``License`` field. The
    manifest is a lookup table, so only the SPDX expression or the license
    classifiers belong in it; the full text ships as a license file.
    """
    expression = (metadata.get("License-Expression") or "").strip()
    if expression:
        return expression

    classifiers = [c for c in (metadata.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers)

    legacy = (metadata.get("License") or "").strip()
    if legacy and "\n" not in legacy and len(legacy) <= 120:
        return legacy
    return ""


def _wheel_metadata(wheel: Path) -> dict[str, Any]:
    """Return name, version, declared license, and license file names."""
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if not metadata_names:
            raise BuildError(f"{wheel.name} has no dist-info METADATA")
        dist_info = metadata_names[0].rsplit("/", 1)[0]
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        license_names = [
            name
            for name in archive.namelist()
            if name.startswith(f"{dist_info}/")
            and not name.endswith("/")
            and any(hint in name.rsplit("/", 1)[-1].lower() for hint in _LICENSE_FILE_HINTS)
        ]
        declared = _declared_license(metadata)
        return {
            "name": metadata.get("Name", wheel.name.split("-")[0]),
            "version": metadata.get("Version", ""),
            "license": declared.strip(),
            "license_members": license_names,
        }


def _extract_licenses(wheel: Path, members: list[str], destination: Path) -> list[str]:
    if not members:
        return []
    destination.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        for member in members:
            target = destination / member.rsplit("/", 1)[-1]
            target.write_bytes(archive.read(member))
            written.append(target.name)
    return sorted(written)


def _build_local_wheels(wheels_dir: Path) -> None:
    for project in _LOCAL_PROJECTS:
        if not (project / "pyproject.toml").is_file():
            raise BuildError(f"local project has no pyproject.toml: {project}")
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--isolated",
                "--wheel-dir",
                str(wheels_dir),
                str(project),
            ],
            description=f"building wheel for {project.name}",
        )


def _download_runtime_wheels(
    wheels_dir: Path,
    *,
    python_version: str,
    abi: str,
    implementation: str,
    platform: str,
) -> None:
    if not _RUNTIME_REQUIREMENTS.is_file():
        raise BuildError(f"missing runtime requirements file: {_RUNTIME_REQUIREMENTS}")
    local_wheels = [
        str(wheel) + (
            "[isaac]" if _wheel_metadata(wheel)["name"].replace("_", "-")
            == "simready-foundation-tier-core" else ""
        )
        for wheel in sorted(wheels_dir.glob("*.whl"))
    ]
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--python-version",
            python_version,
            "--abi",
            abi,
            "--implementation",
            implementation,
            "--platform",
            platform,
            "--dest",
            str(wheels_dir),
            "--find-links",
            str(wheels_dir),
            "--requirement",
            str(_RUNTIME_REQUIREMENTS),
            # Resolve the local wheels' full dependency closure, including
            # the opt-in public Isaac transformer shipped by the core tier.
            *local_wheels,
        ],
        description=f"downloading runtime wheels for {abi}-{platform}",
    )


def _local_distribution_names() -> set[str]:
    return {
        "simready-multiphysics-upgrade",
        "simready-foundation-tier-core",
        "simready-metadata-conform",
    }


def build_wheelhouse(
    output: Path,
    *,
    python_version: str = DEFAULT_PYTHON_VERSION,
    abi: str = DEFAULT_ABI,
    implementation: str = DEFAULT_IMPLEMENTATION,
    platform: str = DEFAULT_PLATFORM,
) -> Path:
    """Build the wheelhouse at ``output`` and return the manifest path."""
    if python_version != "3.12" or abi != "cp312":
        raise BuildError("The Isaac wheelhouse requires Python 3.12 / cp312.")
    output = output.expanduser().resolve()
    if output.exists():
        shutil.rmtree(output)
    wheels_dir = output / WHEELS_DIRNAME
    licenses_dir = output / LICENSES_DIRNAME
    wheels_dir.mkdir(parents=True)
    licenses_dir.mkdir(parents=True)

    _build_local_wheels(wheels_dir)
    _download_runtime_wheels(
        wheels_dir,
        python_version=python_version,
        abi=abi,
        implementation=implementation,
        platform=platform,
    )

    local_names = _local_distribution_names()
    distributions: list[dict[str, Any]] = []
    for wheel in sorted(wheels_dir.glob("*.whl")):
        metadata = _wheel_metadata(wheel)
        canonical = metadata["name"].lower().replace("_", "-")
        license_dir = licenses_dir / f"{canonical}-{metadata['version']}"
        license_files = _extract_licenses(wheel, metadata["license_members"], license_dir)
        if not license_files and canonical not in local_names:
            print(
                f"[wheelhouse] warning: {wheel.name} ships no license file; "
                f"declared license is {metadata['license'] or 'unknown'}",
                flush=True,
            )
        distributions.append(
            {
                "name": canonical,
                "version": metadata["version"],
                "filename": wheel.name,
                "sha256": _sha256(wheel),
                "size": wheel.stat().st_size,
                "license": metadata["license"],
                "license_files": [f"{LICENSES_DIRNAME}/{license_dir.name}/{n}" for n in license_files],
                "source": "local" if canonical in local_names else "index",
            }
        )

    missing = local_names - {dist["name"] for dist in distributions}
    if missing:
        raise BuildError(f"wheelhouse is missing required local distributions: {sorted(missing)}")

    sidecars = _sidecar_entries()
    primary = next(entry for entry in sidecars if entry["module"] == SIDECAR_MODULE)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # Retained so a host built against the single-sidecar manifest keeps
        # resolving multiphysics without reading `sidecars`.
        "protocol_version": primary["protocol_version"],
        "sidecar_module": SIDECAR_MODULE,
        "sidecars": sidecars,
        "python": {
            "version": python_version,
            "abi": abi,
            "implementation": implementation,
            "platform": platform,
        },
        "wheels_dir": WHEELS_DIRNAME,
        "licenses_dir": LICENSES_DIRNAME,
        "distributions": sorted(distributions, key=lambda item: item["name"]),
    }
    manifest_path = output / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"[wheelhouse] wrote {manifest_path} with {len(distributions)} distributions "
        f"and {len(sidecars)} sidecars",
        flush=True,
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_PACKAGE_ROOT / "_build" / "wheelhouse",
        help="Wheelhouse output directory (recreated on every build).",
    )
    parser.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION)
    parser.add_argument("--abi", default=DEFAULT_ABI)
    parser.add_argument("--implementation", default=DEFAULT_IMPLEMENTATION)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument(
        "--skip-smoke-test",
        action="store_true",
        help="Skip the clean-install transformation check after building.",
    )
    args = parser.parse_args(argv)

    try:
        manifest_path = build_wheelhouse(
            args.output,
            python_version=args.python_version,
            abi=args.abi,
            implementation=args.implementation,
            platform=args.platform,
        )
    except BuildError as exc:
        print(f"[wheelhouse] error: {exc}", file=sys.stderr)
        return 1

    if args.skip_smoke_test:
        return 0

    from wheelhouse_smoke_test import run_smoke_test

    return run_smoke_test(manifest_path.parent)


if __name__ == "__main__":
    sys.path.insert(0, str(_TOOLS_DIR))
    raise SystemExit(main())
