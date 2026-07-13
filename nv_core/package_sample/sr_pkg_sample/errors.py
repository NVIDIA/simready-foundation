"""Exceptions raised by the SimReady packaging-step API.

The three step callables (:func:`sr_pkg_sample.pre_validate`,
:func:`sr_pkg_sample.create_package`, :func:`sr_pkg_sample.post_validate`) raise on
failure and return ``None`` (or a result object) on success.  Every
exception they raise inherits from :class:`PackagingError`, so a
caller that just wants "succeeded or didn't" can write::

    try:
        pre_validate(source)
        create_package(name, version, license_id, source, repo)
        post_validate(pkg_def)
    except PackagingError as exc:
        ...

The three concrete subclasses below let a caller distinguish *why*
the call failed:

* :class:`UsageError` — caller's input is wrong.  The message is
  user-fixable (missing path, mismatched marker, source already looks
  like a built package, ...).  Maps to exit code ``2`` in the
  ``create_simready_package.py`` script.
* :class:`ValidationFailed` — validation completed but at least one
  feature failed.  ``failures`` is the sorted list of failing
  ``FET***`` IDs so a programmatic caller can introspect without
  re-parsing the per-feature stdout summary.  Maps to exit code ``1``.
* :class:`BuildFailed` — an unexpected runtime error inside the
  create step (WRAPP failed, I/O error, ...).  Always chained from
  the underlying exception via ``raise BuildFailed(...) from exc`` so
  the original traceback is reachable through ``__cause__``.  Maps
  to exit code ``1``.
"""

from __future__ import annotations

__all__ = [
    "BuildFailed",
    "PackagingError",
    "UsageError",
    "ValidationFailed",
]


class PackagingError(Exception):
    """Base class for everything the packaging API raises on failure."""


class UsageError(PackagingError):
    """Caller-supplied input is invalid (path missing, mismatched marker, ...)."""


class ValidationFailed(PackagingError):
    """At least one feature of the active profile failed.

    Parameters
    ----------
    message:
        Human-readable summary.
    failures:
        Sorted list of failing feature IDs (e.g.
        ``["FET030_PACKAGING_CORE", "FET032_PACKAGING_INTROSPECTION"]``)
        so callers can introspect the outcome without scraping stdout.
    result:
        The full :class:`~sr_pkg_sample.results.PreValidationResult` or
        :class:`~sr_pkg_sample.results.PostValidationResult` that was
        being built when the failure was detected.  Available so the
        CLI layer (or any other caller) can print a detailed summary
        even on failure.  ``None`` when no structured result is
        available.
    """

    def __init__(
        self,
        message: str,
        failures: list[str],
        result: object | None = None,
    ) -> None:
        super().__init__(message)
        self.failures: list[str] = list(failures)
        self.result: object | None = result


class BuildFailed(PackagingError):
    """The create step failed during the underlying build.

    Always chained from the original exception via ``raise ... from
    exc`` so the underlying WRAPP / I/O traceback is accessible
    through :attr:`__cause__`.
    """
