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

"""Editable-install SimReady tiers for local tier development.

The tier developer loop: edit a validator, feature manifest, profile TOML, or
requirement page in a tier checkout and have ``simready-validate`` pick the
change up without rebuilding and reinstalling a wheel.

An editable install registers the tier's ``simready.tier`` entry point in the
environment while its ``TierContent`` descriptor keeps resolving to the
checkout (it derives its paths from ``__file__``). Loading therefore goes
through the *same* entry-point discovery path that a released wheel uses --
``simready.validate.initialize(rules_and_requirements_paths=[],
features_paths=[], profiles_paths=[])`` -- rather than the filesystem-path
branch, so local development exercises production code.

Editable and wheel-installed tiers mix freely. ``simready`` and
``simready.foundation`` are namespace packages, so an editable experimental tier
resolves from its checkout while ``simready-foundation-tier-core`` stays
installed as an ordinary wheel from PyPI.

Requires nothing but a Python interpreter with ``pip``. Unlike
``build_tiers.py``, this needs no ``uv``: ``pip install -e`` drives each tier's
own Hatchling backend through PEP 517, which resolves ``hatchling`` and
``usd-profiles-nvidia`` into an isolated build environment and runs
``build_hook.py`` to generate the requirements enums.

::

    # every tier in this checkout, into the active interpreter
    python nv_core/tiers/_tooling/dev_install.py

    # one tier, into a specific virtual environment
    python nv_core/tiers/_tooling/dev_install.py \
        --tier simready_foundation_tier_core --python .venv/bin/python

Re-run this in two situations:

* After **adding or removing a requirement page**. Requirement enums are
  generated at install time, so a new requirement code is not importable until
  codegen runs again. Edits to validators, feature manifests, profiles, and
  existing requirement prose take effect with no re-run.
* After **building wheels** from the same checkout. A wheel build clears the
  in-checkout codegen mirror so the wheel cannot ship it twice, which leaves an
  active editable install without its requirements module (symptom:
  ``ModuleNotFoundError: No module named '<module>.requirements'``).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_tiers import _TIERS_ROOT, discover_tiers  # noqa: E402


class DevInstallError(RuntimeError):
    """Raised for setup problems that prevent installing (e.g. an unknown tier)."""


def resolve_tiers(tiers_root: str, names: Sequence[str] = ()) -> List[str]:
    """Return the selected tier directories, or every discovered tier.

    Tier discovery is shared with ``build_tiers`` so the two commands always
    agree on what a tier is. Names are matched on the tier's directory name; a
    path to the tier is accepted too, so shell completion works.

    Raises:
        DevInstallError: if a requested tier does not exist.
    """
    available = discover_tiers(tiers_root)
    if not names:
        return available

    by_name = {os.path.basename(path): path for path in available}
    selected: List[str] = []
    for name in names:
        key = os.path.basename(os.path.normpath(name))
        if key not in by_name:
            raise DevInstallError(
                f"unknown tier {name!r}; available: {', '.join(sorted(by_name)) or '(none)'}"
            )
        if by_name[key] not in selected:
            selected.append(by_name[key])
    return selected


def _report_discoverable_tiers(python: str) -> int:
    """Print the tiers the target interpreter can now discover, and where from.

    Reads the ``simready.tier`` entry points and shows each descriptor's resolved
    location, which is the quickest confirmation that a tier is being loaded from
    the checkout rather than from an installed wheel.
    """
    code = (
        "from importlib.metadata import entry_points\n"
        "import importlib\n"
        "eps = sorted(entry_points(group='simready.tier'), key=lambda e: e.name)\n"
        "if not eps:\n"
        "    print('  (none)')\n"
        "for ep in eps:\n"
        "    module = importlib.import_module(ep.value.split(':')[0])\n"
        "    print(f'  {ep.name:24} {getattr(module, \"__file__\", \"?\")}')\n"
    )
    print("[dev_install] tiers discoverable via the 'simready.tier' entry point:")
    return subprocess.run([python, "-c", code]).returncode


def dev_install(
    tiers_root: str = _TIERS_ROOT,
    *,
    names: Sequence[str] = (),
    python: Optional[str] = None,
    no_deps: bool = False,
) -> int:
    """Editable-install the selected tiers.

    Args:
        tiers_root: The directory containing the tier packages. Defaults to the
            parent of this ``_tooling/`` directory, where tiers are siblings.
        names: Tier directory names to install. Empty installs every tier found.
        python: Interpreter to install into. Defaults to the running one.
        no_deps: Pass ``--no-deps`` to pip, leaving an already-installed
            dependency stack untouched.

    Returns:
        A process exit code: 0 on success, otherwise pip's exit code.

    Raises:
        DevInstallError: if a requested tier does not exist.
    """
    tiers_root = os.path.abspath(tiers_root)
    python = python or sys.executable
    tiers = resolve_tiers(tiers_root, names)
    if not tiers:
        print(f"[dev_install] no tiers with a pyproject.toml found under {tiers_root}")
        return 0

    print("=" * 78)
    print("[dev_install] Editable-installing SimReady tiers")
    print(f"[dev_install]   tiers root : {tiers_root}")
    print(f"[dev_install]   python     : {python}")
    for tier in tiers:
        print(f"[dev_install]   tier       : {os.path.basename(tier)}")
    print("=" * 78)

    # One pip invocation for every tier, so a dependency between two tiers being
    # installed resolves against those checkouts instead of downloading the
    # published wheel over the editable install that was just made.
    command = [python, "-m", "pip", "install"]
    if no_deps:
        command.append("--no-deps")
    for tier in tiers:
        command += ["-e", tier]

    print(f"[dev_install]   run        : {' '.join(command)}\n")
    returncode = subprocess.run(command).returncode
    if returncode != 0:
        print(f"\n[dev_install] ERROR: pip exited {returncode}", file=sys.stderr)
        return returncode

    print()
    return _report_discoverable_tiers(python)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev_install",
        description=(
            "Editable-install SimReady tiers so simready-validate loads them from "
            "this checkout via the normal simready.tier entry point. Needs only "
            "Python and pip -- no uv and no repoman. Re-run after adding or "
            "removing a requirement page, since requirement enums are generated "
            "at install time."
        ),
    )
    parser.add_argument(
        "--tier",
        action="append",
        default=[],
        dest="names",
        metavar="NAME",
        help="Tier directory name to install. Repeatable. Defaults to every tier found.",
    )
    parser.add_argument(
        "--python",
        metavar="PATH",
        help="Interpreter to install into. Defaults to the one running this script.",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Pass --no-deps to pip (keeps an already-installed dependency stack untouched).",
    )
    args = parser.parse_args(argv)

    try:
        return dev_install(names=args.names, python=args.python, no_deps=args.no_deps)
    except DevInstallError as exc:
        print(f"[dev_install] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
