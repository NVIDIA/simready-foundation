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

"""Check the relative links of the SimReady docs, in source and in built HTML.

``source`` checks every markdown file the docs assembler publishes. Each
relative link, image, and include-like directive path must resolve from the
file's own directory in the repository, the way a file browser or the GitLab
markdown view follows it. The assembler repoints these links at the assembled
layout, so a link that resolves here also resolves in the built site. ``--fix``
rewrites links that are written against the assembled layout instead::

    python nv_core/tiers/_tooling/check_doc_links.py source [--fix]

``html`` checks every local ``href``/``src`` in a built site, including
``#fragment`` targets in HTML pages::

    python nv_core/tiers/_tooling/check_doc_links.py html nv_core/sr_specs/_build/docs

Both modes print one line per broken link and exit 1 when any are found.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assemble_docs as ad  # noqa: E402


# ---------------------------------------------------------------------------
# Source tree.
# ---------------------------------------------------------------------------
def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _closest_source(sources: Sequence[Path], near: Path) -> Path:
    """Pick the source of a duplicated docname that shares the longest path with ``near``."""
    return max(sources, key=lambda candidate: len(os.path.commonpath([candidate, near])))


def _assembled_layout_target(
    path: str,
    kind: str,
    logical_rel: str,
    source: Path,
    asm: "ad._Assembler",
    by_logical: Mapping[str, Sequence[Path]],
) -> Optional[Path]:
    """Return the real file a link written against the assembled layout points at.

    Such a link resolves from the page's assembled location (``/`` meaning the
    assembled root), and a link that leaves the assembled root resolves from the
    page's location under the site docs root. Links may name a page without its
    ``.md`` suffix, the way Sphinx resolves a docname.
    """
    if path.startswith("/"):
        logical = posixpath.normpath(path.lstrip("/"))
    else:
        logical = posixpath.normpath(posixpath.join(posixpath.dirname(logical_rel), path))
    if logical == ".." or logical.startswith("../"):
        target = Path(os.path.normpath(asm.site_docs_root / logical))
        return target if target.exists() else None
    candidates = [logical]
    if kind == "link" and not logical.endswith(".md"):
        candidates.append(logical + ".md")
    for candidate in candidates:
        sources = by_logical.get(candidate)
        if sources:
            return _closest_source(sources, source)
    return None


def check_source(asm: "ad._Assembler", *, fix: bool = False) -> List[str]:
    """Return one message per relative link that does not resolve in the source tree.

    With ``fix``, links written against the assembled layout are rewritten in
    place to the equivalent source-relative path and are not reported.
    """
    published = asm.published()
    by_logical: Dict[str, List[Path]] = {}
    for logical, source, _label in asm.entries:
        by_logical.setdefault(logical, []).append(source)

    problems: List[str] = []
    for logical, source, _label in asm.markdown_entries():
        with open(source, encoding="utf-8", newline="") as handle:
            text = handle.read()
        edits: List[Tuple[int, int, str]] = []
        for start, end, kind in ad.iter_path_refs(text):
            url = text[start:end]
            path, suffix = ad.split_ref(url)
            if path is None:
                continue
            problem = _source_problem(path, kind, source, published)
            if problem is None:
                continue
            if fix:
                target = _assembled_layout_target(path, kind, logical, source, asm, by_logical)
                if target is not None:
                    new_path = Path(os.path.relpath(target, source.parent)).as_posix()
                    edits.append((start, end, new_path + suffix))
                    continue
            problems.append(f"{source}:{_line_number(text, start)}: {url}: {problem}")
        if edits:
            for start, end, replacement in reversed(edits):
                text = text[:start] + replacement + text[end:]
            with open(source, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
    return problems


def _source_problem(path: str, kind: str, source: Path, published: Mapping[str, str]) -> Optional[str]:
    if path.startswith("/"):
        return "root-relative path; write it relative to this file"
    target = os.path.normpath(source.parent / unquote(path))
    if not os.path.exists(target):
        return "does not resolve from this file"
    if os.path.isdir(target):
        return "links to a directory; link to a file"
    if kind == "link" and target.lower().endswith(".md") and ad.source_key(target) not in published:
        return "markdown file is not published in the docs"
    return None


# ---------------------------------------------------------------------------
# Built HTML.
# ---------------------------------------------------------------------------
#: ``(tag, attribute)`` pairs that reference another file.
_HTML_REF_ATTRS = frozenset(
    {
        ("a", "href"),
        ("link", "href"),
        ("img", "src"),
        ("script", "src"),
        ("source", "src"),
        ("video", "src"),
        ("audio", "src"),
        ("iframe", "src"),
        ("embed", "src"),
    }
)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Set[str] = set()
        self.refs: List[Tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        values = {name: value for name, value in attrs if value is not None}
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "a" and "name" in values:
            self.ids.add(values["name"])
        for name, value in values.items():
            if (tag, name) in _HTML_REF_ATTRS:
                self.refs.append((self.getpos()[0], value))
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            _, _, url = values.get("content", "").partition("url=")
            if url:
                self.refs.append((self.getpos()[0], url.strip()))

    handle_startendtag = handle_starttag


def _parse_page(path: Path) -> _PageParser:
    parser = _PageParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return parser


def check_html(site_root: Path) -> List[str]:
    """Return one message per local link in ``site_root`` whose file or fragment is missing."""
    site_root = Path(site_root).resolve()
    if not site_root.is_dir():
        return [f"{site_root}: built site not found"]
    # One walk up front: a site has thousands of links per page of navigation,
    # and a filesystem query per link is slow on network and WSL mounts.
    files: Set[str] = set()
    dirs: Set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(site_root):
        rel = Path(dirpath).relative_to(site_root).as_posix()
        dirs.add(rel)
        files.update(posixpath.normpath(posixpath.join(rel, name)) for name in filenames)
    # ``_static`` holds theme assets copied verbatim, including Jinja templates.
    pages = {
        rel: _parse_page(site_root / rel)
        for rel in sorted(files)
        if rel.endswith(".html") and "_static" not in rel.split("/")
    }

    problems: List[str] = []
    for page, parsed in pages.items():
        for line, url in parsed.refs:
            problem = _html_problem(url, page, files, dirs, pages)
            if problem is not None:
                problems.append(f"{page}:{line}: {url}: {problem}")
    return problems


def _html_problem(
    url: str, page: str, files: Set[str], dirs: Set[str], pages: Mapping[str, _PageParser]
) -> Optional[str]:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or url.startswith("//"):
        return None
    target = page
    if parts.path:
        if parts.path.startswith("/"):
            return "root-relative path; the site is not served from a fixed root"
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page), unquote(parts.path)))
        if target == ".." or target.startswith("../"):
            return "points outside the built site"
        if target in dirs:
            target = posixpath.normpath(posixpath.join(target, "index.html"))
        if target not in files:
            return "file does not exist"
    fragment = unquote(parts.fragment)
    if fragment and target in pages and fragment not in pages[target].ids:
        return f"no element with id {fragment!r}"
    return None


# ---------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------
def _report(problems: Iterable[str], what: str) -> int:
    problems = list(problems)
    for problem in problems:
        print(problem)
    if problems:
        print(f"[check_doc_links] {len(problems)} broken {what} link(s)", file=sys.stderr)
        return 1
    print(f"[check_doc_links] all {what} links resolve")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="check_doc_links", description=__doc__.split("\n\n")[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    source = modes.add_parser("source", help="Check links in the published markdown sources.")
    source.add_argument("--fix", action="store_true", help="Rewrite assembled-layout links to source-relative ones.")
    html = modes.add_parser("html", help="Check links in a built HTML site.")
    html.add_argument("site", type=Path, help="Built HTML directory (searched recursively).")
    args = parser.parse_args(argv)

    if args.mode == "source":
        try:
            asm = ad.collect_sources()
        except ad.AssembleError as exc:
            print(f"[check_doc_links] ERROR: {exc}", file=sys.stderr)
            return 2
        return _report(check_source(asm, fix=args.fix), "source")
    return _report(check_html(args.site), "HTML")


if __name__ == "__main__":
    sys.exit(main())
