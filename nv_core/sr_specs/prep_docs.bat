@echo off
REM SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
REM SPDX-License-Identifier: Apache-2.0
REM
REM Documentation preparation for the internal (repoman) docs build.
REM
REM Replaces the legacy omni.capabilities codegen: (1) installs the Sphinx
REM extension dependency where repo.toml's python_paths expects it and (2)
REM assembles the staged Sphinx source tree (tiers + shared overlay + residual
REM chrome) into _build\docs-src -- the docs_root that ".\repo.bat docs" builds
REM from. Run before ".\repo.bat docs".
pushd "%~dp0"

REM (1) Sphinx extension dependency (provides usd_profiles_nvidia.sphinx.ext).
call "%~dp0repo.bat" uv pip install ^
    --python-version 3.11 ^
    --target _build/usd-profiles-deps ^
    usd-profiles-nvidia==1.16.0
set PREP_RESULT=%ERRORLEVEL%
if not "%PREP_RESULT%"=="0" goto Exit

REM (2) Assemble the staged docs source tree (repoman-free, stdlib-only).
call "%~dp0repo.bat" uv run ^
    --no-project ^
    python ..\tiers\_tooling\assemble_docs.py %*
set PREP_RESULT=%ERRORLEVEL%

:Exit
popd
exit /b %PREP_RESULT%
