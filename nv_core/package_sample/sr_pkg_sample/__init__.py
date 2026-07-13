"""Python API for the SimReady packaging workflow.

The ``create_simready_package.py`` script at the ``package_sample``
root drives the workflow through the callables exposed here:

* :func:`pre_validate` — validate a candidate source folder against the
  ``Package-Candidate`` profile.  Returns a
  :class:`PreValidationResult`.
* :func:`create_package` — build a SimReady-conformant package from a
  validated source folder using WRAPP.  Returns a
  :class:`CreatedPackage` describing where the new package landed.
* :func:`create_package_definition` — write a minimal package
  definition (no BOM, no ``.metadata/``) directly into the source
  folder, without any WRAPP dependency.  Use as a lightweight
  alternative to :func:`create_package`.
* :func:`post_validate` — validate a finished package against the
  ``Package`` profile.  Returns a :class:`PostValidationResult`.

Validation functions return structured result objects
(:class:`PreValidationResult`, :class:`PostValidationResult`) that
expose the underlying :class:`simready.validate.AssetValidationResult`
objects and convenience properties (``.passed``, ``.failed_features``).
On failure they raise :class:`ValidationFailed` with the partial
result attached as ``ValidationFailed.result``.  Create functions
return :class:`CreatedPackage`.

* :class:`UsageError` — caller-supplied input is wrong.
* :class:`ValidationFailed` — validation completed but features
  failed; ``failures`` is the sorted list of failing feature IDs.
* :class:`BuildFailed` — the create step's underlying build failed
  (chained from the original exception via ``__cause__``).

The API never prints to stdout/stderr — all terminal output is the
responsibility of the CLI orchestrator (``create_simready_package.py``).

Before calling any of the validation functions, initialise
``simready.validate`` once per process — see the "Advanced: integrate
via Python API" section of ``README.md`` for a copy-paste example.

``FOUNDATIONS_DOCS_DIR`` is the on-disk root of the SimReady Foundation
spec docs that ``simready.validate.initialize()`` consumes
(``capabilities/`` + ``features/`` + ``profiles/profiles.toml``);
exposed here so you don't have to recompute the path yourself.

The :func:`create_package` symbol is loaded lazily on first access:
importing :mod:`sr_pkg_sample` does not import ``wrapp``, so the no-WRAPP
paths (:func:`create_package_definition`, :func:`pre_validate`,
:func:`post_validate`) work in environments where the WRAPP wheel
isn't installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

_PACKAGE_SAMPLE_DIR = Path(__file__).resolve().parent.parent
FOUNDATIONS_DOCS_DIR: Path = (
    _PACKAGE_SAMPLE_DIR.parent.parent / "nv_core" / "sr_specs" / "docs"
)

from ._package_def import CreatedPackage  # noqa: E402
from .create_package_definition import create_package_definition  # noqa: E402
from .errors import (  # noqa: E402
    BuildFailed,
    PackagingError,
    UsageError,
    ValidationFailed,
)
from .post_validation import post_validate  # noqa: E402
from .pre_validation import pre_validate  # noqa: E402
from .results import PostValidationResult, PreValidationResult  # noqa: E402

if TYPE_CHECKING:
    from .create_package_using_wrapp import create_package as create_package

from .workflow import (  # noqa: E402
    create_simready_package,
    create_simready_package_no_wrapp,
)


def __getattr__(name: str):
    """Lazy-load WRAPP-backed symbols only when first referenced."""
    if name == "create_package":
        from .create_package_using_wrapp import create_package

        return create_package
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BuildFailed",
    "CreatedPackage",
    "FOUNDATIONS_DOCS_DIR",
    "PackagingError",
    "PostValidationResult",
    "PreValidationResult",
    "UsageError",
    "ValidationFailed",
    "create_package",
    "create_package_definition",
    "create_simready_package",
    "create_simready_package_no_wrapp",
    "post_validate",
    "pre_validate",
]
