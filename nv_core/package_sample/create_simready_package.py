#!/usr/bin/env python3
"""Build, validate, and check a SimReady asset package in one command.

Run the full SimReady packaging workflow against a folder of USD files.
By default the script runs three phases in order:

    1. Pre-validation  — does ``<source>`` look like something we can
                         package?  (``Package-Candidate`` profile)
    2. Create          — build the package into ``<repo>`` (uses WRAPP).
    3. Post-validation — does the freshly built package conform?
                         (``Package`` profile)

Usage
-----
::

    create_simready_package.py <name> <version> <license> <source> <repo>
                              --root-usd PATH [--root-usd PATH ...]
                              [--skip-pre-validation]
                              [--skip-post-validation]
                              [--profile PROFILE ...]

    create_simready_package.py <name> <version> <license> <source>
                              --no-wrapp
                              [--skip-pre-validation]
                              [--skip-post-validation]

    create_simready_package.py --only-pre-validation  --source <path>
                              --root-usd PATH [--root-usd PATH ...]
                              [--write-metadata]
                              [--profile PROFILE ...]
    create_simready_package.py --only-post-validation --package-def <path>
                              [--write-evidence]

``--root-usd`` identifies the entry-point USD file(s) inside
``<source>`` (relative paths, repeatable).  It is required unless
``.metadata/com.nvidia.simready.root_usds.json`` already exists in
``<source>`` from a prior run.  If the source folder intentionally
contains no USD files, pass ``--no-usd-files`` instead.

The default form runs all three phases.  Use ``--skip-*`` to opt out
of an individual phase, or ``--only-*`` to run a single phase against
the matching input.

In the default full flow (all three phases), ``--write-metadata`` is
implicitly enabled so the create step can verify and register the
conformance results.  Use ``--write-metadata`` explicitly with
``--only-pre-validation`` to produce ``.metadata/`` without running
the create step.

``--no-wrapp`` switches the create phase to a lightweight backend
that writes a minimal ``com.nvidia.simready.packaging.json`` into
``<source>`` directly (no BOM, no ``.metadata/``, no WRAPP
dependency).  In that mode there is no separate ``<repo>`` — the
source folder *is* the package — so the ``<repo>`` positional
argument must be omitted.  Pre-validation stamps results into the USD
file directly, and post-validation uses the ``Package-NoBOM`` profile
(core package rules only, no BOM check).

Exit codes: ``0`` if every phase that ran exited ``0``; otherwise the
non-zero exit code of the first phase to fail.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import logging
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

# Avoid asset-validator INFO messages when imported.
logging.basicConfig(level=logging.WARNING)

import simready.validate as sv
from omni.asset_validator import to_identifier

from sr_pkg_sample import (
    FOUNDATIONS_DOCS_DIR,
    BuildFailed,
    UsageError,
    ValidationFailed,
    post_validate,
    pre_validate,
)
from sr_pkg_sample._package_def import CreatedPackage
from sr_pkg_sample.results import PostValidationResult, PreValidationResult

EXIT_OK = 0
EXIT_VALIDATION_OR_BUILD_FAILED = 1
EXIT_USAGE_ERROR = 2


# ---------------------------------------------------------------------------
# Requirement metadata lookup — built once after sv.initialize().
# ---------------------------------------------------------------------------

_req_info: dict[str, tuple[str, str]] = {}


def _build_req_info() -> None:
    """Populate ``_req_info`` with ``{code: (display_name, message)}``."""
    from omni.asset_validator import RequirementsRegistry

    reg = RequirementsRegistry()
    for key in reg.keys():
        req = reg.get(key)
        _req_info[req.code] = (req.display_name, req.message)


def _format_failing_requirements(
    raw: str,
    issues: dict[str, list[str]] | None = None,
) -> list[str]:
    """Turn the engine's ``"['NP.005', 'NP.006']"`` string into display lines.

    When *issues* is provided (a dict mapping requirement codes to the
    list of Issue objects produced by the validator), each
    requirement line is followed by the actual failure messages so the
    user can see exactly what went wrong.
    """
    try:
        codes = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return [f"  {raw}"]
    lines: list[str] = []
    for code in codes:
        if code in _req_info:
            name, msg = _req_info[code]
            lines.append(f"  {code}  {name} — {msg}")
        else:
            lines.append(f"  {code}")
        if issues and code in issues:
            for m in issues[code]:
                if m.at is not None:
                    lines.append(f"    at: {to_identifier(m.at).as_str()}")
                if m.message is not None:
                    lines.append(f"    {m.message}")
    return lines


# ---------------------------------------------------------------------------
# Printing helpers — translate result objects into the terminal output
# that the workflow has always produced.
# ---------------------------------------------------------------------------

def _print_pre_result(result: PreValidationResult) -> None:
    """Print per-USD per-feature PASS/FAIL lines, metadata confirmations, and summary."""
    print("\n--- Pre-validation ---")
    for profile_id, asset_results in result.results.items():
        for rel_path, engine_result in asset_results:
            if engine_result is None:
                print(
                    f"FAIL {rel_path}: simready.validate returned no result",
                    file=sys.stderr,
                )
                continue
            features = engine_result.features_summary
            if not features:
                print(
                    f"FAIL {rel_path}: no features evaluated for profile "
                    f"{profile_id!r} v{result.profile_version}",
                    file=sys.stderr,
                )
                continue
            for fid in sorted(features):
                detail = features[fid]
                passed = bool(detail.get("passed"))
                if passed:
                    print(f"PASS {fid}: {rel_path}")
                else:
                    print(f"FAIL {fid}: {rel_path}")
                    raw = detail.get("failing requirements", "")
                    issues = detail.get("issues")
                    if raw:
                        for line in _format_failing_requirements(raw, issues):
                            print(line)

    for path in result.metadata_written:
        print(f"Wrote {path}")

    print()
    profiles = list(result.results)
    profiles_str = ", ".join(profiles)
    n_assets = max(
        (len(pairs) for pairs in result.results.values()),
        default=0,
    )
    if result.passed:
        suffix = "; .metadata/ written." if result.metadata_written else "."
        print(
            f"OK: {result.source} passed [{profiles_str}] "
            f"on {n_assets} {'root ' if result.metadata_written else ''}USD file(s){suffix}"
        )
    else:
        summary = f"{result.source} did not pass [{profiles_str}]"
        print(f"FAIL: {summary}", file=sys.stderr)


def _print_post_result(result: PostValidationResult) -> None:
    """Print per-feature PASS/FAIL lines, evidence confirmations, and summary."""
    print("\n--- Post-validation ---")
    for _profile_id, asset_results in result.results.items():
        for rel_path, engine_result in asset_results:
            if engine_result is None:
                print(
                    f"FAIL {rel_path}: simready.validate returned no result",
                    file=sys.stderr,
                )
                continue
            features = engine_result.features_summary
            if not features:
                print(
                    f"FAIL {rel_path}: no features evaluated for profile "
                    f"{_profile_id!r} v{result.profile_version}",
                    file=sys.stderr,
                )
                continue
            for fid in sorted(features):
                detail = features[fid]
                passed = bool(detail.get("passed"))
                if passed:
                    print(f"PASS {fid}: {rel_path}")
                else:
                    print(f"FAIL {fid}: {rel_path}")
                    raw = detail.get("failing requirements", "")
                    issues = detail.get("issues")
                    if raw:
                        for line in _format_failing_requirements(raw, issues):
                            print(line)

    for path in result.evidence_paths:
        pkg_dir = result.package_def.parent
        print(f"Wrote evidence: {path.relative_to(pkg_dir)}")

    print()
    profiles_str = ", ".join(result.results)
    if result.passed:
        print(
            f"OK: {result.package_def} passed every feature of "
            f"[{profiles_str}] v{result.profile_version}."
        )
    else:
        summary = (
            f"{result.package_def} did not pass every feature of "
            f"[{profiles_str}] v{result.profile_version}."
        )
        print(f"FAIL: {summary}", file=sys.stderr)


def _print_created(created: CreatedPackage, name: str, version: str) -> None:
    """Print write confirmations for the create step."""
    print("\n--- Create package ---")
    print(f"Wrote package definition: {created.pkg_def_url}")
    if created.bom_url:
        print(f"Wrote BOM metadata:       {created.bom_url}")
        print(f"OK: created {name} {version}")
    else:
        print(f"OK: created {name} {version} (definition only — no BOM)")


def _local_path_from_url(url: str) -> Path:
    """Resolve a local-or-``file://`` URL to a :class:`Path`."""
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    return Path(url)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_simready_package.py",
        description=(
            "Validate, build, and verify a SimReady-Foundation-conformant "
            "package in one shot.  Default behaviour runs all three phases."
        ),
    )

    parser.add_argument("name", nargs="?", help="package name (e.g. apple_a01)")
    parser.add_argument("version", nargs="?", help="package version (e.g. 1.0.0)")
    parser.add_argument(
        "license",
        nargs="?",
        help="SPDX licence identifier for the asset (e.g. MIT, Apache-2.0)",
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="folder of USD files to publish",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        help="WRAPP repository to publish into (path or URL)",
    )

    parser.add_argument(
        "--skip-pre-validation",
        action="store_true",
        help="skip phase 1 (pre-validation) — use if you already ran it.",
    )
    parser.add_argument(
        "--skip-post-validation",
        action="store_true",
        help="skip phase 3 (post-validation) — use if you'll validate later.",
    )

    parser.add_argument(
        "--no-wrapp",
        dest="no_wrapp",
        action="store_true",
        help=(
            "use the WRAPP-less backend for the create phase: write a "
            "minimal com.nvidia.simready.packaging.json (required fields "
            "only, no BOM) into <source>.  Drops the <repo> positional; "
            "the source folder is the package."
        ),
    )

    only_group = parser.add_mutually_exclusive_group()
    only_group.add_argument(
        "--only-pre-validation",
        action="store_true",
        help=(
            "run only phase 1 against the folder given via --source.  "
            "Mutually exclusive with all positional arguments."
        ),
    )
    only_group.add_argument(
        "--only-post-validation",
        action="store_true",
        help=(
            "run only phase 3 against the package-definition file given via "
            "--package-def.  Mutually exclusive with all positional arguments."
        ),
    )

    parser.add_argument(
        "--source",
        dest="only_source",
        help="source folder (only with --only-pre-validation).",
    )
    parser.add_argument(
        "--package-def",
        dest="only_package_def",
        help="path to com.nvidia.simready.packaging.json (only with --only-post-validation).",
    )

    parser.add_argument(
        "--write-metadata",
        action="store_true",
        help=(
            "write .metadata/ files (BOM, root_usds, conformance JSONs) "
            "during pre-validation.  Enabled implicitly in the default "
            "full flow; use explicitly with --only-pre-validation."
        ),
    )
    parser.add_argument(
        "--profile",
        dest="profiles",
        action="append",
        metavar="PROFILE",
        help=(
            "validation profile to use (repeatable).  "
            "Default: Package-Candidate for pre-validation."
        ),
    )
    parser.add_argument(
        "--root-usd",
        dest="root_usds",
        action="append",
        metavar="PATH",
        help=(
            "relative path of a root USD file inside <source> (repeatable).  "
            "Required unless .metadata/com.nvidia.simready.root_usds.json "
            "already exists or --no-usd-files is given."
        ),
    )
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help=(
            "write a conformance evidence JSON into .metadata/ during "
            "post-validation.  Enabled implicitly in the default full "
            "flow; use explicitly with --only-post-validation."
        ),
    )
    parser.add_argument(
        "--no-usd-files",
        dest="no_usd_files",
        action="store_true",
        help=(
            "allow pre-validation to succeed even when no root USD files "
            "are found in <source>.  Without this flag, an empty source "
            "folder is treated as a usage error."
        ),
    )

    parser.add_argument(
        "--sha256-only",
        action="store_true",
        help=(
            "limit hash objects to SHA-256 only (omit BLAKE3).  "
            "By default BLAKE3 hashes are included alongside SHA-256 "
            "when the blake3 library is installed, as recommended by "
            "PKG.HASH.001."
        ),
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show detailed INFO/WARNING log messages from the validation engine.",
    )

    return parser


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int | None:
    """Cross-check the parsed args; return an exit code if they are bad."""
    positional = (args.name, args.version, args.license, args.source, args.repo)
    has_positional = any(p is not None for p in positional)

    if args.only_pre_validation:
        if has_positional or args.only_package_def is not None:
            parser.error(
                "--only-pre-validation rejects positional arguments and --package-def"
            )
        if args.only_source is None:
            parser.error("--only-pre-validation requires --source <folder>")
        if args.skip_pre_validation:
            parser.error(
                "--skip-pre-validation contradicts --only-pre-validation"
            )
        # --skip-post-validation and --no-wrapp are no-ops here (the
        # post-validation and create phases never run in --only-pre
        # mode), so we accept them silently.
        return None

    if args.only_post_validation:
        if has_positional or args.only_source is not None:
            parser.error(
                "--only-post-validation rejects positional arguments and --source"
            )
        if args.only_package_def is None:
            parser.error("--only-post-validation requires --package-def <path>")
        if args.skip_post_validation:
            parser.error(
                "--skip-post-validation contradicts --only-post-validation"
            )
        # --skip-pre-validation and --no-wrapp are no-ops here (the
        # pre-validation and create phases never run in --only-post
        # mode), so we accept them silently.
        return None

    # Default flow.  ``--no-wrapp`` drops the <repo> positional (the
    # source folder is the package); the regular flow requires all
    # five positionals.
    if args.no_wrapp:
        required_names = ("name", "version", "license", "source")
        required_values = positional[:4]
        if args.repo is not None:
            parser.error(
                "--no-wrapp does not accept a <repo> positional "
                "argument — the package is written in place into <source>."
            )
    else:
        required_names = ("name", "version", "license", "source", "repo")
        required_values = positional

    missing = [n for n, v in zip(required_names, required_values) if v is None]
    if missing:
        usage = (
            "<name> <version> <license> <source> --no-wrapp"
            if args.no_wrapp
            else "<name> <version> <license> <source> <repo>"
        )
        parser.error(
            "missing positional argument(s): "
            + ", ".join(missing)
            + f" — pass {usage}, or use --only-*."
        )
    if args.only_source is not None or args.only_package_def is not None:
        parser.error(
            "--source and --package-def are reserved for --only-* modes; "
            "in the default flow the source folder is the 4th positional argument."
        )
    return None


