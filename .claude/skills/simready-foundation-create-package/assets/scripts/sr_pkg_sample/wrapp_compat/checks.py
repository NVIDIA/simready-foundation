"""Pre- and post-flight source-folder checks for the WRAPP create step.

These guard against two WRAPP 2.2 behaviours that produce confusing
results if the user is unaware of them:

* A root-level ``.<name>.wrapp`` marker whose ``<name>`` differs from
  the requested package name would be silently folded in as a
  sub-dependency by ``wrapp.create``.
* Nested ``.wrapp`` markers in subfolders get recorded as
  sub-dependencies — the SimReady standard does not yet define nested
  packages, so reject them early.

WRAPP 2.3 is expected to handle both cases natively.
"""

from __future__ import annotations

from wrapp.datastructures.package import read_package_info
from wrapp.utils.storage import wrapp_list_directory
from wrapp.utils.utils import get_filename_from_url


def _wrapp_marker_package_name(filename: str) -> str:
    """Return the package name encoded in a ``*.wrapp`` marker filename.

    ``wrapp`` writes the canonical marker as ``.<name>.wrapp`` (hidden);
    older / hand-authored markers may appear as plain ``<name>.wrapp``.
    Handle both spellings.
    """
    stem = filename[1:] if filename.startswith(".") else filename
    assert stem.endswith(".wrapp"), filename
    return stem[: -len(".wrapp")]


async def check_existing_package(source: str, package_name: str) -> str | None:
    """Return an error if ``source`` has ``.wrapp`` markers that don't match *package_name*.

    Lists immediate children of ``source`` via WRAPP's storage router so
    the check works for any backend WRAPP can read (local, ``file://``,
    ``s3://``, ``omniverse://``, ...).  A ``.<existing>.wrapp`` marker
    at the root means the folder is already a package called
    ``<existing>``; if that name differs from the build target,
    ``wrapp.create`` would silently absorb it as a sub-dependency, so
    refuse and tell the user how to fix it.  A matching marker is
    allowed — ``wrapp.create`` handles the re-create case itself, which
    lets users re-run after a failed build without hand-cleaning the
    source.
    """
    mismatched: list[str] = []
    async for entry in wrapp_list_directory(source):
        if not entry.is_regular_file:
            continue
        filename = get_filename_from_url(entry.relative_path)
        if not filename.endswith(".wrapp"):
            continue
        existing_name = _wrapp_marker_package_name(filename)
        if existing_name != package_name:
            mismatched.append(filename)

    if not mismatched:
        return None
    files = ", ".join(sorted(mismatched))
    if len(mismatched) == 1:
        name = _wrapp_marker_package_name(mismatched[0])
        return (
            f"source folder already contains {mismatched[0]!r} (package "
            f"{name!r}); either remove it or use {name!r} as the "
            f"package name."
        )
    return (
        f"source folder already contains .wrapp markers for other "
        f"packages: {files}.  Remove them before creating a new package."
    )


async def check_no_nested_subpackages(wrapp_marker_url: str) -> str | None:
    """Return an error if ``wrapp.create`` absorbed any nested subpackages.

    ``wrapp.create`` walks the source tree for ``.wrapp`` files and
    records each one as a sub-dependency in the new package.  Reading
    the freshly written marker back is the easiest way to spot any
    nested marker no matter where in the source it was hiding — the
    pre-flight check (``check_existing_package``) only inspects the
    root.  The SimReady packaging standard does not yet describe
    nested packages, so reject them here.
    """
    package_info = await read_package_info(wrapp_marker_url)
    if package_info is None or not package_info.dependencies:
        return None
    deps = ", ".join(repr(d.package) for d in package_info.dependencies)
    return (
        f"source folder contains installed WRAPP subpackages "
        f"({deps}); nested packages are not yet supported by the "
        f"SimReady packaging standard.  Remove the nested .wrapp files "
        f"from the source before publishing."
    )
