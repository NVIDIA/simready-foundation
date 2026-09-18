# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Build HTML documentation using Sphinx.

Usage:
    python build_docs.py [--strict] [--verbose]

The SimReady docs are assembled on the fly: each validation tier under
``nv_core/tiers/`` owns its capabilities/features/profiles, the shared overlay
holds cross-tier pages, and the remaining site chrome lives in
``nv_core/sr_specs/docs``. This script stages them into
``nv_core/sr_specs/_build/docs-src`` (via ``assemble_docs``), drops the
standalone ``conf.py`` in, and points Sphinx at the staged tree -- while keeping
the published artifact at ``nv_core/sr_specs/docs/_build/html`` where the deploy
job expects it.

Versioned deploys resolve refs with ``scripts/docs_version_refs.py`` and set
``DOCS_VERSION`` for Sphinx (``conf.py``). Release branches map to dotted
versions; preview branches keep the branch name.
"""

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_SR_SPECS = _REPO_ROOT / "nv_core" / "sr_specs"
#: Committed standalone Sphinx config for the public build.
CONF_PY = _SR_SPECS / "docs" / "conf.py"
#: Published HTML artifact location (unchanged; the deploy job copies from here).
DOCS_OUTPUT = _SR_SPECS / "docs" / "_build" / "html"
#: The repoman-free docs assembler shipped with the tiers source.
_ASSEMBLER_PATH = _REPO_ROOT / "nv_core" / "tiers" / "_tooling" / "assemble_docs.py"


def _load_assembler():
    """Load the repoman-free assembler module by file path."""
    spec = importlib.util.spec_from_file_location("simready_assemble_docs", _ASSEMBLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load docs assembler at {_ASSEMBLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_docs() -> Path:
    """Assemble the staged Sphinx source tree and return its path."""
    assembler = _load_assembler()
    assembler.assemble()
    staged = Path(assembler.DEFAULT_OUTPUT)
    # Inject the standalone conf.py (kept out of the assembled tree so the
    # internal repoman build can generate its own).
    shutil.copy2(CONF_PY, staged / "conf.py")
    return staged


def build_docs(strict: bool = False, verbose: bool = False) -> int:
    from sphinx.cmd.build import build_main

    staged = stage_docs()

    args = ["-b", "html", "-j", "auto"]
    if strict:
        args.append("-W")
    if verbose:
        args.append("-v")
    args += [str(staged), str(DOCS_OUTPUT)]

    return build_main(args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Sphinx documentation")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors (-W)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    ret = build_docs(strict=args.strict, verbose=args.verbose)
    sys.exit(ret)


if __name__ == "__main__":
    main()
