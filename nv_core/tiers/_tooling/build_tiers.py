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

"""Portable builder for SimReady tier wheels.

The tiers root (this ``_tooling/`` directory's parent) is a uv workspace, and
every tier is a member of it. One ``uv build --all-packages`` therefore builds
the tiers, including any runtime tests advertised by their tier descriptors.
This module builds into an owned temporary staging directory, sanity-checks the
result, and then publishes only the wheel distributions produced by that run.
Unrelated files already present in ``<tiers root>/_build/dist/`` are preserved.

The Kit-free Isaac asset transformer is not built as its own wheel: its source
lives under ``simready_foundation_tier_core/tools/`` and is force-included into
the tier-core wheel (see that tier's ``pyproject.toml``). Only workspace members
are built here.

Each tier's Hatchling build hook (``build_hook.py``, here) generates the
requirements-enum module during the build; that codegen needs
``usd_profiles_nvidia`` (+ ``pxr``) resolvable at build time -- point uv at the
internal index the usual way (``UV_EXTRA_INDEX_URL`` or a uv config) if it isn't
on the default index.

This module has **no repoman / Omniverse dependency** so it can travel with the
tiers source and be run by third parties who don't have the repoman framework::

    python nv_core/tiers/_tooling/build_tiers.py

``uv`` is taken from ``PATH``. Inside this repo, ``repo build_tiers``
(``tools/repoman/build_tiers.py``) is a thin wrapper that just injects the
repo-managed ``uv`` and calls :func:`build_tiers`.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Optional, Sequence, Tuple

# Tiers live next to this _tooling/ directory: every tier's pyproject points
# hatchling at ../_tooling/build_hook.py, so the tiers root is _tooling/'s parent.
_TIERS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TierBuildError(RuntimeError):
    """Raised for setup problems that prevent building (e.g. ``uv`` not found)."""


def _wheel_distribution_key(wheel_path: str) -> str:
    """Return the normalized distribution component of a wheel filename."""
    filename = os.path.basename(wheel_path)
    if not filename.lower().endswith(".whl"):
        raise TierBuildError(f"not a wheel artifact: {wheel_path}")
    distribution, separator, _ = filename.partition("-")
    if not separator or not distribution:
        raise TierBuildError(f"invalid wheel filename: {filename}")
    return distribution.lower()


def _publish_staged_wheels(staged_wheels: Sequence[str], out_dir: str) -> List[str]:
    """Publish staged wheels while preserving unrelated output-directory data.

    New artifacts are moved into place first. Only stale ``.whl`` files for the
    exact distributions produced by this build are then removed; other files,
    directories, and wheel distributions are never touched.
    """
    distribution_keys = {_wheel_distribution_key(path) for path in staged_wheels}
    os.makedirs(out_dir, exist_ok=True)

    published: List[str] = []
    for staged_path in staged_wheels:
        destination = os.path.join(out_dir, os.path.basename(staged_path))
        os.replace(staged_path, destination)
        published.append(destination)

    published_names = {os.path.basename(path) for path in published}
    for existing_path in glob.glob(os.path.join(out_dir, "*.whl")):
        if os.path.basename(existing_path) in published_names:
            continue
        try:
            existing_key = _wheel_distribution_key(existing_path)
        except TierBuildError:
            # A file that is not a valid wheel name is not one of our known
            # generated artifacts. Preserve it rather than guessing ownership.
            continue
        if existing_key in distribution_keys:
            os.remove(existing_path)
    return sorted(published)


def discover_tiers(tiers_root: str) -> List[str]:
    """Return every tier directory (those with a ``pyproject.toml``) under ``tiers_root``.

    Directories without a ``pyproject.toml`` are skipped, so the shared
    ``_tooling/`` directory is ignored automatically. The workspace root's own
    ``pyproject.toml`` is a file rather than a directory, so it is skipped too.

    uv resolves the workspace members it builds from ``tiers_root``'s
    ``[tool.uv.workspace]`` table, so this scan does not drive the build. It
    gives :func:`build_tiers` an independent count to check uv's output against,
    and gives ``assemble_docs`` the same sorted tier list the builder sees.
    """
    if not os.path.isdir(tiers_root):
        return []
    tiers: List[str] = []
    for name in sorted(os.listdir(tiers_root)):
        tier_dir = os.path.join(tiers_root, name)
        if not os.path.isfile(os.path.join(tier_dir, "pyproject.toml")):
            continue  # e.g. the shared _tooling/ dir
        tiers.append(tier_dir)
    return tiers


def build_tiers(
    tiers_root: str = _TIERS_ROOT,
    *,
    uv: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Build every tier wheel into ``_build/dist/``.

    Args:
        tiers_root: The uv workspace root containing the tier packages. Defaults
            to the parent of this ``_tooling/`` directory, where the tiers are
            always siblings.
        uv: Path to the ``uv`` executable. Defaults to ``uv`` found on ``PATH``.
    Returns:
        ``(built, failures)`` -- a list of built wheel paths and a list of
        failure descriptions. Failure does not raise; the caller decides how to
        signal it. ``uv build --all-packages`` builds the members as a unit, so
        a failure is reported for the run rather than per tier; uv's own output
        names the member that failed.

    Raises:
        TierBuildError: if ``uv`` cannot be located.
    """
    tiers_root = os.path.abspath(tiers_root)
    uv = uv or shutil.which("uv")
    if not uv:
        raise TierBuildError("`uv` not found on PATH; pass uv=<path> or install uv.")

    # Shared across all members: `uv build --all-packages` writes every wheel to
    # one directory (covered by .gitignore, and a sibling of each tier's own
    # _build/python codegen scratch rather than inside it).
    build_root = os.path.join(tiers_root, "_build")
    out_dir = os.path.join(build_root, "dist")
    print("=" * 78)
    print("[build_tiers] Building SimReady tier wheels")
    print(f"[build_tiers]   workspace : {tiers_root}")
    print(f"[build_tiers]   out       : {out_dir}")
    print(f"[build_tiers]   uv        : {uv}")

    # Tier discovery is uv's job (the workspace members); this scan is only used
    # to assert afterwards that uv produced a wheel for each one.
    expected = [os.path.basename(t) for t in discover_tiers(tiers_root)]
    if not expected:
        print(f"[build_tiers]   no tiers with a pyproject.toml found under {tiers_root}")
        print("=" * 78)
        return [], []

    total_expected = len(expected)
    print(f"[build_tiers]   expecting {len(expected)} tier wheel(s) for: {', '.join(expected)}")
    os.makedirs(build_root, exist_ok=True)

    start = time.time()
    failures: List[str] = []
    built: List[str] = []
    with tempfile.TemporaryDirectory(prefix="tier-wheels-", dir=build_root) as staging_dir:
        tier_cmd = [uv, "build", "--wheel", "--all-packages", "--out-dir", staging_dir, tiers_root]
        print(f"[build_tiers]   staging   : {staging_dir}")
        print(f"[build_tiers]   run       : {' '.join(tier_cmd)}")
        print("=" * 78 + "\n")

        tier_returncode = subprocess.run(tier_cmd).returncode
        staged_wheels = sorted(glob.glob(os.path.join(staging_dir, "*.whl")))
        if tier_returncode != 0:
            failures.append(f"tier uv build exited {tier_returncode}")
        if not failures and len(staged_wheels) != total_expected:
            # uv returned 0 but did not produce the expected artifacts -> treat
            # it as a failure rather than publishing a partial result.
            failures.append(
                f"expected {total_expected} wheel(s), found {len(staged_wheels)} in the owned staging directory"
            )
        if not failures:
            try:
                built = _publish_staged_wheels(staged_wheels, out_dir)
            except (OSError, TierBuildError) as exc:
                failures.append(f"could not publish tier wheels to {out_dir}: {exc}")

    elapsed = time.time() - start

    print("\n" + "=" * 78)
    print(f"[build_tiers] Summary: {len(built)} wheel(s) built in {elapsed:.1f}s, {len(failures)} failure(s)")
    for whl in built:
        print(f"[build_tiers]   built  : {whl} ({os.path.getsize(whl) / 1024.0:.1f} KiB)")
    for failure in failures:
        print(f"[build_tiers]   FAILED : {failure}")
    print("=" * 78)

    return built, failures


def main(argv: Optional[Sequence[str]] = None) -> int:
    argparse.ArgumentParser(
        prog="build_tiers",
        description=(
            "Build every SimReady tier wheel (repoman-free). Tiers are the "
            "members of the uv workspace rooted at this _tooling/ package's parent; "
            "wheels go to <tiers root>/_build/dist/ and uv is taken from PATH. Set "
            "UV_EXTRA_INDEX_URL if the codegen dep isn't on the default index."
        ),
    ).parse_args(argv)

    try:
        _, failures = build_tiers()
    except TierBuildError as exc:
        print(f"[build_tiers] ERROR: {exc}", file=sys.stderr)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
