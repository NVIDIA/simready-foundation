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

"""Deterministic documentation assembler for the SimReady tier layout.

The SimReady docs no longer live in a single monolithic tree. Each validation
tier under ``nv_core/tiers/`` owns its own ``capabilities``/``features``/
``profiles`` content and may declare additional mappings in
``docs-sources.json``. Cross-tier site content lives in a committed *shared
overlay* (``nv_core/sr_specs/docs/shared/``), and the remaining site chrome
(``index.md``, ``guides/``, ``indexes/``, ``_static/`` ...) stays in
``nv_core/sr_specs/docs/``.

This module stitches those sources back into one Sphinx source tree at
``nv_core/sr_specs/_build/docs-src`` on every run, preserving the *logical*
docnames (``capabilities/**``, ``features/**``, ``profiles/**``) that the
published site has always used. Both documentation pipelines (the standalone
``build_docs.py`` used for GitHub Pages and the internal ``repo docs`` flow)
point Sphinx at the staged tree rather than at any single source.

Design goals:

* **Deterministic** -- tiers are discovered in sorted order (reusing
  :func:`build_tiers.discover_tiers`), files are walked sorted, and the emitted
  manifest is stable, so repeated runs on the same inputs produce identical
  output.
* **Portable** -- stdlib only, no repoman/Omniverse/``pxr`` dependency, so it
  travels with the tiers source and can be run by third parties::

      python nv_core/tiers/_tooling/assemble_docs.py

* **Safe** -- assembling two *different* files onto the same logical docname is
  a hard error (a divergent duplicate); assembling byte-identical content from
  two sources onto the same path is allowed (idempotent overlap). Existing
  output is cleaned only when an exact ownership marker proves this assembler
  created the directory, and links/reparse points are rejected before cleanup.

Because the staged tree sits one directory deeper than the historical
``docs/`` tree, relative references that *escape* the docs root (e.g.
``changelist.md``'s ``{include} ../../../changelist.md`` or feature pages'
``../../../../sample_content/*.usd`` links) are rewritten so they still resolve
to the same real targets. References that stay inside the tree are untouched,
since the assembled tree mirrors the historical logical structure exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Reuse the repoman-free, sorted tier discovery from the sibling builder so the
# assembler and the wheel builder always agree on what "the tiers" are.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_tiers import discover_tiers  # noqa: E402

# ---------------------------------------------------------------------------
# Layout constants (all derived from this file's location so the module is
# relocatable with the tiers source).
# ---------------------------------------------------------------------------
_TOOLING_DIR = Path(__file__).resolve().parent  # nv_core/tiers/_tooling
_TIERS_ROOT = _TOOLING_DIR.parent  # nv_core/tiers
_NV_CORE = _TIERS_ROOT.parent  # nv_core
_SR_SPECS = _NV_CORE / "sr_specs"  # nv_core/sr_specs

#: Historical site-docs root. Residual site chrome lives here directly; the
#: cross-tier overlay lives in its ``shared/`` subdirectory.
DEFAULT_SITE_DOCS = _SR_SPECS / "docs"
#: Name of the committed cross-tier overlay directory under the site docs root.
SHARED_OVERLAY_DIRNAME = "shared"
#: Where the assembled Sphinx source tree is (re)written on every run.
DEFAULT_OUTPUT = _SR_SPECS / "_build" / "docs-src"
#: Where the diagnostics/parity manifest is written (outside the Sphinx srcdir).
DEFAULT_MANIFEST = _SR_SPECS / "_build" / "docs-src.manifest.json"

#: Optional declarative documentation sources owned by an individual tier.
#: The JSON file lives at the tier root and maps tier-local documentation trees
#: onto stable logical paths in the assembled site. Keeping this declarative
#: avoids teaching the assembler about individual tiers or package names.
TIER_DOC_SOURCES_FILENAME = "docs-sources.json"
TIER_DOC_SOURCES_SCHEMA_VERSION = 1

#: Marker proving that an existing output directory was created and is owned by
#: this assembler. Cleanup is refused when the marker is absent, malformed, or
#: names a different resolved directory.
OUTPUT_OWNERSHIP_MARKER = ".simready-docs-assembler-owned.json"
OUTPUT_OWNERSHIP_SCHEMA_VERSION = 1
_OUTPUT_OWNER = "simready-tier-docs-assembler"

#: The three logical section roots owned by tiers + the shared overlay.
SECTION_ROOTS: Tuple[str, ...] = ("capabilities", "features", "profiles")

#: Directory/file names never copied from any source (build scratch, caches,
#: compiled python, and Python package markers). ``__init__.py`` is validator-
#: registration scaffolding, not documentation: each tier ships its own, so
#: merging them onto one logical ``capabilities/__init__.py`` would be a
#: (meaningless) divergent duplicate. A Sphinx source tree never needs it.
#: Matched by exact basename.
_ALWAYS_IGNORE_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".git", ".DS_Store", "__init__.py"})
_IGNORE_SUFFIXES = (".pyc", ".pyo")

#: Top-level entries under the site docs root that are NOT residual site chrome:
#: they are reproduced from the tiers + shared overlay, or are validator-plugin
#: scaffolding that has no place in a Sphinx source tree.
_RESIDUAL_EXCLUDE_NAMES = frozenset(
    {
        SHARED_OVERLAY_DIRNAME,
        "capabilities",
        "features",
        "profiles",
        "__init__.py",
        "__main__.py",
        "_plugin.py",
        "_build",
        "conf.py",  # never trust a stray generated conf in the source tree
    }
)

#: Logical-path prefixes (POSIX, relative to the output root) to drop entirely.
#: Nothing is excluded by default; pass ``exclude_logical`` to quarantine a
#: subtree that a hub page does not link, which would otherwise assemble into an
#: orphan page.
DEFAULT_EXCLUDE_LOGICAL: Tuple[str, ...] = ()


class AssembleError(RuntimeError):
    """Raised for unrecoverable assembly problems (e.g. divergent duplicates)."""


def _validate_manifest_relative_path(value: object, field: str, manifest_path: Path) -> str:
    """Return a normalized, safe POSIX-relative path from a tier manifest."""
    if not isinstance(value, str) or not value.strip():
        raise AssembleError(f"{manifest_path}: '{field}' must be a non-empty string")
    value = value.strip()
    if "\\" in value or "\x00" in value:
        raise AssembleError(f"{manifest_path}: '{field}' must use a safe POSIX-relative path: {value!r}")

    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ":" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise AssembleError(f"{manifest_path}: '{field}' must not be absolute or contain traversal: {value!r}")
    return posix.as_posix()


def tier_doc_sources(tier_dir: Path) -> List[Tuple[Path, str, str]]:
    """Load validated custom documentation mappings declared by ``tier_dir``.

    The optional ``docs-sources.json`` contract is::

        {
          "schema_version": 1,
          "sources": [
            {"path": "package/docs", "destination": "guides/package"}
          ]
        }

    Source paths must resolve inside the declaring tier. Destinations are
    logical POSIX paths relative to the assembled Sphinx root.
    """
    tier_dir = Path(tier_dir).resolve()
    manifest_path = tier_dir / TIER_DOC_SOURCES_FILENAME
    if not manifest_path.exists():
        return []
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise AssembleError(f"Tier docs-source manifest must be a regular file: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssembleError(f"Unable to read tier docs-source manifest {manifest_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise AssembleError(f"{manifest_path}: top-level value must be an object")
    if payload.get("schema_version") != TIER_DOC_SOURCES_SCHEMA_VERSION:
        raise AssembleError(
            f"{manifest_path}: unsupported schema_version {payload.get('schema_version')!r}; "
            f"expected {TIER_DOC_SOURCES_SCHEMA_VERSION}"
        )
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise AssembleError(f"{manifest_path}: 'sources' must be a list")

    mappings: List[Tuple[Path, str, str]] = []
    seen: set = set()
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict) or set(raw) != {"path", "destination"}:
            raise AssembleError(f"{manifest_path}: sources[{index}] must contain exactly 'path' and 'destination'")
        source_rel = _validate_manifest_relative_path(raw["path"], f"sources[{index}].path", manifest_path)
        destination = _validate_manifest_relative_path(
            raw["destination"], f"sources[{index}].destination", manifest_path
        )
        key = (source_rel, destination)
        if key in seen:
            raise AssembleError(f"{manifest_path}: duplicate docs-source mapping {key!r}")
        seen.add(key)

        source_root = (tier_dir / source_rel).resolve()
        try:
            source_root.relative_to(tier_dir)
        except ValueError as exc:
            raise AssembleError(f"{manifest_path}: source escapes tier root: {source_rel!r}") from exc
        if not source_root.is_dir():
            raise AssembleError(f"{manifest_path}: declared docs source is not a directory: {source_rel!r}")
        mappings.append((source_root, destination, source_rel))
    return mappings


def _is_link_or_reparse(path: Path) -> bool:
    """Return whether ``path`` redirects traversal outside its parent tree."""
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _ownership_marker_payload(output_root: Path) -> Dict[str, object]:
    return {
        "owner": _OUTPUT_OWNER,
        "schema_version": OUTPUT_OWNERSHIP_SCHEMA_VERSION,
        "output_root": str(output_root),
    }


def _write_ownership_marker(output_root: Path) -> None:
    marker = output_root / OUTPUT_OWNERSHIP_MARKER
    payload = _ownership_marker_payload(output_root)
    with open(marker, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _validate_ownership_marker(output_root: Path) -> Path:
    marker = output_root / OUTPUT_OWNERSHIP_MARKER
    if not marker.exists() or _is_link_or_reparse(marker) or not marker.is_file():
        raise AssembleError(
            f"Refusing to clean unowned documentation output directory: {output_root}. "
            f"Expected regular ownership marker {marker.name!r}. Verify the directory, then remove it manually "
            "or choose a new output path."
        )
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssembleError(f"Refusing to clean output with invalid ownership marker {marker}: {exc}") from exc

    expected = _ownership_marker_payload(output_root)
    if payload != expected:
        raise AssembleError(
            f"Refusing to clean output with mismatched ownership marker {marker}; "
            "the marker must identify this exact resolved directory."
        )
    return marker


def _assert_owned_tree_has_no_links(output_root: Path, marker: Path) -> None:
    """Reject links/reparse points before cleanup can traverse the owned tree."""
    pending = [output_root]
    while pending:
        current = pending.pop()
        for child in current.iterdir():
            if child == marker:
                continue
            if _is_link_or_reparse(child):
                raise AssembleError(f"Refusing to clean output containing a link or reparse point: {child}")
            if child.is_dir():
                pending.append(child)


def _prepare_owned_output(output_root: Path) -> None:
    """Create a marked output or clean only a previously marked output tree."""
    if output_root.exists():
        if _is_link_or_reparse(output_root) or not output_root.is_dir():
            raise AssembleError(f"Documentation output must be a regular directory: {output_root}")
        marker = _validate_ownership_marker(output_root)
        _assert_owned_tree_has_no_links(output_root, marker)
        for child in output_root.iterdir():
            if child == marker:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        return

    output_root.mkdir(parents=True, exist_ok=False)
    _write_ownership_marker(output_root)


# ---------------------------------------------------------------------------
# Small filesystem helpers.
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iter_files(root: Path) -> Iterable[Tuple[str, Path]]:
    """Yield ``(relative_posix_path, absolute_path)`` for every file under root.

    Deterministic (sorted) and skips ignored directories/files. ``root`` itself
    is not required to exist; a missing root yields nothing.
    """
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _ALWAYS_IGNORE_NAMES)
        for name in sorted(filenames):
            if name in _ALWAYS_IGNORE_NAMES or name.endswith(_IGNORE_SUFFIXES):
                continue
            abspath = Path(dirpath) / name
            rel = abspath.relative_to(root).as_posix()
            yield rel, abspath


def tier_docs_module_root(tier_dir: Path) -> Optional[Path]:
    """Return ``<tier>/simready/foundation/<module>/`` for a tier dir, or None.

    Each tier commits its content under a single ``simready/foundation/<module>``
    package; that package directory is where ``capabilities``/``features``/
    ``profiles`` live. Build scratch such as ``__pycache__`` is ignored, so a
    tier that has been imported or tested in place still resolves to its one
    module directory.
    """
    foundation = tier_dir / "simready" / "foundation"
    if not foundation.is_dir():
        return None
    module_dirs = sorted(
        p
        for p in foundation.iterdir()
        if p.is_dir() and p.name not in _ALWAYS_IGNORE_NAMES and not p.name.startswith(".")
    )
    if len(module_dirs) != 1:
        return None
    return module_dirs[0]


# ---------------------------------------------------------------------------
# Escaping-reference rewriting.
# ---------------------------------------------------------------------------
# Inline markdown links / images:  [text](url)  or  ![alt](url "title")
_INLINE_LINK_RE = re.compile(r"(!?\[[^\]]*\]\()\s*([^)\s]+)((?:\s+\"[^\"]*\")?\s*\))")
# Reference-style link definitions:  [label]: url
_REF_DEF_RE = re.compile(r"(^[ \t]*\[[^\]]+\]:[ \t]+)(\S+)", re.MULTILINE)
# MyST include-like directives:  ```{include} path   /   :::{literalinclude} path
_INCLUDE_RE = re.compile(r"(\{(?:include|literalinclude|figure|image)\}\s+)(\S+)")

_SKIP_URL_PREFIXES = ("http://", "https://", "ftp://", "mailto:", "tel:", "#", "/", "{", "<", "data:")


def _rewrite_ref(url: str, orig_dir: Path, new_dir: Path, site_docs_root: Path) -> str:
    """Rewrite a single relative reference if it escapes the site docs root.

    ``url`` is resolved against the file's *historical* directory (``orig_dir``,
    i.e. the logical docs location). If the target lies inside ``site_docs_root``
    the reference is returned unchanged (the assembled tree mirrors that
    structure). If it escapes, it is recomputed relative to ``new_dir`` (the
    file's location in the staged tree) so it still points at the same target.
    """
    if not url or url.startswith(_SKIP_URL_PREFIXES) or "://" in url:
        return url
    # Split off a trailing #fragment or ?query so we only touch the path part.
    frag = ""
    for sep in ("#", "?"):
        idx = url.find(sep)
        if idx != -1:
            frag = url[idx:] + frag
            url = url[:idx]
    if not url or url.startswith(_SKIP_URL_PREFIXES):
        return url + frag
    target = Path(os.path.normpath(orig_dir / url))
    site_root = site_docs_root.resolve()
    try:
        target.relative_to(site_root)
        return url + frag  # inside the tree -> structure preserved, leave as-is
    except ValueError:
        pass  # escapes the docs root -> repoint from the new location
    new_ref = os.path.relpath(target, new_dir)
    return Path(new_ref).as_posix() + frag


def rewrite_escaping_refs(text: str, logical_rel: str, site_docs_root: Path, output_root: Path) -> str:
    """Rewrite every escaping relative reference in one markdown document.

    ``logical_rel`` is the document's POSIX path relative to the output root
    (e.g. ``features/FET_003-rigid_body_physics.md``).
    """
    orig_dir = (site_docs_root / logical_rel).parent
    new_dir = (output_root / logical_rel).parent

    def _sub_inline(m: "re.Match[str]") -> str:
        return m.group(1) + _rewrite_ref(m.group(2), orig_dir, new_dir, site_docs_root) + m.group(3)

    def _sub_two(m: "re.Match[str]") -> str:
        return m.group(1) + _rewrite_ref(m.group(2), orig_dir, new_dir, site_docs_root)

    text = _INLINE_LINK_RE.sub(_sub_inline, text)
    text = _REF_DEF_RE.sub(_sub_two, text)
    text = _INCLUDE_RE.sub(_sub_two, text)
    return text


# ---------------------------------------------------------------------------
# Copy engine with divergent-duplicate detection + manifest recording.
# ---------------------------------------------------------------------------
class _Assembler:
    def __init__(self, site_docs_root: Path, output_root: Path, exclude_logical: Sequence[str]):
        self.site_docs_root = site_docs_root
        self.output_root = output_root
        self.exclude_logical = tuple(exclude_logical)
        # logical POSIX path -> (source_label, sha256)
        self.registry: Dict[str, Tuple[str, str]] = {}
        # logical POSIX path -> {"source": label, "sha256": hex}
        self.manifest: Dict[str, Dict[str, str]] = {}
        self.skipped_excluded: List[str] = []

    def _is_excluded(self, logical: str) -> bool:
        for prefix in self.exclude_logical:
            if logical == prefix or logical.startswith(prefix + "/"):
                return True
        return False

    def _place(self, logical: str, data: bytes, source_label: str) -> None:
        """Write ``data`` to ``output_root/logical``, guarding duplicates."""
        if self._is_excluded(logical):
            self.skipped_excluded.append(logical)
            return
        sha = _sha256_bytes(data)
        prior = self.registry.get(logical)
        if prior is not None:
            prior_label, prior_sha = prior
            if prior_sha != sha:
                raise AssembleError(
                    "Divergent duplicate logical path: "
                    f"'{logical}' provided by '{prior_label}' and '{source_label}' "
                    "with differing content. Two sources must not disagree on the "
                    "same docname."
                )
            return  # identical content already placed; idempotent overlap
        dest = self.output_root / logical
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        self.registry[logical] = (source_label, sha)
        self.manifest[logical] = {"source": source_label, "sha256": sha}

    def add_source(self, src_root: Path, dest_prefix: str, source_label: str) -> None:
        """Copy every file under ``src_root`` into ``output_root/dest_prefix``.

        Markdown files have their escaping relative references rewritten for the
        staged location; all other files are copied verbatim.
        """
        for rel, abspath in _iter_files(src_root):
            logical = f"{dest_prefix}/{rel}" if dest_prefix else rel
            logical = Path(logical).as_posix()
            if abspath.suffix.lower() == ".md":
                raw = abspath.read_bytes()
                text = raw.decode("utf-8")
                rewritten = rewrite_escaping_refs(text, logical, self.site_docs_root, self.output_root)
                data = rewritten.encode("utf-8")
            else:
                data = abspath.read_bytes()
            self._place(logical, data, source_label)


def assemble(
    site_docs_root: Path = DEFAULT_SITE_DOCS,
    output_root: Path = DEFAULT_OUTPUT,
    tiers_root: Path = _TIERS_ROOT,
    *,
    manifest_path: Optional[Path] = DEFAULT_MANIFEST,
    exclude_logical: Sequence[str] = DEFAULT_EXCLUDE_LOGICAL,
) -> Dict[str, Dict[str, str]]:
    """Assemble the staged Sphinx source tree and return the file manifest.

    Order of assembly (later divergent collisions are hard errors):

    1. Residual site chrome from ``site_docs_root`` (everything except the
       shared overlay, the three tier-owned sections, and plugin scaffolding).
    2. Each discovered tier's ``capabilities``/``features``/``profiles`` trees,
       merged onto the matching logical section root.
    3. Additional per-tier documentation trees declared in
       ``docs-sources.json``, mapped onto their declared logical destinations.
    4. The committed shared overlay (``site_docs_root/shared/**``), mapped onto
       the logical section roots.
    """
    site_docs_root = Path(site_docs_root).resolve()
    output_root_arg = Path(output_root).absolute()
    if _is_link_or_reparse(output_root_arg):
        raise AssembleError(f"Documentation output must not be a link or reparse point: {output_root_arg}")
    output_root = output_root_arg.resolve()
    tiers_root = Path(tiers_root).resolve()

    if not site_docs_root.is_dir():
        raise AssembleError(f"Site docs root not found: {site_docs_root}")

    # Recreate only a tree carrying this assembler's valid ownership marker.
    # An arbitrary existing directory is never deleted or adopted implicitly.
    _prepare_owned_output(output_root)

    asm = _Assembler(site_docs_root, output_root, exclude_logical)

    # (1) Residual site chrome: copy each top-level entry that is not excluded.
    for entry in sorted(site_docs_root.iterdir(), key=lambda p: p.name):
        if entry.name in _RESIDUAL_EXCLUDE_NAMES or entry.name in _ALWAYS_IGNORE_NAMES:
            continue
        if entry.is_dir():
            asm.add_source(entry, entry.name, "site")
        elif entry.is_file() and not entry.name.endswith(_IGNORE_SUFFIXES):
            data = entry.read_bytes()
            if entry.suffix.lower() == ".md":
                text = data.decode("utf-8")
                data = rewrite_escaping_refs(text, entry.name, site_docs_root, output_root).encode("utf-8")
            asm._place(entry.name, data, "site")

    # (2) Tier-owned sections, in sorted tier order.
    for tier_dir in discover_tiers(str(tiers_root)):
        tier_dir_path = Path(tier_dir)
        module_root = tier_docs_module_root(tier_dir_path)
        if module_root is None:
            print(
                f"[assemble_docs] WARNING: no single simready/foundation/<module> "
                f"directory in {tier_dir_path}; its docs are not staged.",
                file=sys.stderr,
            )
            continue
        tier_label = f"tier:{tier_dir_path.name}"
        if module_root is not None:
            for section in SECTION_ROOTS:
                section_src = module_root / section
                if section_src.is_dir():
                    asm.add_source(section_src, section, tier_label)

        # Additional tier-owned docs are completely declarative. The assembler
        # deliberately has no knowledge of a specific tier or package name.
        for source_root, destination, source_rel in tier_doc_sources(tier_dir_path):
            asm.add_source(source_root, destination, f"{tier_label}:docs:{source_rel}")

    # (4) Shared cross-tier overlay, mapped onto the logical section roots.
    shared_root = site_docs_root / SHARED_OVERLAY_DIRNAME
    if shared_root.is_dir():
        for entry in sorted(shared_root.iterdir(), key=lambda p: p.name):
            if entry.name in _ALWAYS_IGNORE_NAMES:
                continue
            if entry.is_dir():
                asm.add_source(entry, entry.name, "shared")
            elif entry.is_file() and not entry.name.endswith(_IGNORE_SUFFIXES):
                data = entry.read_bytes()
                if entry.suffix.lower() == ".md":
                    text = data.decode("utf-8")
                    data = rewrite_escaping_refs(text, entry.name, site_docs_root, output_root).encode("utf-8")
                asm._place(entry.name, data, "shared")

    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "site_docs_root": str(site_docs_root),
            "output_root": str(output_root),
            "tiers_root": str(tiers_root),
            "excluded_logical_prefixes": list(exclude_logical),
            "excluded_paths": sorted(asm.skipped_excluded),
            "files": {k: asm.manifest[k] for k in sorted(asm.manifest)},
        }
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")

    return dict(asm.manifest)


def docnames(output_root: Path = DEFAULT_OUTPUT) -> List[str]:
    """Return the sorted set of Sphinx docnames (``*.md`` without extension)."""
    output_root = Path(output_root)
    names: List[str] = []
    for rel, _ in _iter_files(output_root):
        if rel.endswith(".md"):
            names.append(rel[: -len(".md")])
    return sorted(names)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="assemble_docs",
        description=(
            "Assemble the SimReady tier docs + shared overlay + residual site "
            "chrome into a single staged Sphinx source tree (repoman-free)."
        ),
    )
    parser.add_argument("--site-docs", default=str(DEFAULT_SITE_DOCS), help="Site docs root (default: %(default)s)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Staged output tree (default: %(default)s)")
    parser.add_argument("--tiers-root", default=str(_TIERS_ROOT), help="Tiers root (default: %(default)s)")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest path (default: %(default)s)")
    parser.add_argument(
        "--exclude-logical",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Logical path prefix to drop from the staged tree; repeatable.",
    )
    args = parser.parse_args(argv)

    exclude = tuple(args.exclude_logical) or DEFAULT_EXCLUDE_LOGICAL
    try:
        manifest = assemble(
            site_docs_root=Path(args.site_docs),
            output_root=Path(args.output),
            tiers_root=Path(args.tiers_root),
            manifest_path=Path(args.manifest),
            exclude_logical=exclude,
        )
    except AssembleError as exc:
        print(f"[assemble_docs] ERROR: {exc}", file=sys.stderr)
        return 2

    md = [k for k in manifest if k.endswith(".md")]
    print("=" * 78)
    print("[assemble_docs] Assembled staged docs tree")
    print(f"[assemble_docs]   output   : {Path(args.output).resolve()}")
    print(f"[assemble_docs]   files    : {len(manifest)} ({len(md)} markdown docnames)")
    print(f"[assemble_docs]   manifest : {Path(args.manifest).resolve()}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
