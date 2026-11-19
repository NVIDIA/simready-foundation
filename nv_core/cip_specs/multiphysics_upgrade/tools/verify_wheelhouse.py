# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check that a wheelhouse directory is complete and internally consistent.

Runs on any platform, including CI hosts that cannot install Windows wheels, so
a broken bundle fails the build before it reaches a release artifact.

Usage::

    python tools/verify_wheelhouse.py _build/wheelhouse
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

MANIFEST_NAME = "wheelhouse.json"
SUPPORTED_SCHEMA_VERSION = 1
REQUIRED_DISTRIBUTIONS = (
    "simready-multiphysics-upgrade",
    "simready-foundation-tier-core",
    "simready-metadata-conform",
    "usd-core",
    "numpy",
)
REQUIRED_SIDECARS = ("multiphysics", "metadata")
_REQUIRED_MANIFEST_KEYS = (
    "schema_version",
    "protocol_version",
    "sidecar_module",
    "sidecars",
    "python",
    "distributions",
)
_REQUIRED_SIDECAR_KEYS = ("name", "module", "distribution", "protocol_version")


def _verify_sidecars(manifest: dict[str, Any], present: set[str]) -> list[str]:
    """Check every sidecar entry names a real module and a bundled distribution."""
    problems: list[str] = []
    sidecars = manifest.get("sidecars")
    if not isinstance(sidecars, list) or not sidecars:
        return ["manifest sidecars must be a non-empty list"]

    for index, sidecar in enumerate(sidecars):
        label = f"sidecars[{index}]"
        if not isinstance(sidecar, dict):
            problems.append(f"{label} must be an object")
            continue
        label = f"sidecars[{sidecar.get('name', index)}]"
        for key in _REQUIRED_SIDECAR_KEYS:
            if key not in sidecar:
                problems.append(f"{label} is missing key: {key}")
        if not str(sidecar.get("module", "")).strip():
            problems.append(f"{label}: module must be a non-empty string")
        if not isinstance(sidecar.get("protocol_version"), int):
            problems.append(f"{label}: protocol_version must be an integer")
        distribution = sidecar.get("distribution")
        if distribution and distribution not in present:
            problems.append(
                f"{label}: distribution {distribution} is not in the bundle"
            )

    names = {
        sidecar.get("name") for sidecar in sidecars if isinstance(sidecar, dict)
    }
    for required in REQUIRED_SIDECARS:
        if required not in names:
            problems.append(f"manifest is missing required sidecar: {required}")

    # The legacy single-sidecar keys must stay consistent with the array, or a
    # host that reads only one of the two gets a different answer.
    legacy_module = manifest.get("sidecar_module")
    legacy = [
        sidecar
        for sidecar in sidecars
        if isinstance(sidecar, dict) and sidecar.get("module") == legacy_module
    ]
    if not legacy:
        problems.append(
            f"manifest sidecar_module {legacy_module!r} has no matching sidecars entry"
        )
    elif legacy[0].get("protocol_version") != manifest.get("protocol_version"):
        problems.append(
            "manifest protocol_version disagrees with the matching sidecars entry"
        )
    return problems


def verify_wheelhouse(wheelhouse: Path) -> list[str]:
    """Return a list of problems; an empty list means the bundle is usable."""
    problems: list[str] = []
    manifest_path = wheelhouse / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]

    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest is not valid JSON: {exc}"]

    missing_keys = [key for key in _REQUIRED_MANIFEST_KEYS if key not in manifest]
    if missing_keys:
        problems.append(f"manifest is missing keys: {sorted(missing_keys)}")
        return problems

    if manifest["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        problems.append(
            f"manifest schema_version {manifest['schema_version']} "
            f"is not supported (expected {SUPPORTED_SCHEMA_VERSION})"
        )
    if not isinstance(manifest["protocol_version"], int):
        problems.append("manifest protocol_version must be an integer")
    if not str(manifest["sidecar_module"]).strip():
        problems.append("manifest sidecar_module must be a non-empty string")

    python = manifest.get("python") or {}
    for key in ("version", "abi", "implementation", "platform"):
        if not str(python.get(key, "")).strip():
            problems.append(f"manifest python.{key} must be a non-empty string")

    wheels_dir = wheelhouse / manifest.get("wheels_dir", "wheels")
    present = {dist["name"] for dist in manifest["distributions"]}
    for required in REQUIRED_DISTRIBUTIONS:
        if required not in present:
            problems.append(f"manifest is missing required distribution: {required}")

    problems.extend(_verify_sidecars(manifest, present))

    for distribution in manifest["distributions"]:
        name = distribution.get("name", "<unnamed>")
        wheel = wheels_dir / distribution.get("filename", "")
        if not wheel.is_file():
            problems.append(f"{name}: wheel file is missing: {wheel}")
            continue
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if digest != distribution.get("sha256"):
            problems.append(f"{name}: sha256 mismatch for {wheel.name}")
        if wheel.stat().st_size != distribution.get("size"):
            problems.append(f"{name}: size mismatch for {wheel.name}")

        license_files = distribution.get("license_files") or []
        for relative in license_files:
            if not (wheelhouse / relative).is_file():
                problems.append(f"{name}: declared license file is missing: {relative}")
        if not license_files and not str(distribution.get("license", "")).strip():
            problems.append(f"{name}: no license file and no declared license")
        if distribution.get("source") == "index" and not license_files:
            problems.append(f"{name}: third-party wheel ships no license file")

    orphans = sorted(
        wheel.name
        for wheel in wheels_dir.glob("*.whl")
        if wheel.name not in {dist.get("filename") for dist in manifest["distributions"]}
    )
    if orphans:
        problems.append(f"wheels present but not listed in the manifest: {orphans}")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheelhouse", type=Path, help="Directory holding wheelhouse.json")
    args = parser.parse_args(argv)

    problems = verify_wheelhouse(args.wheelhouse.expanduser().resolve())
    if problems:
        print("[verify-wheelhouse] FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("[verify-wheelhouse] bundle is complete and consistent", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
