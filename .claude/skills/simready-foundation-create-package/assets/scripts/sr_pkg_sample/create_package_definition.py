"""Stamp a minimal SimReady package definition into a source folder (no WRAPP).

A lightweight alternative to :func:`sr_pkg_sample.create_package` for the case
where you don't need a full BOM-bearing package — for example, quick
prototyping, or environments where the WRAPP wheel can't be installed.
This step writes a single ``com.nvidia.simready.packaging.json`` file
into the source folder containing only the three fields the SimReady
packaging standard marks as required (``format_version``,
``package_id``, ``license`` — see ``PKG.DEF.001`` in
``capabilities/packaging/packaging_core/requirements/package-definition.md``).

The result is a SimReady-conformant package skeleton with no BOM, no
``.metadata/`` folder, and no file hashes.  The package will satisfy
the package-definition required-fields rule and nothing more — most
notably, post-validation features that rely on a BOM (e.g.
``FET032_PACKAGING_INTROSPECTION``) will FAIL against it.  That's
expected.
"""

from __future__ import annotations

import json
from pathlib import Path

from ._package_def import (
    PACKAGE_ID_PREFIX,
    PACKAGING_DEFINITION_FILENAME,
    STANDARD_FORMAT_VERSION,
    CreatedPackage,
)
from .errors import UsageError


async def create_package_definition(
    name: str,
    version: str,
    license_id: str,
    source: str,
) -> CreatedPackage:
    """Write a minimal package definition into ``source``.

    Stamps ``com.nvidia.simready.packaging.json`` at the root of
    ``source``, turning the folder into a SimReady-conformant package
    skeleton.  No BOM, no ``.metadata/`` directory, no file hashes,
    and — unlike :func:`sr_pkg_sample.create_package` — no WRAPP dependency.

    Parameters
    ----------
    name, version:
        Package coordinates; combined into the SimReady ``package_id``
        as ``<PACKAGE_ID_PREFIX>.<name>.<version>``.
    license_id:
        SPDX licence identifier copied verbatim into the definition
        (e.g. ``MIT``, ``Apache-2.0``).
    source:
        Local-path folder of USD files; must already exist.  This
        function only supports local paths — remote URLs are out of
        scope for the no-WRAPP fallback.

    Returns
    -------
    CreatedPackage
        ``pkg_def_url`` points at the freshly-written
        ``com.nvidia.simready.packaging.json``.  ``bom_url`` is
        ``None`` because no BOM is produced.

    Raises
    ------
    UsageError
        ``source`` is not a directory, or already carries a
        ``com.nvidia.simready.packaging.json`` at its root (refuse to
        silently overwrite — remove the existing file first if you
        want to re-stamp).
    """
    src = Path(source)
    if not src.is_dir():
        raise UsageError(f"source is not a directory: {src}")

    pkg_def_path = src / PACKAGING_DEFINITION_FILENAME
    if pkg_def_path.exists():
        raise UsageError(
            f"package definition already exists at {pkg_def_path}; "
            f"refusing to overwrite.  Remove the file if you want to "
            f"re-stamp the source folder."
        )

    definition = {
        "format_version": STANDARD_FORMAT_VERSION,
        "package_id": f"{PACKAGE_ID_PREFIX}.{name}.{version}",
        "license": license_id,
    }
    pkg_def_path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")

    return CreatedPackage(pkg_def_url=str(pkg_def_path))
