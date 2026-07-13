"""Top-level packaging workflow: pre-validate, create, post-validate.

Two entry points mirror the CLI's two modes:

* :func:`create_simready_package` — full WRAPP-backed flow.
* :func:`create_simready_package_no_wrapp` — lightweight, no-BOM flow.

Both orchestrate the three individual phases exposed by this package
(:func:`pre_validate`, :func:`create_package` /
:func:`create_package_definition`, :func:`post_validate`) and return a
:class:`CreatedPackage` on success or raise a :class:`PackagingError`
subclass on failure.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from ._package_def import CreatedPackage
from .create_package_definition import create_package_definition
from .post_validation import post_validate
from .pre_validation import pre_validate


def _local_path_from_url(url: str) -> Path:
    """Resolve a local-or-``file://`` URL to a :class:`Path`."""
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    return Path(url)


async def create_simready_package(
    name: str,
    version: str,
    license_id: str,
    source: str,
    repo: str,
    *,
    profiles: list[str] | None = None,
    root_usds: list[str] | None = None,
    skip_pre_validation: bool = False,
    skip_post_validation: bool = False,
) -> CreatedPackage:
    """Run the full WRAPP-backed packaging workflow.

    Pre-validates the *source* folder (writing ``.metadata/`` with
    BOM, conformance metadata and root-USD list), builds the package
    into *repo* via WRAPP, and post-validates the result (writing
    evidence metadata).

    Parameters
    ----------
    name, version, license_id:
        Package identity and SPDX licence.
    source:
        Local path (or ``file://`` URL) to the folder of USD files.
    repo:
        WRAPP repository to publish into.
    profiles:
        Pre-validation profiles.  Default: ``["Package-Candidate"]``.
    root_usds:
        Explicit root-USD relative paths (from ``--root-usd``).
        Falls back to an existing
        ``.metadata/com.nvidia.simready.root_usds.json``; raises
        :class:`UsageError` if neither source provides entries.
    skip_pre_validation:
        Skip the pre-validation phase.
    skip_post_validation:
        Skip the post-validation phase.

    Returns
    -------
    CreatedPackage
        Locations of the package definition and BOM.

    Raises
    ------
    UsageError, ValidationFailed, BuildFailed
    """
    source_path = Path(source)

    if not skip_pre_validation:
        await pre_validate(
            source_path,
            profiles=profiles,
            root_usds=root_usds,
            write_metadata=True,
        )

    from .create_package_using_wrapp import create_package

    created = await create_package(name, version, license_id, source, repo)

    if not skip_post_validation:
        pkg_def = _local_path_from_url(created.pkg_def_url)
        post_result = await post_validate(pkg_def, write_evidence=True)

        # ``post_validate`` writes its evidence files (e.g.
        # ``com.nvidia.simready.conformance.Package@1.0.0.json``) into
        # the published package's ``.metadata/`` directory in the repo,
        # but the WRAPP catalog was already finalised by ``create_package``
        # — so without this patch the evidence lives only in the repo
        # filesystem and gets dropped by ``wrapp.install`` /
        # ``wrapp.export``.  Inject the evidence into the catalog now so
        # consumers see a faithful mirror of the published package.
        if post_result.evidence_paths and created.marker_url is not None:
            await _patch_evidence_into_catalog(
                created.marker_url, created.pkg_def_url, post_result.evidence_paths,
            )

    return created


async def _patch_evidence_into_catalog(
    marker_url: str, pkg_def_url: str, evidence_paths: list[Path],
) -> None:
    """Append post-validation conformance files to the ``.wrapp`` catalog."""
    import wrapp

    from .wrapp_compat.catalog_patch import augment_wrapp_catalog
    from .wrapp_compat.create_and_emit import METADATA_FOLDER

    pkg_dir_url = pkg_def_url.rsplit("/", 1)[0]
    files: list[tuple[str, str, bytes]] = []
    for path in evidence_paths:
        rel = f"{METADATA_FOLDER}/{path.name}"
        source_url = f"{pkg_dir_url}/{rel}"
        files.append((rel, source_url, path.read_bytes()))

    async with wrapp.ContextManager():
        await augment_wrapp_catalog(
            marker_url,
            files=files,
            context=wrapp.CommandParameters(),
        )


async def create_simready_package_no_wrapp(
    name: str,
    version: str,
    license_id: str,
    source: str,
    *,
    profiles: list[str] | None = None,
    root_usds: list[str] | None = None,
    skip_pre_validation: bool = False,
    skip_post_validation: bool = False,
) -> CreatedPackage:
    """Run the lightweight, WRAPP-free packaging workflow.

    Pre-validates the *source* folder (stamping results directly into
    the USD file), writes a minimal package definition (no BOM, no
    ``.metadata/``), and post-validates against the ``Package-NoBOM``
    profile (core rules only).

    Parameters
    ----------
    name, version, license_id:
        Package identity and SPDX licence.
    source:
        Local path to the folder of USD files.  The source folder
        *is* the package — no separate repo is needed.
    profiles:
        Pre-validation profiles.  Default: ``["Package-Candidate"]``.
    root_usds:
        Explicit root-USD relative paths.
    skip_pre_validation:
        Skip the pre-validation phase.
    skip_post_validation:
        Skip the post-validation phase.

    Returns
    -------
    CreatedPackage
        Location of the package definition (``bom_url`` is ``None``).

    Raises
    ------
    UsageError, ValidationFailed, BuildFailed
    """
    source_path = Path(source)

    if not skip_pre_validation:
        await pre_validate(
            source_path,
            profiles=profiles,
            root_usds=root_usds,
            stamp_usd=True,
        )

    created = await create_package_definition(name, version, license_id, source)

    if not skip_post_validation:
        pkg_def = _local_path_from_url(created.pkg_def_url)
        await post_validate(pkg_def, profiles=["Package-NoBOM"])

    return created
