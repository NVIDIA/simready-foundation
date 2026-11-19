# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""SR.002 thumbnail discovery, validation, and normalization.

Two providers share one interface. ``ExistingThumbnailProvider`` ranks
package-local PNGs and normalizes a unique winner, which is what batch and CLI
runs need. ``ExplicitThumbnailProvider`` copies a caller-nominated PNG, which is
what a host application uses when it already knows which image is the
thumbnail. Neither provider renders or fabricates an image.
"""

from __future__ import annotations

import shutil
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Canonical SR.002 directory. A candidate that already lives here is preferred
# over an equally ranked sibling, because it is the location the requirement
# names and the one an existing pipeline most likely wrote on purpose.
CANONICAL_THUMB_DIR = "256x256"

_USD_SUFFIXES = (".usd", ".usda", ".usdc", ".usdz")

STATUS_RETAINED = "retained"
STATUS_SELECTED = "selected"
STATUS_PROVIDED = "provided"
STATUS_MISSING = "missing"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_INVALID = "invalid"


@dataclass(frozen=True)
class ThumbnailCandidate:
    path: Path
    score: int
    reason: str
    preferred: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "score": self.score,
            "reason": self.reason,
            "preferred": self.preferred,
        }


@dataclass(frozen=True)
class ThumbnailResult:
    status: str
    target: Path
    candidates: tuple[ThumbnailCandidate, ...]
    selected: Path | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {STATUS_RETAINED, STATUS_SELECTED, STATUS_PROVIDED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "target": str(self.target),
            "selected": str(self.selected) if self.selected else None,
            "reason": self.reason,
            "candidates": [item.to_dict() for item in self.candidates],
        }


def is_valid_png(path: Path) -> bool:
    """Verify PNG signature, chunk CRCs, and a non-degenerate IHDR."""
    try:
        data = Path(path).read_bytes()
        if not data.startswith(PNG_SIGNATURE):
            return False
        offset = len(PNG_SIGNATURE)
        saw_header = False
        while offset + 12 <= len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            chunk_type = data[offset + 4 : offset + 8]
            end = offset + 12 + length
            if end > len(data):
                return False
            payload = data[offset + 8 : offset + 8 + length]
            expected_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
            if zlib.crc32(chunk_type + payload) & 0xFFFFFFFF != expected_crc:
                return False
            if chunk_type == b"IHDR":
                if saw_header or length != 13:
                    return False
                width, height = struct.unpack(">II", payload[:8])
                if width == 0 or height == 0:
                    return False
                saw_header = True
            if chunk_type == b"IEND":
                return saw_header and end == len(data)
            offset = end
        return False
    except (OSError, struct.error):
        return False


def target_path(asset_path: Path) -> Path:
    """Return the exact SR.002 thumbnail path for a root USD."""
    asset = Path(asset_path)
    return asset.parent / ".thumbs" / CANONICAL_THUMB_DIR / f"{asset.name}.png"


def _legacy_suffix_names(asset_name: str, asset_stem: str) -> set[str]:
    """Names that pair the asset stem with a different USD suffix.

    A package is routinely re-rooted between ``.usd`` and ``.usda`` after
    authoring, which leaves a thumbnail named for the old suffix. For example a
    Blender export writes ``sm_prop_01.usd.png`` and the Isaac interface layer
    that later replaces it is ``sm_prop_01.usda``. That PNG is still the asset's
    thumbnail, so it is recognized rather than demoted to a generic package PNG.
    """
    names = {f"{asset_stem}{suffix}.png".casefold() for suffix in _USD_SUFFIXES}
    names.discard(f"{asset_name}.png".casefold())
    return names


def discover_candidates(
    asset_path: Path, package_root: Path | None = None
) -> tuple[ThumbnailCandidate, ...]:
    """Rank every valid package-local PNG as an SR.002 thumbnail candidate."""
    asset = Path(asset_path).resolve()
    package = Path(package_root).resolve() if package_root else asset.parent.parent
    target = target_path(asset)
    legacy_names = _legacy_suffix_names(asset.name, asset.stem)
    candidates = []
    for path in package.rglob("*.png"):
        if not is_valid_png(path):
            continue
        parts = {part.casefold() for part in path.parts}
        thumbnail_directory = ".thumbs" in parts
        beside_asset = path.parent.resolve() == asset.parent.resolve()
        name = path.name.casefold()
        if path.resolve() == target.resolve():
            score, reason = 1000, "exact SR.002 target"
        elif not thumbnail_directory and not beside_asset:
            score, reason = 100, "package PNG"
        elif name == f"{asset.name}.png".casefold():
            score, reason = 900, "exact asset filename"
        elif name in legacy_names:
            score, reason = 850, "asset stem with alternate USD suffix"
        elif name == f"{asset.stem}.png".casefold():
            score, reason = 800, "legacy asset stem"
        elif thumbnail_directory:
            score, reason = 500, "package thumbnail directory"
        else:
            score, reason = 100, "package PNG"
        candidates.append(
            ThumbnailCandidate(
                path.resolve(),
                score,
                reason,
                preferred=CANONICAL_THUMB_DIR.casefold() in parts,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (-item.score, not item.preferred, str(item.path)),
        )
    )


def _copy_to_target(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # A staged package shares non-USD payload with its source through hardlinks,
    # so writing through an existing target would change the source file's
    # bytes. Unlinking first breaks the link instead of writing through it.
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(source, target)


class ThumbnailProvider(Protocol):
    def provide(self, asset_path: Path) -> ThumbnailResult: ...


class ExistingThumbnailProvider:
    """Retain or normalize a unique valid package-local thumbnail."""

    def __init__(self, package_root: Path | None = None) -> None:
        self._package_root = package_root

    def provide(self, asset_path: Path) -> ThumbnailResult:
        target = target_path(asset_path)
        candidates = discover_candidates(asset_path, self._package_root)
        if candidates and candidates[0].path == target.resolve():
            return ThumbnailResult(
                STATUS_RETAINED, target, candidates, target, "exact SR.002 target"
            )
        if not candidates:
            return ThumbnailResult(
                STATUS_MISSING, target, candidates, reason="no valid package PNG"
            )
        best_score = candidates[0].score
        best = tuple(item for item in candidates if item.score == best_score)
        if best_score <= 100:
            return ThumbnailResult(
                STATUS_MISSING,
                target,
                candidates,
                reason="no recognized thumbnail naming or location",
            )
        if len(best) != 1:
            # Equal scores are broken by the canonical 256x256 location before
            # giving up, so a package carrying both a full-res thumbnail and its
            # own 256x256 copy resolves instead of blocking.
            preferred = tuple(item for item in best if item.preferred)
            if len(preferred) != 1:
                return ThumbnailResult(
                    STATUS_AMBIGUOUS,
                    target,
                    candidates,
                    reason="multiple equally ranked candidates",
                )
            best = preferred
        _copy_to_target(best[0].path, target)
        return ThumbnailResult(
            STATUS_SELECTED, target, candidates, best[0].path, best[0].reason
        )


class ExplicitThumbnailProvider:
    """Copy one caller-nominated PNG onto the exact SR.002 target.

    A host application that just rendered or already owns the thumbnail knows
    which file it is, so it should not be re-derived from filename heuristics.
    The PNG is still validated, and an unreadable or invalid file is a blocker
    rather than a silent fallback to discovery.
    """

    def __init__(self, source: Path) -> None:
        self._source = Path(source)

    def provide(self, asset_path: Path) -> ThumbnailResult:
        target = target_path(asset_path)
        source = self._source.expanduser()
        if not source.is_file():
            return ThumbnailResult(
                STATUS_MISSING,
                target,
                (),
                reason=f"thumbnail_source not found: {source}",
            )
        if not is_valid_png(source):
            return ThumbnailResult(
                STATUS_INVALID,
                target,
                (),
                reason=f"thumbnail_source is not a valid PNG: {source}",
            )
        source = source.resolve()
        candidate = ThumbnailCandidate(source, 1000, "caller-provided", preferred=True)
        if source == target.resolve():
            return ThumbnailResult(
                STATUS_RETAINED, target, (candidate,), target, "exact SR.002 target"
            )
        _copy_to_target(source, target)
        return ThumbnailResult(
            STATUS_PROVIDED, target, (candidate,), source, "caller-provided"
        )


def normalize_thumbnail(
    asset_path: Path,
    *,
    thumbnail_source: Path | None = None,
    package_root: Path | None = None,
) -> ThumbnailResult:
    """Normalize the SR.002 thumbnail, preferring an explicit source."""
    provider: ThumbnailProvider = (
        ExplicitThumbnailProvider(thumbnail_source)
        if thumbnail_source is not None
        else ExistingThumbnailProvider(package_root)
    )
    return provider.provide(asset_path)
