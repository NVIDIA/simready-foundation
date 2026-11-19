# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the wheelhouse manifest verifier and the multi-sidecar manifest.

The verifier is the packaging gate: a bundle with a missing wheel, a bad hash,
an undocumented license, or a sidecar whose distribution is not bundled must
fail before it reaches a release artifact.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from verify_wheelhouse import MANIFEST_NAME, verify_wheelhouse  # noqa: E402
from wheelhouse_smoke_test import (  # noqa: E402
    SmokeTestError,
    resolve_sidecar,
    write_thumbnail,
)


def _write_bundle(root: Path) -> dict:
    wheels = root / "wheels"
    wheels.mkdir(parents=True)
    licenses = root / "licenses"

    distributions = []
    for name, source in (
        ("simready_multiphysics_upgrade", "local"),
        ("simready_foundation_tier_core", "local"),
        ("simready_metadata_conform", "local"),
        ("usd_core", "index"),
        ("numpy", "index"),
    ):
        canonical = name.replace("_", "-")
        wheel = wheels / f"{name}-1.0.0-py3-none-any.whl"
        wheel.write_bytes(f"wheel bytes for {name}".encode())
        license_files: list[str] = []
        if source == "index":
            license_dir = licenses / f"{canonical}-1.0.0"
            license_dir.mkdir(parents=True)
            (license_dir / "LICENSE.txt").write_text("license text", encoding="utf-8")
            license_files = [f"licenses/{canonical}-1.0.0/LICENSE.txt"]
        distributions.append(
            {
                "name": canonical,
                "version": "1.0.0",
                "filename": wheel.name,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "size": wheel.stat().st_size,
                "license": "Apache-2.0" if source == "local" else "BSD-3-Clause",
                "license_files": license_files,
                "source": source,
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_utc": "2026-01-01T00:00:00Z",
        "protocol_version": 1,
        "sidecar_module": "simready.multiphysics_upgrade.sidecar",
        "sidecars": [
            {
                "name": "multiphysics",
                "module": "simready.multiphysics_upgrade.sidecar",
                "distribution": "simready-multiphysics-upgrade",
                "protocol_version": 1,
            },
            {
                "name": "metadata",
                "module": "simready.metadata_conform.sidecar",
                "distribution": "simready-metadata-conform",
                "protocol_version": 1,
            },
        ],
        "python": {
            "version": "3.11",
            "abi": "cp311",
            "implementation": "cp",
            "platform": "win_amd64",
        },
        "wheels_dir": "wheels",
        "licenses_dir": "licenses",
        "distributions": distributions,
    }
    (root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _rewrite(root: Path, manifest: dict) -> None:
    (root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_accepts_a_complete_bundle(tmp_path):
    _write_bundle(tmp_path)

    assert verify_wheelhouse(tmp_path) == []


def test_rejects_a_missing_manifest(tmp_path):
    problems = verify_wheelhouse(tmp_path)

    assert len(problems) == 1
    assert "missing manifest" in problems[0]


def test_rejects_a_missing_wheel(tmp_path):
    manifest = _write_bundle(tmp_path)
    (tmp_path / "wheels" / manifest["distributions"][0]["filename"]).unlink()

    problems = verify_wheelhouse(tmp_path)

    assert any("wheel file is missing" in problem for problem in problems)


def test_rejects_a_hash_mismatch(tmp_path):
    manifest = _write_bundle(tmp_path)
    wheel = tmp_path / "wheels" / manifest["distributions"][0]["filename"]
    wheel.write_bytes(b"tampered")
    manifest["distributions"][0]["size"] = wheel.stat().st_size
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("sha256 mismatch" in problem for problem in problems)


def test_rejects_a_missing_required_distribution(tmp_path):
    manifest = _write_bundle(tmp_path)
    dropped = manifest["distributions"].pop(0)
    (tmp_path / "wheels" / dropped["filename"]).unlink()
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("missing required distribution" in problem for problem in problems)


def test_rejects_third_party_wheel_without_license_file(tmp_path):
    manifest = _write_bundle(tmp_path)
    third_party = next(d for d in manifest["distributions"] if d["source"] == "index")
    third_party["license_files"] = []
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("ships no license file" in problem for problem in problems)


def test_rejects_a_declared_license_file_that_is_absent(tmp_path):
    manifest = _write_bundle(tmp_path)
    third_party = next(d for d in manifest["distributions"] if d["source"] == "index")
    (tmp_path / third_party["license_files"][0]).unlink()
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("declared license file is missing" in problem for problem in problems)


def test_rejects_missing_protocol_metadata(tmp_path):
    manifest = _write_bundle(tmp_path)
    del manifest["protocol_version"]
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("missing keys" in problem for problem in problems)


def test_rejects_unlisted_wheels(tmp_path):
    _write_bundle(tmp_path)
    (tmp_path / "wheels" / "stowaway-9.9.9-py3-none-any.whl").write_bytes(b"stowaway")

    problems = verify_wheelhouse(tmp_path)

    assert any("not listed in the manifest" in problem for problem in problems)


def test_rejects_a_missing_sidecars_array(tmp_path):
    manifest = _write_bundle(tmp_path)
    del manifest["sidecars"]
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("missing keys" in problem for problem in problems)


def test_rejects_a_missing_required_sidecar(tmp_path):
    manifest = _write_bundle(tmp_path)
    manifest["sidecars"] = [
        entry for entry in manifest["sidecars"] if entry["name"] != "metadata"
    ]
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("missing required sidecar: metadata" in problem for problem in problems)


def test_rejects_a_sidecar_whose_distribution_is_not_bundled(tmp_path):
    manifest = _write_bundle(tmp_path)
    entry = next(e for e in manifest["sidecars"] if e["name"] == "metadata")
    entry["distribution"] = "simready-not-shipped"
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("is not in the bundle" in problem for problem in problems)


def test_rejects_a_sidecar_with_a_non_integer_protocol_version(tmp_path):
    manifest = _write_bundle(tmp_path)
    manifest["sidecars"][0]["protocol_version"] = "1"
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("protocol_version must be an integer" in problem for problem in problems)


def test_rejects_a_sidecar_entry_missing_a_key(tmp_path):
    manifest = _write_bundle(tmp_path)
    del manifest["sidecars"][1]["module"]
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("is missing key: module" in problem for problem in problems)


def test_rejects_legacy_keys_that_disagree_with_the_sidecars_array(tmp_path):
    """A host reading only `protocol_version` must not get a stale answer."""
    manifest = _write_bundle(tmp_path)
    manifest["protocol_version"] = 2
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("disagrees with the matching sidecars entry" in p for p in problems)


def test_rejects_a_sidecar_module_with_no_matching_entry(tmp_path):
    manifest = _write_bundle(tmp_path)
    manifest["sidecar_module"] = "simready.gone.sidecar"
    _rewrite(tmp_path, manifest)

    problems = verify_wheelhouse(tmp_path)

    assert any("has no matching sidecars entry" in problem for problem in problems)


def test_resolve_sidecar_finds_each_entry(tmp_path):
    manifest = _write_bundle(tmp_path)

    assert resolve_sidecar(manifest, "metadata")["module"] == (
        "simready.metadata_conform.sidecar"
    )
    assert resolve_sidecar(manifest, "multiphysics")["protocol_version"] == 1


def test_resolve_sidecar_falls_back_to_the_legacy_keys(tmp_path):
    manifest = _write_bundle(tmp_path)
    del manifest["sidecars"]

    resolved = resolve_sidecar(manifest, "multiphysics")

    assert resolved["module"] == "simready.multiphysics_upgrade.sidecar"
    assert resolved["protocol_version"] == 1


def test_resolve_sidecar_rejects_an_unknown_name(tmp_path):
    manifest = _write_bundle(tmp_path)

    try:
        resolve_sidecar(manifest, "nonexistent")
    except SmokeTestError as exc:
        assert "nonexistent" in str(exc)
    else:
        raise AssertionError("expected SmokeTestError")


def test_smoke_test_thumbnail_is_a_valid_png(tmp_path):
    """The smoke-test fixture PNG must pass the conform step's own validator."""
    src = Path(__file__).resolve().parents[2] / "metadata_conform" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from simready.metadata_conform.core.thumbnails import is_valid_png

    assert is_valid_png(write_thumbnail(tmp_path / "thumb.png"))


def test_builder_uses_buildable_local_projects(monkeypatch, tmp_path):
    import build_wheelhouse as builder

    commands = []
    monkeypatch.setattr(builder, "_run", lambda cmd, **kw: commands.append(cmd))
    builder._build_local_wheels(tmp_path)
    assert len(commands) == 3
    assert builder._TIER_ROOT in builder._LOCAL_PROJECTS
    assert all((Path(cmd[-1]) / "pyproject.toml").is_file() for cmd in commands)
    assert all("--no-build-isolation" not in cmd for cmd in commands)
    assert "simready-foundation-tier-core" in builder._local_distribution_names()


def test_builder_resolves_local_wheel_dependency_closure(monkeypatch, tmp_path):
    import build_wheelhouse as builder

    wheel = tmp_path / "simready_foundation_tier_core-0.0.1a10-py3-none-any.whl"
    wheel.touch()
    monkeypatch.setattr(builder, "_wheel_metadata", lambda path: {
        "name": "simready-foundation-tier-core",
    })
    commands = []
    monkeypatch.setattr(builder, "_run", lambda cmd, **kw: commands.append(cmd))
    builder._download_runtime_wheels(
        tmp_path, python_version="3.12", abi="cp312",
        implementation="cp", platform="win_amd64",
    )
    assert str(wheel) + "[isaac]" in commands[0]
    assert "--no-deps" not in commands[0]
