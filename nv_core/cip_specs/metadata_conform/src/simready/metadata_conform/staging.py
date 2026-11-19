# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Staging copy and transactional promotion of a package directory.

Kept separate from the conformance chain so the safety properties are readable
on their own: the source package is never mutated, and a pre-existing
destination is restored when promotion fails.
"""

from __future__ import annotations

import os
import shutil
import stat
import time
import uuid
from pathlib import Path

USD_COPY_SUFFIXES = frozenset({".usd", ".usda", ".usdc", ".usdz"})


class StagingError(OSError):
    """Raised when a staging copy cannot be created."""


def _make_writable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:
        pass


def _link_or_copy(source: Path, dest: Path) -> str:
    try:
        os.link(source, dest)
        return "link"
    except (OSError, NotImplementedError, AttributeError):
        pass
    try:
        os.symlink(source, dest)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        pass
    shutil.copy2(source, dest)
    return "copy"


def copy_package(source: Path, dest: Path) -> None:
    """Stage a mutable working copy of ``source`` at ``dest``.

    USD files are real-copied and made writable so the conformance chain can
    ``Save()`` without touching the source package. Everything else is
    hardlinked when the filesystem allows it, so large textures are not
    duplicated. Never chmod a link: that would flip the source file's mode.
    """
    source = Path(source).resolve()
    dest = Path(dest).resolve()
    if dest.exists():
        raise StagingError(f"Refusing to overwrite existing staging path {dest}")

    dest.mkdir(parents=True)
    _make_writable(dest)

    for src_path in source.rglob("*"):
        rel = src_path.relative_to(source)
        dst_path = dest / rel
        src_lstat = src_path.lstat()

        if stat.S_ISDIR(src_lstat.st_mode):
            dst_path.mkdir(parents=True, exist_ok=True)
            _make_writable(dst_path)
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = src_path.suffix.lower()
        is_symlink = stat.S_ISLNK(src_lstat.st_mode)

        if is_symlink and suffix not in USD_COPY_SUFFIXES:
            os.symlink(os.readlink(src_path), dst_path)
            continue

        if suffix in USD_COPY_SUFFIXES:
            shutil.copy2(src_path, dst_path, follow_symlinks=True)
            _make_writable(dst_path)
            continue

        real_src = src_path.resolve() if is_symlink else src_path
        if _link_or_copy(real_src, dst_path) == "copy":
            _make_writable(dst_path)


def materialize_symlinks(root: Path) -> None:
    """Replace symlinks with real files so the package survives staging cleanup.

    Staged packages share non-USD payload with the source through hardlinks when
    the filesystem allows it, and symlinks otherwise. Hardlinks stay valid after
    the source is removed; symlinks do not, so they are copied before promotion.
    """
    root = Path(root)
    for path in sorted(
        root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        if not path.is_symlink():
            continue
        target = Path(os.path.realpath(path))
        path.unlink()
        if target.is_dir():
            shutil.copytree(target, path)
        else:
            shutil.copy2(target, path)
            _make_writable(path)


def preserve_diagnostics(staging: Path, diagnostics_dir: Path | None) -> str | None:
    """Move failed staging output aside for inspection; return its location."""
    if diagnostics_dir is None:
        return None
    try:
        diagnostics_dir = Path(diagnostics_dir)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        destination = diagnostics_dir / f"failed_{stamp}_{uuid.uuid4().hex[:8]}"
        shutil.move(str(staging), str(destination))
        return str(destination)
    except OSError:
        return None


def restore_backup(backup: Path, output: Path) -> bool:
    try:
        if output.exists():
            shutil.rmtree(output, ignore_errors=True)
        shutil.move(str(backup), str(output))
        return True
    except OSError:
        return False
