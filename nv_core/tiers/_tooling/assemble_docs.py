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
tier under ``nv_core/tiers/`` owns its own ``rules_and_reqs``/``capabilities``/
``features``/``profiles`` content and may declare additional mappings in
``docs-sources.json``. Cross-tier site content lives in a committed *shared
overlay* (``nv_core/sr_specs/docs/shared/``), and the remaining site chrome
(``index.md``, ``guides/``, ``indexes/``, ``_static/`` ...) stays in
``nv_core/sr_specs/docs/``.

This module stitches those sources back into one Sphinx source tree at
``nv_core/sr_specs/_build/docs-src`` on every run, preserving the *logical*
docnames (``rules_and_reqs/**``, ``capabilities/**``, ``features/**``,
``profiles/**``) that the
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

Relative links, images, and include paths in the markdown sources are written
relative to the source file in the repository, so they work when the markdown
is browsed directly. The assembler repoints each one at the assembled layout: a
link to another published file becomes the path between the two logical
locations, and a link to any other repository file (``sample_content`` assets,
``changelist.md``) is recomputed from the staged location.
``check_doc_links.py`` enforces that every such link resolves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote

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

#: The logical section roots owned by tiers + the shared overlay.
SECTION_ROOTS: Tuple[str, ...] = ("rules_and_reqs", "capabilities", "features", "profiles")

#: Directory/file names never copied from any source (build scratch, caches,
#: and non-documentation records that live beside content).
#:
#: ``known_edits`` holds provenance records for edits to published feature
#: versions. They sit inside a tier's ``features/`` directory, so copying them
#: puts a non-descriptor TOML where the docs spec parser reads every file as a
#: feature descriptor, and the build dies on the missing ``id`` key. Excluded
#: here rather than through ``exclude_logical`` because it is never
#: documentation in any tier, not a subtree a hub happens not to link.
#: Matched by exact basename.
_ALWAYS_IGNORE_NAMES = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", ".DS_Store", "known_edits"}
)
#: Python is never documentation: tiers ship validators beside their docs, and a
#: tier contributing requirements to another tier's capability ships its own
#: ``validation.py`` at the same logical path, a (meaningless) divergent
#: duplicate. A stray ``conf.py`` is never trusted either.
_IGNORE_SUFFIXES = (".py", ".pyc", ".pyo")

#: Top-level entries under the site docs root that are NOT residual site chrome:
#: they are reproduced from the tiers + shared overlay.
_RESIDUAL_EXCLUDE_NAMES = frozenset(
    {
        SHARED_OVERLAY_DIRNAME,
        "rules_and_reqs",
        "capabilities",
        "features",
        "profiles",
        "_build",
    }
)

#: Logical-path prefixes (POSIX, relative to the output root) to drop entirely.
#: Nothing is excluded by default; pass ``exclude_logical`` to quarantine a
#: subtree that a hub page does not link, which would otherwise assemble into an
#: orphan page.
DEFAULT_EXCLUDE_LOGICAL: Tuple[str, ...] = ()

#: Tier catalog mapping file produced by Foundations 2 relocation.
TIER_CATALOG_MAP_FILENAME = "catalog-map.json"

#: Published June 2026 (v2026.06.0) feature page stems under ``features/`` and
#: the ordered Foundations 1 contract page stems they were split/renamed into
#: in August 2026 (v2026.08.0). The first target in each tuple is the primary
#: neutral/default replacement route; any remaining entries are split runtime
#: variants. When assembling a Foundations 2 relocated tree, each Foundations 1
#: stem is resolved further through the tier's ``catalog-map.json``.
LEGACY_JUNE_FEATURE_ROUTES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "FET_000-base_neutral-0.1.0-core",
        ("FET_000_STANDARD", "FET_000_PHYSX", "FET_000_NEWTON", "FET_000_MUJOCO", "FET_000_ISAAC"),
    ),
    ("FET_001-minimal", ("FET_001_STANDARD",)),
    ("FET_002-posable_bodies", ("FET_002_STANDARD",)),
    (
        "FET_003-rigid_body_physics",
        ("FET_003_STANDARD", "FET_003_PHYSX", "FET_003_NEWTON", "FET_003_MUJOCO"),
    ),
    (
        "FET_004-simulate_multi_body_physics",
        (
            "FET_004_STANDARD",
            "FET_004_PHYSX",
            "FET_004_NEWTON",
            "FET_004_MUJOCO",
            "FET_004_ROBOT_PHYSX",
            "FET_004_ROBOT_NEWTON",
            "FET_004_ROBOT_MUJOCO",
        ),
    ),
    ("FET_005-simulate_grasp_physics", ("FET_005_STANDARD",)),
    ("FET_006-materials", ("FET_006_STANDARD", "FET_006_MDL", "FET_006_OPENPBR")),
    ("FET_007-nonvisual_materials", ("FET_007_STANDARD",)),
    ("FET_011-semantic_labels", ("FET_011_STANDARD", "FET_011_RTX")),
    ("FET_021-robot_core", ("FET_021_ISAAC",)),
    (
        "FET_022-driven_joints",
        ("FET_022_STANDARD", "FET_022_PHYSX", "FET_022_NEWTON", "FET_022_MUJOCO", "FET_022_ISAAC"),
    ),
    ("FET_023-robot_materials", ("FET_023_ISAAC",)),
    (
        "FET_024-base_articulation",
        ("FET_024_STANDARD", "FET_024_PHYSX", "FET_024_NEWTON", "FET_024_MUJOCO"),
    ),
    ("FET_030-packaging_core", ("FET_030_STANDARD",)),
    ("FET_031-package_self_contained", ("FET_031_STANDARD",)),
    ("FET_032-packaging_introspection", ("FET_032_STANDARD",)),
    ("FET_033-simready_packaging", ("FET_033_STANDARD",)),
    ("FET_100-isaacsim-0.1.0-composition", ("FET_100_ISAAC",)),
)


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


def _tier_doc_manifest(tier_dir: Path) -> Optional[Tuple[Path, dict]]:
    """Return ``(manifest_path, payload)`` for ``tier_dir``'s docs-source manifest, if any."""
    manifest_path = tier_dir / TIER_DOC_SOURCES_FILENAME
    if not manifest_path.exists():
        return None
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
    return manifest_path, payload


def tier_doc_sources(tier_dir: Path) -> List[Tuple[Path, str, str]]:
    """Load validated custom documentation mappings declared by ``tier_dir``.

    The optional ``docs-sources.json`` contract is::

        {
          "schema_version": 1,
          "sources": [
            {"path": "package/docs", "destination": "guides/package"}
          ],
          "exclude": [
            "simready/foundation/<module>/rules_and_reqs/<capability>/requirements.md"
          ]
        }

    Source paths must resolve inside the declaring tier. Destinations are
    logical POSIX paths relative to the assembled Sphinx root. ``exclude`` is
    read by :func:`tier_doc_excludes`.
    """
    tier_dir = Path(tier_dir).resolve()
    loaded = _tier_doc_manifest(tier_dir)
    if loaded is None:
        return []
    manifest_path, payload = loaded
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


def tier_doc_excludes(tier_dir: Path) -> FrozenSet[Path]:
    """Return the tier files that ``docs-sources.json`` keeps out of the docs tree.

    ``exclude`` lists exact tier-relative file paths. It is for files a tier needs
    for something other than its docs, such as a capability page that drives
    requirement codegen for a capability another tier documents. Matching is by
    source file, so another tier's file at the same logical path still assembles.
    """
    tier_dir = Path(tier_dir).resolve()
    loaded = _tier_doc_manifest(tier_dir)
    if loaded is None:
        return frozenset()
    manifest_path, payload = loaded
    raw_excludes = payload.get("exclude", [])
    if not isinstance(raw_excludes, list):
        raise AssembleError(f"{manifest_path}: 'exclude' must be a list")

    excludes = set()
    for index, raw in enumerate(raw_excludes):
        exclude_rel = _validate_manifest_relative_path(raw, f"exclude[{index}]", manifest_path)
        exclude_path = (tier_dir / exclude_rel).resolve()
        try:
            exclude_path.relative_to(tier_dir)
        except ValueError as exc:
            raise AssembleError(f"{manifest_path}: exclude escapes tier root: {exclude_rel!r}") from exc
        if not exclude_path.is_file():
            raise AssembleError(f"{manifest_path}: excluded path is not a file: {exclude_rel!r}")
        excludes.add(exclude_path)
    return frozenset(excludes)


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


def _check_owned_output(output_root: Path) -> Optional[Path]:
    """Validate that an existing ``output_root`` is owned and link-free before mutation."""
    if not output_root.exists():
        return None
    if _is_link_or_reparse(output_root) or not output_root.is_dir():
        raise AssembleError(f"Documentation output must be a regular directory: {output_root}")
    marker = _validate_ownership_marker(output_root)
    _assert_owned_tree_has_no_links(output_root, marker)
    return marker


def _prepare_owned_output(output_root: Path) -> None:
    """Create a marked output or clean only a previously marked output tree."""
    marker = _check_owned_output(output_root)
    if marker is not None:
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
    package; that package directory is where ``rules_and_reqs``/``capabilities``/
    ``features``/``profiles`` live.
    """
    foundation = tier_dir / "simready" / "foundation"
    if not foundation.is_dir():
        return None
    # Caches must be filtered, not counted. A tier that ships modules directly
    # under ``simready/foundation`` gets a ``__pycache__`` sibling there the
    # first time anything imports them, and counting it makes this return None
    # and silently drop the tier's entire documentation.
    module_dirs = sorted(p for p in foundation.iterdir() if p.is_dir() and p.name not in _ALWAYS_IGNORE_NAMES)
    if len(module_dirs) != 1:
        return None
    return module_dirs[0]


# ---------------------------------------------------------------------------
# Markdown path references.
# ---------------------------------------------------------------------------
# Inline links / images:  [text](url)  or  ![alt](<url> "title")
_INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>\n]*>|[^)\s]+)")
# Reference-style link definitions:  [label]: url  (not footnotes, ``[^1]:``)
_REF_DEF_RE = re.compile(r"^[ \t]*\[(?!\^)[^\]]+\]:[ \t]+(<[^>\n]*>|\S+)", re.MULTILINE)
# Code, colon, and directive fences:  ```usda  /  ````{note}  /  :::{figure} path
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,}|:{3,})[ \t]*(.*?)[ \t]*$")
_DIRECTIVE_RE = re.compile(r"\{([\w-]+)\}[ \t]*(\S*)")
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

#: Directives whose argument is a path relative to the document.
_PATH_ARG_DIRECTIVES = frozenset({"include", "literalinclude", "figure", "image"})
#: Directives whose body is not markdown, so it holds no links.
_VERBATIM_BODY_DIRECTIVES = frozenset(
    {"code", "code-block", "sourcecode", "literalinclude", "include", "raw", "mermaid", "eval-rst", "math", "toctree"}
)


def _blank(text: str) -> str:
    return re.sub(r"[^\r\n]", " ", text)


def _mask_non_links(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """Blank out code and comments and return the spans of path directive arguments.

    The masked text has the same length as ``text``, so link offsets found in
    it index ``text`` directly.
    """
    lines: List[str] = []
    directive_args: List[Tuple[int, int]] = []
    # Open fences, innermost last: (fence character, fence length, body is verbatim).
    fences: List[Tuple[str, int, bool]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        fence = _FENCE_RE.match(line.rstrip("\r\n"))
        closes = (
            fence is not None
            and bool(fences)
            and fence.group(1)[0] == fences[-1][0]
            and len(fence.group(1)) >= fences[-1][1]
            and not fence.group(2)
        )
        if closes:
            fences.pop()
            lines.append(_blank(line))
        elif fences and fences[-1][2]:
            lines.append(_blank(line))
        elif fence is not None and (fence.group(1)[0] != ":" or fence.group(2).startswith("{")):
            directive = _DIRECTIVE_RE.match(fence.group(2))
            name = directive.group(1) if directive else None
            if name in _PATH_ARG_DIRECTIVES and directive.group(2):
                start = offset + fence.start(2) + directive.start(2)
                directive_args.append((start, start + len(directive.group(2))))
            fences.append((fence.group(1)[0], len(fence.group(1)), name is None or name in _VERBATIM_BODY_DIRECTIVES))
            lines.append(_blank(line))
        else:
            lines.append(_INLINE_CODE_RE.sub(lambda m: _blank(m.group()), line))
        offset += len(line)
    masked = _HTML_COMMENT_RE.sub(lambda m: _blank(m.group()), "".join(lines))
    return masked, directive_args


def iter_path_refs(text: str) -> List[Tuple[int, int, str]]:
    """Return ``(start, end, kind)`` for every link target in a markdown document.

    ``kind`` is ``"link"`` for inline links, images, and reference definitions,
    and ``"directive"`` for the path argument of an include-like directive.
    Targets inside code blocks, inline code, and HTML comments are skipped.
    Angle brackets around a target are not part of its span.
    """
    masked, directive_args = _mask_non_links(text)
    refs = [(start, end, "directive") for start, end in directive_args]
    for pattern in (_INLINE_LINK_RE, _REF_DEF_RE):
        for match in pattern.finditer(masked):
            start, end = match.span(1)
            if text[start] == "<":
                start, end = start + 1, end - 1
            refs.append((start, end, "link"))
    return sorted(refs)


def split_ref(url: str) -> Tuple[Optional[str], str]:
    """Split a link target into ``(path, "#fragment" or "?query")``.

    The path is None for targets that are not file paths: URLs, same-page
    anchors, and MyST substitutions.
    """
    if not url or url.startswith(("#", "{")) or url.startswith("//") or _URL_SCHEME_RE.match(url):
        return None, url
    cut = min((index for index in (url.find("#"), url.find("?")) if index != -1), default=len(url))
    if cut == 0:
        return None, url
    return url[:cut], url[cut:]


def source_key(path: "os.PathLike[str] | str") -> str:
    """Normalize a source path for lookups in :meth:`_Assembler.published`."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def rewrite_links(text: str, source: Path, logical_rel: str, published: Dict[str, str], output_root: Path) -> str:
    """Repoint the relative links of one markdown source at the assembled tree.

    Links are written relative to ``source`` in the repository. A link to a
    published file becomes the relative path between the two logical locations;
    a link to any other existing file is recomputed from the document's staged
    location under ``output_root``. Links that do not resolve to a file are left
    as written, for the link check to report.
    """
    logical_dir = posixpath.dirname(logical_rel) or "."
    staged_dir = output_root / logical_dir
    pieces: List[str] = []
    last = 0
    for start, end, _kind in iter_path_refs(text):
        path, suffix = split_ref(text[start:end])
        if path is None or path.startswith("/"):
            continue
        target = os.path.normpath(source.parent / unquote(path))
        logical = published.get(source_key(target))
        if logical is not None:
            new_path = posixpath.relpath(logical, logical_dir)
        elif os.path.isfile(target):
            new_path = Path(os.path.relpath(target, staged_dir)).as_posix()
        else:
            continue
        pieces += [text[last:start], new_path + suffix]
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


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
        # logical POSIX path -> file bytes (flushed only after all checks pass)
        self.staged_bytes: Dict[str, bytes] = {}
        self.skipped_excluded: List[str] = []
        # (logical POSIX path, source file, source label), in assembly order
        self.entries: List[Tuple[str, Path, str]] = []
        # Foundations 1 page stem -> relocated logical page, from catalog-map.json
        self.legacy_pages: Dict[str, str] = {}

    def _is_excluded(self, logical: str) -> bool:
        for prefix in self.exclude_logical:
            if logical == prefix or logical.startswith(prefix + "/"):
                return True
        return False

    def _place(self, logical: str, data: bytes, source_label: str) -> None:
        """Stage ``data`` for ``output_root/logical``, guarding duplicates."""
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
        self.staged_bytes[logical] = data
        self.registry[logical] = (source_label, sha)
        self.manifest[logical] = {"source": source_label, "sha256": sha}

    def flush(self) -> None:
        """Write all validated staged files into ``output_root``."""
        for logical in sorted(self.staged_bytes):
            dest = self.output_root / logical
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(self.staged_bytes[logical])

    def add_file(self, logical: str, source: Path, source_label: str) -> None:
        """Register ``source`` for ``output_root/logical``; :meth:`stage` copies it."""
        if self._is_excluded(logical):
            self.skipped_excluded.append(logical)
            return
        self.entries.append((logical, source, source_label))

    def add_source(
        self, src_root: Path, dest_prefix: str, source_label: str, skip: FrozenSet[Path] = frozenset()
    ) -> None:
        """Register every file under ``src_root`` for ``output_root/dest_prefix``.

        Files in ``skip`` (resolved absolute paths) are not registered.
        """
        for rel, abspath in _iter_files(src_root):
            if abspath.resolve() in skip:
                continue
            logical = f"{dest_prefix}/{rel}" if dest_prefix else rel
            self.add_file(Path(logical).as_posix(), abspath, source_label)

    def published(self) -> Dict[str, str]:
        """Map each registered source file (:func:`source_key`) to its logical path."""
        return {source_key(source): logical for logical, source, _ in self.entries}

    def markdown_entries(self) -> List[Tuple[str, Path, str]]:
        return [entry for entry in self.entries if entry[1].suffix.lower() == ".md"]

    def stage(self) -> None:
        """Stage every registered file, repointing markdown links at the assembled tree."""
        published = self.published()
        for logical, source, source_label in self.entries:
            data = source.read_bytes()
            if source.suffix.lower() == ".md":
                text = rewrite_links(data.decode("utf-8"), source, logical, published, self.output_root)
                data = text.encode("utf-8")
            self._place(logical, data, source_label)


def _tier_catalog_legacy_pages(module_root: Path) -> Dict[str, str]:
    """Return ``{legacy_page_stem: relocated_logical_md}`` from ``catalog-map.json``."""
    catalog_path = module_root / TIER_CATALOG_MAP_FILENAME
    if not catalog_path.is_file() or _is_link_or_reparse(catalog_path):
        return {}
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssembleError(f"Unable to read tier catalog map {catalog_path}: {exc}") from exc

    contracts = payload.get("contracts") if isinstance(payload, dict) else None
    if not isinstance(contracts, list):
        return {}

    mapping: Dict[str, str] = {}
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        legacy_page = contract.get("legacy_page") or contract.get("legacy_id")
        contract_id = contract.get("id")
        kind = contract.get("kind")
        if (
            not isinstance(legacy_page, str)
            or not legacy_page
            or not isinstance(contract_id, str)
            or "." not in contract_id
            or kind not in ("feature", "capability")
        ):
            continue
        section = "features" if kind == "feature" else "capabilities"
        stem = contract_id.rsplit(".", 1)[0]
        mapping[legacy_page] = f"{section}/{stem}.md"
    return mapping


def _render_compat_stub(legacy_logical: str, resolved_targets: Sequence[Tuple[str, str]]) -> bytes:
    """Render an ``orphan: true`` compatibility redirect page for ``legacy_logical``."""
    legacy_stem = PurePosixPath(legacy_logical).stem
    legacy_dir = PurePosixPath(legacy_logical).parent.as_posix()
    primary_logical, primary_f1 = resolved_targets[0]
    primary_rel_md = Path(os.path.relpath(primary_logical, legacy_dir)).as_posix()
    primary_rel_html = f"{primary_rel_md[: -len('.md')]}.html"
    primary_stem = PurePosixPath(primary_logical).stem

    lines = [
        "---",
        "orphan: true",
        "---",
        "",
        f"# `{legacy_stem}`",
        "",
        "```{raw} html",
        f'<meta http-equiv="refresh" content="0; url={primary_rel_html}" />',
        f'<link rel="canonical" href="{primary_rel_html}" />',
        "```",
        "",
    ]
    if primary_stem != primary_f1:
        lines.append(
            f"This published feature route moved to [`{primary_stem}`]({primary_rel_md}) "
            f"(Foundations 1 ID: `{primary_f1}`)."
        )
    else:
        lines.append(f"This published feature route moved to [`{primary_stem}`]({primary_rel_md}).")

    if len(resolved_targets) > 1:
        lines.extend(["", "Split runtime contracts:", ""])
        for target_logical, f1_stem in resolved_targets:
            rel_md = Path(os.path.relpath(target_logical, legacy_dir)).as_posix()
            stem = PurePosixPath(target_logical).stem
            if stem != f1_stem:
                lines.append(f"- [`{stem}`]({rel_md}) (`{f1_stem}`)")
            else:
                lines.append(f"- [`{stem}`]({rel_md})")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _emit_legacy_feature_routes(asm: "_Assembler", f1_to_f2_pages: Dict[str, str]) -> None:
    """Emit compatibility redirect pages for renamed published feature routes.

    Compatibility stubs are generated only when the legacy logical path is not
    already occupied by an authored page and at least one replacement target
    exists in the assembled tree.
    """
    native_pages = frozenset(asm.registry)

    # (a) Foundations 1 feature routes relocated by Foundations 2 (catalog-map.json).
    for legacy_page, target_logical in sorted(f1_to_f2_pages.items()):
        legacy_logical = f"features/{legacy_page}.md"
        if legacy_logical in asm.registry or target_logical not in native_pages:
            continue
        asm._place(
            legacy_logical,
            _render_compat_stub(legacy_logical, ((target_logical, legacy_page),)),
            "compat:foundations1",
        )

    # (b) June 2026 (v2026.06.0) published feature routes renamed in August 2026.
    for june_stem, f1_stems in LEGACY_JUNE_FEATURE_ROUTES:
        legacy_logical = f"features/{june_stem}.md"
        if legacy_logical in asm.registry:
            continue
        resolved: List[Tuple[str, str]] = []
        seen_targets: set = set()
        for f1_stem in f1_stems:
            f2_target = f1_to_f2_pages.get(f1_stem)
            f1_logical = f"features/{f1_stem}.md"
            if f2_target is not None and f2_target in native_pages:
                target_logical = f2_target
            elif f1_logical in native_pages:
                target_logical = f1_logical
            else:
                continue
            if target_logical not in seen_targets:
                seen_targets.add(target_logical)
                resolved.append((target_logical, f1_stem))
        if resolved:
            asm._place(
                legacy_logical,
                _render_compat_stub(legacy_logical, resolved),
                "compat:2026.06",
            )


def collect_sources(
    site_docs_root: Path = DEFAULT_SITE_DOCS,
    output_root: Path = DEFAULT_OUTPUT,
    tiers_root: Path = _TIERS_ROOT,
    *,
    exclude_logical: Sequence[str] = DEFAULT_EXCLUDE_LOGICAL,
) -> _Assembler:
    """Register every documentation source with its logical path, without staging anything.

    Order of assembly (later divergent collisions are hard errors):

    1. Residual site chrome from ``site_docs_root`` (everything except the
       shared overlay, the tier-owned sections, and plugin scaffolding).
    2. Each discovered tier's ``rules_and_reqs``/``capabilities``/``features``/
       ``profiles`` trees,
       merged onto the matching logical section root.
    3. Additional per-tier documentation trees declared in
       ``docs-sources.json``, mapped onto their declared logical destinations.
    4. The committed shared overlay (``site_docs_root/shared/**``), mapped onto
       the logical section roots.
    """
    site_docs_root = Path(site_docs_root).resolve()
    tiers_root = Path(tiers_root).resolve()
    if not site_docs_root.is_dir():
        raise AssembleError(f"Site docs root not found: {site_docs_root}")

    asm = _Assembler(site_docs_root, Path(output_root), exclude_logical)

    # (1) Residual site chrome: copy each top-level entry that is not excluded.
    for entry in sorted(site_docs_root.iterdir(), key=lambda p: p.name):
        if entry.name in _RESIDUAL_EXCLUDE_NAMES or entry.name in _ALWAYS_IGNORE_NAMES:
            continue
        if entry.is_dir():
            asm.add_source(entry, entry.name, "site")
        elif entry.is_file() and not entry.name.endswith(_IGNORE_SUFFIXES):
            asm.add_file(entry.name, entry, "site")

    # (2) Tier-owned sections, in sorted tier order.
    for tier_dir in discover_tiers(str(tiers_root)):
        tier_dir_path = Path(tier_dir)
        module_root = tier_docs_module_root(tier_dir_path)
        tier_label = f"tier:{tier_dir_path.name}"
        tier_excludes = tier_doc_excludes(tier_dir_path)
        if module_root is not None:
            asm.legacy_pages.update(_tier_catalog_legacy_pages(module_root))
            for section in SECTION_ROOTS:
                section_src = module_root / section
                if section_src.is_dir():
                    asm.add_source(section_src, section, tier_label, tier_excludes)

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
                asm.add_file(entry.name, entry, "shared")
    return asm


def assemble(
    site_docs_root: Path = DEFAULT_SITE_DOCS,
    output_root: Path = DEFAULT_OUTPUT,
    tiers_root: Path = _TIERS_ROOT,
    *,
    manifest_path: Optional[Path] = DEFAULT_MANIFEST,
    exclude_logical: Sequence[str] = DEFAULT_EXCLUDE_LOGICAL,
) -> Dict[str, Dict[str, str]]:
    """Assemble the staged Sphinx source tree and return the file manifest.

    Sources are collected in the order :func:`collect_sources` documents, then
    compatibility redirect pages are added for renamed published feature routes.
    """
    site_docs_root = Path(site_docs_root).resolve()
    output_root_arg = Path(output_root).absolute()
    if _is_link_or_reparse(output_root_arg):
        raise AssembleError(f"Documentation output must not be a link or reparse point: {output_root_arg}")
    output_root = output_root_arg.resolve()
    tiers_root = Path(tiers_root).resolve()

    if not site_docs_root.is_dir():
        raise AssembleError(f"Site docs root not found: {site_docs_root}")

    # Validate any existing output tree before reading sources, but defer
    # cleaning or writing until every source and duplicate check succeeds so a
    # rejected rebuild never leaves a truncated tree beside a prior manifest.
    _check_owned_output(output_root)

    asm = collect_sources(site_docs_root, output_root, tiers_root, exclude_logical=exclude_logical)
    asm.stage()
    _emit_legacy_feature_routes(asm, asm.legacy_pages)

    # Remove any prior manifest before mutating output_root so an interrupted
    # filesystem write cannot leave a stale manifest behind.
    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        if manifest_path.is_file() or manifest_path.is_symlink():
            manifest_path.unlink()

    _prepare_owned_output(output_root)
    asm.flush()

    if manifest_path is not None:
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
