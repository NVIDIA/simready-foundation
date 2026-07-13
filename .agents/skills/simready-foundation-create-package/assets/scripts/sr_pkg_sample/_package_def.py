"""Lightweight types and constants shared by the package-creation paths.

Lives in its own WRAPP-free module so the no-WRAPP fallback
(:mod:`sr_pkg_sample.create_package_definition`) keeps importing cleanly when
the ``wrapp`` wheel isn't installed.  The WRAPP-driven path
(:mod:`sr_pkg_sample.create_package_using_wrapp`) imports from here too, so
the two creation backends share a single :class:`CreatedPackage`
return type.
"""

from __future__ import annotations

from dataclasses import dataclass

PACKAGE_ID_PREFIX = "com.nvidia.simready"
PACKAGING_DEFINITION_FILENAME = "com.nvidia.simready.packaging.json"
STANDARD_FORMAT_VERSION = "1.0"


@dataclass(frozen=True)
class CreatedPackage:
    """Result of a successful ``create_package*`` call.

    Attributes
    ----------
    pkg_def_url:
        URL or path of the freshly written
        ``com.nvidia.simready.packaging.json``.  Pass this to
        :func:`sr_pkg_sample.post_validate` to validate the new package.
    bom_url:
        URL or path of the BOM sidecar
        (``.metadata/com.nvidia.simready.packaging.bom.json``).
        ``None`` when the create step does not produce a BOM, e.g.
        the WRAPP-less :func:`sr_pkg_sample.create_package_definition` path.
    marker_url:
        URL of the ``.<name>.wrapp`` marker file that owns the package
        catalog.  Provided by the WRAPP-backed creation path so callers
        can patch additional metadata into the catalog after creation
        (e.g. post-validation conformance evidence written by
        :func:`sr_pkg_sample.post_validate`, which lands in the repo
        filesystem after the catalog is closed).  ``None`` for the
        WRAPP-less path, which has no catalog.
    """

    pkg_def_url: str
    bom_url: str | None = None
    marker_url: str | None = None
