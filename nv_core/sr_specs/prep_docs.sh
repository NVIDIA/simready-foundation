#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Documentation preparation for the internal (repoman) docs build.
#
# Replaces the legacy omni.capabilities codegen: the docs are no longer a single
# monolithic tree, so this (1) installs the Sphinx extension dependency where
# repo.toml's ``python_paths`` expects it and (2) assembles the staged Sphinx
# source tree (tiers + shared overlay + residual chrome) into
# ``_build/docs-src`` -- the ``docs_root`` that ``./repo.sh docs`` builds from.
#
# Run before ``./repo.sh docs``.
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pushd "$SCRIPT_DIR" > /dev/null

# (1) Sphinx extension dependency (provides usd_profiles_nvidia.sphinx.ext).
./repo.sh uv pip install \
    --python-version 3.11 \
    --target _build/usd-profiles-deps \
    usd-profiles-nvidia==1.16.0

# (2) Assemble the staged docs source tree. The assembler is repoman-free and
#     stdlib-only; it writes to nv_core/sr_specs/_build/docs-src regardless of cwd.
./repo.sh uv run \
    --no-project \
    python ../tiers/_tooling/assemble_docs.py "$@"

popd > /dev/null
