"""CLI-surface tests for the ``create_simready_package.py`` orchestrator.

The per-step tests in this directory exercise the public ``sr_pkg_sample.*``
API directly; this module is the only place we still pay the cost of
spawning a subprocess, because the orchestrator's value is its CLI:
argument parsing, mutually-exclusive ``--only-*`` modes, the
``--skip-*`` opt-outs, and one-shot validation-runtime initialisation
across all three phases.

Each test runs ``create_simready_package.py`` from the package_sample
directory with ``sys.executable`` (so it picks up the active venv).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"


def _run_orchestrator(
    package_sample_dir: Path, *args: str, env_override: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    import os

    script = package_sample_dir / "create_simready_package.py"
    assert script.is_file(), f"create_simready_package.py is missing at {script}"
    env = {**os.environ, **(env_override or {})}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=package_sample_dir,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_orchestrator_default_flow_runs_all_three_phases(
    package_sample_dir: Path, sample_source_copy: Path, tmp_path: Path
) -> None:
    """Five positional args → pre-validation, create, post-validation.

    All three phases must run in order against the apple_a01 sample
    and the orchestrator must exit ``0`` because the source is
    candidate-clean and the freshly built package satisfies the
    ``Package`` profile.  The output should carry one signature line
    from each phase so we know the orchestrator did not silently skip
    one.
    """
    pytest.importorskip("wrapp", reason="wrapp is required to build the package")

    repo = tmp_path / "repo"
    repo.mkdir()

    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        str(repo),
        "--root-usd", "sm_apple_a01_01.usd",
    )

    assert result.returncode == 0, (
        "default flow failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "PASS FET031_PACKAGE_SELF_CONTAINED" in result.stdout, result.stdout
    assert "OK: created apple_a01 1.0.0" in result.stdout, result.stdout
    assert "PASS FET030_PACKAGING_CORE" in result.stdout, result.stdout
    assert "PASS FET032_PACKAGING_INTROSPECTION" in result.stdout, result.stdout

    pkg_def = repo / ".packages" / "apple_a01" / "1.0.0" / PACKAGE_DEF_NAME
    assert pkg_def.is_file(), f"package definition missing at {pkg_def}"
    definition = json.loads(pkg_def.read_text())
    assert definition["license"] == "MIT", definition


def test_orchestrator_only_pre_validation(
    package_sample_dir: Path, sample_source: Path
) -> None:
    """``--only-pre-validation --source`` runs phase 1 alone.

    No ``<repo>``, no positional arguments, no build — just the
    pre-validation pass against the read-only sample source folder.
    """
    result = _run_orchestrator(
        package_sample_dir,
        "--only-pre-validation",
        "--source",
        str(sample_source),
    )

    assert result.returncode == 0, (
        "--only-pre-validation failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "PASS FET031_PACKAGE_SELF_CONTAINED" in result.stdout, result.stdout
    # Phases 2 and 3 must not have run.
    assert "OK: created" not in result.stdout, result.stdout
    assert "PASS FET030_PACKAGING_CORE" not in result.stdout, result.stdout


def test_orchestrator_only_post_validation(
    package_sample_dir: Path, foundations_dir: Path
) -> None:
    """``--only-post-validation --package-def`` runs phase 3 alone.

    Drives the orchestrator against the committed ``apple_a01_nobom``
    sample; it lacks a BOM so ``FET032_PACKAGING_INTROSPECTION`` fails,
    causing the orchestrator to exit non-zero while still leaving the
    per-feature summary lines on stdout.
    """
    pkg_def = (
        foundations_dir
        / "sample_content"
        / "packaging"
        / "simple_packages"
        / "apple_a01_nobom"
        / PACKAGE_DEF_NAME
    )
    if not pkg_def.is_file():
        pytest.skip(f"Sample package definition missing: {pkg_def}")

    result = _run_orchestrator(
        package_sample_dir,
        "--only-post-validation",
        "--package-def",
        str(pkg_def),
    )

    assert result.returncode != 0, (
        "--only-post-validation exited 0 on apple_a01_nobom; expected non-zero.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "PASS FET030_PACKAGING_CORE" in result.stdout, result.stdout
    assert "FAIL FET032_PACKAGING_INTROSPECTION" in result.stdout, result.stdout
    # Phases 1 and 2 must not have run.
    assert "PASS FET031_PACKAGE_SELF_CONTAINED" not in result.stdout, result.stdout
    assert "OK: created" not in result.stdout, result.stdout


def test_orchestrator_skip_post_validation(
    package_sample_dir: Path, sample_source_copy: Path, tmp_path: Path
) -> None:
    """``--skip-post-validation`` runs phases 1 + 2 but not 3.

    Useful for users who want to publish without paying the cost of a
    full ``Package``-profile validation right after the build (or who
    plan to validate later).
    """
    pytest.importorskip("wrapp", reason="wrapp is required to build the package")

    repo = tmp_path / "repo"
    repo.mkdir()

    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        str(repo),
        "--root-usd", "sm_apple_a01_01.usd",
        "--skip-post-validation",
    )

    assert result.returncode == 0, (
        "--skip-post-validation flow failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "PASS FET031_PACKAGE_SELF_CONTAINED" in result.stdout, result.stdout
    assert "OK: created apple_a01 1.0.0" in result.stdout, result.stdout
    # Post-validation prints either "PASS FET030_PACKAGING_CORE" or
    # "FAIL FET030_PACKAGING_CORE" — neither must appear.  (The plain
    # FET030 substring shows up in the simready.validate registration
    # logs at startup, so we cannot match on that.)
    assert "PASS FET030_PACKAGING_CORE" not in result.stdout, (
        "post-validation appears to have run despite --skip-post-validation:\n"
        + result.stdout
    )
    assert "FAIL FET030_PACKAGING_CORE" not in result.stdout, (
        "post-validation appears to have run despite --skip-post-validation:\n"
        + result.stdout
    )

    pkg_def = repo / ".packages" / "apple_a01" / "1.0.0" / PACKAGE_DEF_NAME
    assert pkg_def.is_file(), f"package definition missing at {pkg_def}"


def test_orchestrator_skip_pre_validation(
    package_sample_dir: Path, sample_source_copy: Path, tmp_path: Path
) -> None:
    """``--skip-pre-validation`` runs phases 2 + 3 but not 1.

    Inject a root-level ``com.nvidia.simready.packaging.json`` into the
    source — this would normally trip the pre-validation guard.  With
    the skip flag the orchestrator must dive straight into the create
    step instead (which itself fails because the source already
    carries built-package artifacts; that is expected — we only assert
    that pre-validation did *not* run).
    """
    pytest.importorskip("wrapp", reason="wrapp is required to drive create")

    # The injected file is enough to trip the pre-validation guard.
    (sample_source_copy / "com.nvidia.simready.packaging.json").write_text("{}")

    repo = tmp_path / "repo"
    repo.mkdir()

    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        str(repo),
        "--skip-pre-validation",
        "--skip-post-validation",
    )

    # The pre-validation guard's signature message must not appear — it
    # would have been printed if pre_validate had actually run.
    assert "looks like a built SimReady package" not in (
        result.stdout + result.stderr
    ), result.stdout + result.stderr


def test_orchestrator_only_pre_validation_rejects_positional(
    package_sample_dir: Path, sample_source: Path
) -> None:
    """``--only-pre-validation`` together with positional args is an error.

    Argparse's ``parser.error`` exits 2 and writes a usage line to
    stderr; the orchestrator must propagate that without ever calling
    into the sr_pkg_sample API.
    """
    result = _run_orchestrator(
        package_sample_dir,
        "--only-pre-validation",
        "--source",
        str(sample_source),
        "apple_a01",
    )

    assert result.returncode != 0
    assert "rejects positional arguments" in result.stderr.lower() or (
        "error" in result.stderr.lower()
    ), result.stderr


def test_orchestrator_default_flow_missing_args(package_sample_dir: Path) -> None:
    """Running the default flow without all five positionals must fail.

    A clear "missing positional argument(s)" message tells the user
    which arguments to supply (and that ``--only-*`` is the alternative).
    """
    result = _run_orchestrator(package_sample_dir)

    assert result.returncode != 0
    assert "missing positional argument" in result.stderr.lower(), result.stderr


def test_orchestrator_no_wrapp_skips_wrapp(
    package_sample_dir: Path, sample_source_copy: Path
) -> None:
    """``--no-wrapp`` writes a minimal pkg def into <source>, skips WRAPP.

    Pre-validation stamps validation results into the USD file's
    ``customLayerData`` (no ``.metadata/``, no BOM, no WRAPP
    dependency).  The WRAPP-less create step stamps
    ``com.nvidia.simready.packaging.json`` into ``<source>``.
    Post-validation runs the ``Package-NoBOM`` profile (FET030 only —
    no BOM check), so the exit code is 0.

    Notably, no ``<repo>`` argument is passed — the source folder is
    the package.
    """
    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        "--no-wrapp",
    )

    assert result.returncode == 0, (
        f"--no-wrapp unexpectedly exited {result.returncode}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "PASS FET031_PACKAGE_SELF_CONTAINED" in result.stdout, result.stdout
    assert "OK: created apple_a01 1.0.0 (definition only" in result.stdout, result.stdout
    assert "PASS FET030_PACKAGING_CORE" in result.stdout, result.stdout
    assert "PASS FET032" not in result.stdout and "FAIL FET032" not in result.stdout, (
        "FET032 should not be validated in --no-wrapp post-validation "
        "(Package-NoBOM profile):\n" + result.stdout
    )

    pkg_def = sample_source_copy / PACKAGE_DEF_NAME
    assert pkg_def.is_file(), f"definition missing at {pkg_def}"
    definition = json.loads(pkg_def.read_text())
    assert set(definition.keys()) == {"format_version", "package_id", "license"}, definition

    # Repo-style layout must NOT exist — the source folder is the package.
    assert not (sample_source_copy / ".packages").exists(), (
        "--no-wrapp produced a .packages/ tree; expected in-place stamping only."
    )


def test_orchestrator_no_wrapp_with_skip_post(
    package_sample_dir: Path, sample_source_copy: Path
) -> None:
    """``--no-wrapp --skip-post-validation`` exits 0.

    Same flow as the previous test but post-validation is skipped, so
    the FET032 fail can't surface and the orchestrator exits clean.
    Useful for users who explicitly want a minimal package and don't
    want the FET032 failure to gate publication.
    """
    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        "--no-wrapp",
        "--skip-post-validation",
    )

    assert result.returncode == 0, (
        "--no-wrapp --skip-post-validation failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "OK: created apple_a01 1.0.0 (definition only" in result.stdout, result.stdout
    assert "PASS FET030_PACKAGING_CORE" not in result.stdout, result.stdout


def test_orchestrator_no_wrapp_rejects_repo(
    package_sample_dir: Path, sample_source_copy: Path, tmp_path: Path
) -> None:
    """``--no-wrapp`` together with a 5th positional <repo> is an error.

    The WRAPP-less path has no concept of a repository — the source
    folder *is* the package — so passing a ``<repo>`` would be
    misleading.  Argparse-level rejection keeps the user from
    accidentally writing a package they didn't intend.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        str(repo),
        "--no-wrapp",
    )

    assert result.returncode != 0
    assert "--no-wrapp" in result.stderr, result.stderr
    assert "<repo>" in result.stderr or "repo" in result.stderr.lower(), result.stderr


def test_orchestrator_no_wrapp_without_wrapp_installed(
    package_sample_dir: Path, sample_source_copy: Path, tmp_path: Path
) -> None:
    """``--no-wrapp`` works even when the ``wrapp`` package is not importable.

    Poisons ``import wrapp`` in the subprocess by prepending a tiny
    ``wrapp.py`` stub that raises ``ImportError`` to ``PYTHONPATH``.
    The ``--no-wrapp`` flow must never touch ``wrapp``, so the
    orchestrator should exit 0 just as it does with WRAPP present.
    """
    poison_dir = tmp_path / "_poison"
    poison_dir.mkdir()
    (poison_dir / "wrapp.py").write_text(
        'raise ImportError("wrapp is not installed (test poison)")\n'
    )

    result = _run_orchestrator(
        package_sample_dir,
        "apple_a01",
        "1.0.0",
        "MIT",
        str(sample_source_copy),
        "--no-wrapp",
        env_override={"PYTHONPATH": str(poison_dir)},
    )

    assert result.returncode == 0, (
        f"--no-wrapp failed without wrapp installed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
