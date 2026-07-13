#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Run all repository pytest test suites.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
VENV_ROOT = REPO_ROOT / "_build" / "test-venvs"

# Test suite configuration. To add a suite, add its test directory. The
# runner derives the pip dependencies from `<test_dir>/requirements.txt`.
TEST_SUITES = {
    "aif": {
        "test_dir": "nv_core/sr_specs/tests",
        "cwd": "nv_core/sr_specs",
        "pytest_args": ["-v"],
    },
}

MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 13)


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"+ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def _upgrade_pip(python: Path) -> None:
    try:
        _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=REPO_ROOT)
    except subprocess.CalledProcessError as exc:
        print(f"WARNING: pip upgrade failed with exit code {exc.returncode}; continuing with bundled pip.")


def _create_venv_if_needed(venv_dir: Path) -> Path:
    python = _venv_python(venv_dir)
    if python.exists():
        return python

    print(f"Creating test venv: {venv_dir.relative_to(REPO_ROOT)}")
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        venv.create(venv_dir, with_pip=True)
    except Exception as exc:
        raise RuntimeError(
            "Failed to create the test virtual environment. Make sure this Python "
            "installation includes venv/ensurepip support. On Debian/Ubuntu, install "
            "the matching python3-venv package."
        ) from exc
    _upgrade_pip(python)
    return python


def _install_requirements(python: Path, requirements: Path) -> None:
    if not requirements.exists():
        print(f"No requirements file found at {requirements.relative_to(REPO_ROOT)}; skipping install.")
        return
    try:
        _run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=REPO_ROOT)
    except subprocess.CalledProcessError:
        print(
            "\nERROR: Failed to install test dependencies. If a package such as "
            "'simready-validate' could not be found, the required package index is "
            "probably not configured. Set PIP_EXTRA_INDEX_URL to the index hosting "
            "these packages (see nv_core/sr_specs/tests/README.md) and re-run.",
            file=sys.stderr,
        )
        raise


def _suite_paths(suite: dict[str, object]) -> tuple[Path, Path, Path]:
    test_dir = (REPO_ROOT / str(suite["test_dir"])).resolve()
    cwd_config = suite.get("cwd")
    cwd = (REPO_ROOT / str(cwd_config)).resolve() if cwd_config else test_dir.parent.resolve()
    requirements = test_dir / "requirements.txt"
    return test_dir, cwd, requirements


def _pytest_path(path: Path, cwd: Path) -> str:
    try:
        return str(path.relative_to(cwd))
    except ValueError:
        return str(path)


def run_suite(name: str) -> None:
    suite = TEST_SUITES[name]
    test_dir, cwd, requirements = _suite_paths(suite)
    venv_dir = VENV_ROOT / name

    python = _create_venv_if_needed(venv_dir)
    _install_requirements(python, requirements)

    pytest_paths = [_pytest_path(test_dir, cwd)]
    suite_pytest_args = [str(arg) for arg in suite.get("pytest_args", ["-v"])]
    command = [str(python), "-m", "pytest", *pytest_paths, *suite_pytest_args]
    _run(command, cwd=cwd)


def main() -> int:
    if sys.version_info < MIN_PYTHON or sys.version_info >= MAX_PYTHON_EXCLUSIVE:
        min_version = ".".join(str(part) for part in MIN_PYTHON)
        max_version = ".".join(str(part) for part in MAX_PYTHON_EXCLUSIVE)
        print(
            f"Python {min_version}+ and <{max_version} is required; "
            f"running {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 2

    try:
        for suite_name in TEST_SUITES:
            run_suite(suite_name)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