def _initialize_runtime() -> None:
    """Initialise simready.validate exactly once."""
    sv.initialize(
        rules_and_requirements_paths=[FOUNDATIONS_DOCS_DIR / "capabilities"],
        features_paths=[FOUNDATIONS_DOCS_DIR / "features"],
        profiles_paths=[FOUNDATIONS_DOCS_DIR / "profiles" / "profiles.toml"],
    )


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])
    _validate_args(args, parser)

    log_level = logging.INFO if args.verbose else logging.WARNING
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)

    _initialize_runtime()
    _build_req_info()

    try:
        asyncio.run(_run(args))
        return EXIT_OK
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except (ValidationFailed, BuildFailed):
        return EXIT_VALIDATION_OR_BUILD_FAILED


async def _run(args: argparse.Namespace) -> None:
    """Dispatch *args* to the matching workflow or single-phase call."""
    if args.only_pre_validation:
        await _run_only_pre(args)
        return

    if args.only_post_validation:
        await _run_only_post(args)
        return

    if args.no_wrapp:
        await _run_no_wrapp(args)
    else:
        await _run_wrapp(args)


async def _run_only_pre(args: argparse.Namespace) -> None:
    """``--only-pre-validation`` mode."""
    pre_result: PreValidationResult | None = None
    try:
        pre_result = await pre_validate(
            Path(args.only_source),
            profiles=args.profiles,
            root_usds=args.root_usds,
            write_metadata=args.write_metadata,
            allow_no_usd_files=args.no_usd_files,
            sha256_only=args.sha256_only,
        )
    except ValidationFailed as exc:
        pre_result = exc.result  # type: ignore[assignment]
        raise
    finally:
        if pre_result is not None:
            _print_pre_result(pre_result)


