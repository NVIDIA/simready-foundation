"""Tests for the WRAPP-less ``create_package_definition`` step.

Drives :func:`sr_pkg_sample.create_package_definition` directly against a
writable apple_a01 sample copy.  Asserts that the function:

* writes a parseable ``com.nvidia.simready.packaging.json`` at the
  source root carrying exactly the three required fields
  (``format_version``, ``package_id``, ``license``) and nothing else;
* returns a :class:`CreatedPackage` with ``bom_url=None`` (no BOM is
  produced in this mode);
* refuses to overwrite a pre-existing definition file (raises
  :class:`UsageError`);
* raises :class:`UsageError` when ``source`` is not a directory.

Unlike :mod:`tests.test_create_package_using_wrapp`, this module has
no WRAPP dependency — it intentionally must keep importing cleanly in
environments without the WRAPP wheel installed, since that is the
whole point of the no-WRAPP fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_pkg_sample import CreatedPackage, UsageError, create_package_definition


async def test_create_package_definition_happy_path(
    sample_source_copy: Path,
) -> None:
    """End-to-end: stamp a minimal package definition into the source folder."""
    name = "apple_a01"
    version = "1.0.0"
    license_id = "MIT"

    created = await create_package_definition(
        name, version, license_id, str(sample_source_copy)
    )

    assert isinstance(created, CreatedPackage)
    assert created.pkg_def_url.endswith("com.nvidia.simready.packaging.json")
    assert created.bom_url is None

    pkg_def = sample_source_copy / "com.nvidia.simready.packaging.json"
    assert pkg_def.is_file(), f"missing package def: {pkg_def}"

    definition = json.loads(pkg_def.read_text())

    assert set(definition.keys()) == {"format_version", "package_id", "license"}, definition
    assert definition["license"] == license_id, definition
    assert definition["format_version"] == "1.0", definition
    package_id = definition["package_id"]
    assert package_id == f"com.nvidia.simready.{name}.{version}", package_id

    assert not (sample_source_copy / ".metadata").exists(), (
        "create_package_definition must not produce a .metadata/ folder"
    )


async def test_create_package_definition_rejects_existing_file(
    sample_source_copy: Path,
) -> None:
    """A pre-existing definition triggers UsageError instead of being overwritten.

    Belt-and-suspenders for the user: if they re-run ``--no-wrapp``
    without first cleaning up, we tell them what to do rather than
    silently rewriting the file.
    """
    pkg_def = sample_source_copy / "com.nvidia.simready.packaging.json"
    pkg_def.write_text("{}\n")

    with pytest.raises(UsageError) as exc_info:
        await create_package_definition(
            "apple_a01", "1.0.0", "MIT", str(sample_source_copy)
        )

    msg = str(exc_info.value)
    assert "already exists" in msg, msg
    assert "com.nvidia.simready.packaging.json" in msg, msg


async def test_create_package_definition_rejects_non_directory(tmp_path: Path) -> None:
    """A missing or non-directory ``source`` argument raises UsageError."""
    bogus = tmp_path / "does_not_exist"

    with pytest.raises(UsageError) as exc_info:
        await create_package_definition("apple_a01", "1.0.0", "MIT", str(bogus))

    assert "not a directory" in str(exc_info.value)
