# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Distribution shape: metadata, entry points, and import boundaries."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
MODULE_ROOT = SRC / "simready" / "metadata_conform"


def _pyproject() -> dict:
    return tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_distribution_metadata():
    project = _pyproject()["project"]

    assert project["name"] == "simready-metadata-conform"
    assert project["license"] == "Apache-2.0"
    # Must cover the bundled CPython 3.11 sidecar interpreter.
    assert project["requires-python"] == ">=3.10,<3.14"


def test_console_scripts_point_at_real_callables():
    scripts = _pyproject()["project"]["scripts"]

    assert scripts["simready-metadata-sidecar"] == (
        "simready.metadata_conform.sidecar:main"
    )
    assert scripts["simready-metadata-conform"] == (
        "simready.metadata_conform.runner:main"
    )
    from simready.metadata_conform import runner, sidecar

    assert callable(sidecar.main)
    assert callable(runner.main)


def test_namespace_package_is_declared():
    setuptools = _pyproject()["tool"]["setuptools"]

    assert setuptools["packages"]["find"]["namespaces"] is True
    assert setuptools["packages"]["find"]["where"] == ["src"]
    # PEP 420: no __init__.py at the namespace root, or it would shadow the
    # sibling simready.* distributions in the same interpreter.
    assert not (SRC / "simready" / "__init__.py").exists()


def test_no_hard_third_party_dependencies():
    project = _pyproject()["project"]

    assert project["dependencies"] == []
    assert "usd-core>=23.5" in project["optional-dependencies"]["usd"]
    validate_extra = project["optional-dependencies"]["validate"]
    assert "simready-validate" in validate_extra
    assert "simready-foundation-tier-core" in validate_extra


def test_protocol_module_is_importable_without_usd():
    """Wheelhouse tooling loads protocol.py by path on hosts without USD."""
    spec = importlib.util.spec_from_file_location(
        "_isolated_protocol", MODULE_ROOT / "protocol.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.PROTOCOL_VERSION, int)
    assert module.PROTOCOL_VERSION >= 1


def test_version_module_is_importable_without_usd():
    spec = importlib.util.spec_from_file_location(
        "_isolated_version", MODULE_ROOT / "version.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.__version__ == _pyproject()["project"]["version"]


def test_validation_module_is_not_imported_by_the_runtime_path():
    """The sidecar must work without simready-validate installed."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(SRC)!r}); "
            "import simready.metadata_conform.sidecar as s; "
            "assert 'simready.metadata_conform.validation' not in sys.modules; "
            "print('ok')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


def test_public_exports():
    import simready.metadata_conform as package

    for name in (
        "PROTOCOL_VERSION",
        "REQUIRED_FIELDS",
        "MetadataConformRequest",
        "MetadataConformResult",
        "ResultError",
        "conform_package",
        "run_metadata_conform",
        "__version__",
    ):
        assert name in package.__all__
        assert hasattr(package, name)


def test_required_fields_match_the_sr_003_contract():
    from simready.metadata_conform import REQUIRED_FIELDS

    assert set(REQUIRED_FIELDS) == {
        "author",
        "asset_name",
        "asset_type",
        "asset_license",
        "category",
        "source_file",
        "usd_date_generated",
        "qcode",
        "rigid_body_count",
        "asset_extents",
        "mass",
    }


def test_bundled_derivation_snapshot_is_ascii_only():
    """The snapshot runs in cp1252 consoles, so it must stay ASCII."""
    source = (MODULE_ROOT / "resources" / "extract_simready_metadata.py").read_bytes()

    assert all(byte < 128 for byte in source)