async def _run_only_post(args: argparse.Namespace) -> None:
    """``--only-post-validation`` mode."""
    post_result: PostValidationResult | None = None
    try:
        post_result = await post_validate(
            Path(args.only_package_def),
            write_evidence=args.write_evidence,
        )
    except ValidationFailed as exc:
        post_result = exc.result  # type: ignore[assignment]
        raise
    finally:
        if post_result is not None:
            _print_post_result(post_result)


async def _run_wrapp(args: argparse.Namespace) -> None:
    """Default WRAPP-backed flow with per-phase printing."""
    source_path = Path(args.source)

    if not args.skip_pre_validation:
        pre_result: PreValidationResult | None = None
        try:
            pre_result = await pre_validate(
                source_path,
                profiles=args.profiles,
                root_usds=args.root_usds,
                write_metadata=True,
                allow_no_usd_files=args.no_usd_files,
                sha256_only=args.sha256_only,
            )
        except ValidationFailed as exc:
            pre_result = exc.result  # type: ignore[assignment]
            raise
        finally:
            if pre_result is not None:
                _print_pre_result(pre_result)

    from sr_pkg_sample.create_package_using_wrapp import create_package

    created = await create_package(
        args.name, args.version, args.license, args.source, args.repo,
        sha256_only=args.sha256_only,
    )
    _print_created(created, args.name, args.version)

    if not args.skip_post_validation:
        pkg_def = _local_path_from_url(created.pkg_def_url)
        post_result: PostValidationResult | None = None
        try:
            post_result = await post_validate(pkg_def, write_evidence=True)
        except ValidationFailed as exc:
            post_result = exc.result  # type: ignore[assignment]
            raise
        finally:
            if post_result is not None:
                _print_post_result(post_result)


async def _run_no_wrapp(args: argparse.Namespace) -> None:
    """WRAPP-free flow with per-phase printing."""
    source_path = Path(args.source)

    if not args.skip_pre_validation:
        pre_result: PreValidationResult | None = None
        try:
            pre_result = await pre_validate(
                source_path,
                profiles=args.profiles,
                root_usds=args.root_usds,
                stamp_usd=True,
                allow_no_usd_files=args.no_usd_files,
            )
        except ValidationFailed as exc:
            pre_result = exc.result  # type: ignore[assignment]
            raise
        finally:
            if pre_result is not None:
                _print_pre_result(pre_result)

    from sr_pkg_sample.create_package_definition import create_package_definition

    created = await create_package_definition(
        args.name, args.version, args.license, args.source,
    )
    _print_created(created, args.name, args.version)

    if not args.skip_post_validation:
        pkg_def = Path(created.pkg_def_url)
        post_result: PostValidationResult | None = None
        try:
            post_result = await post_validate(pkg_def, profiles=["Package-NoBOM"])
        except ValidationFailed as exc:
            post_result = exc.result  # type: ignore[assignment]
            raise
        finally:
            if post_result is not None:
                _print_post_result(post_result)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
