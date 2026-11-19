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

"""Tests for the docs link checker (``check_doc_links.py``)."""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLING_DIR))

import assemble_docs as ad  # noqa: E402
import check_doc_links as cdl  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _layout(tmp_path: Path):
    """Return ``(site, tiers, core module root)`` laid out like the repository."""
    site = tmp_path / "nv_core" / "sr_specs" / "docs"
    tiers = tmp_path / "nv_core" / "tiers"
    _write(site / "index.md", "# Home\n")
    _write(site / "guides" / "guides.md", "# Guides\n")
    tier_dir = tiers / "tier_core"
    _write(tier_dir / "pyproject.toml", '[project]\nname = "tier_core"\n')
    core = tier_dir / "simready" / "foundation" / "tier_core"
    _write(core / "rules_and_reqs" / "cap" / "cap.md", "# Cap\n")
    _write(tmp_path / "sample_content" / "a.usda", "#usda 1.0\n")
    return site, tiers, core


def _collect(site: Path, tiers: Path) -> "ad._Assembler":
    return ad.collect_sources(site, tiers_root=tiers, exclude_logical=())


# ---------------------------------------------------------------------------
# Source tree.
# ---------------------------------------------------------------------------
def test_source_links_that_resolve_pass(tmp_path) -> None:
    site, tiers, core = _layout(tmp_path)
    _write(
        core / "features" / "F.md",
        "[cap](../rules_and_reqs/cap/cap.md#x) [guide](../../../../../../sr_specs/docs/guides/guides.md) "
        "[asset](../../../../../../../sample_content/a.usda) [web](https://x.y) [here](#top)\n"
        "```text\n[example](nowhere.md)\n```\n",
    )

    assert cdl.check_source(_collect(site, tiers)) == []


def test_source_reports_unresolved_root_relative_and_unpublished_links(tmp_path) -> None:
    site, tiers, core = _layout(tmp_path)
    _write(tmp_path / "README.md", "# Repo\n")
    page = core / "features" / "F.md"
    _write(
        page,
        "[missing](missing.md)\n[root](/rules_and_reqs/cap/cap.md)\n[readme](../../../../../../../README.md)\n",
    )
    page = page.resolve()

    problems = cdl.check_source(_collect(site, tiers))

    assert problems == [
        f"{page}:1: missing.md: does not resolve from this file",
        f"{page}:2: /rules_and_reqs/cap/cap.md: root-relative path; write it relative to this file",
        f"{page}:3: ../../../../../../../README.md: markdown file is not published in the docs",
    ]


def test_fix_rewrites_assembled_layout_links_and_the_build_keeps_them(tmp_path) -> None:
    site, tiers, core = _layout(tmp_path)
    page = core / "features" / "F.md"
    # Written against the assembled layout; sample_content from the site docs root.
    _write(
        page,
        "[cap](../rules_and_reqs/cap/cap.md) [guide](../guides/guides.md#top) "
        "[asset](../../../../sample_content/a.usda)\n",
    )
    _write(site / "shared" / "features" / "features.md", "[F](F.md)\n")

    assert cdl.check_source(_collect(site, tiers), fix=True) == []

    assert page.read_text(encoding="utf-8") == (
        "[cap](../rules_and_reqs/cap/cap.md) [guide](../../../../../../sr_specs/docs/guides/guides.md#top) "
        "[asset](../../../../../../../sample_content/a.usda)\n"
    )
    assert (site / "shared" / "features" / "features.md").read_text(encoding="utf-8") == (
        "[F](../../../../tiers/tier_core/simready/foundation/tier_core/features/F.md)\n"
    )
    out = tmp_path / "nv_core" / "sr_specs" / "_build" / "docs-src"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert (out / "features" / "F.md").read_text(encoding="utf-8") == (
        "[cap](../rules_and_reqs/cap/cap.md) [guide](../guides/guides.md#top) "
        "[asset](../../../../../sample_content/a.usda)\n"
    )
    assert (out / "features" / "features.md").read_text(encoding="utf-8") == "[F](F.md)\n"


def test_directory_links_are_reported_and_fixed_as_docnames(tmp_path) -> None:
    site, tiers, core = _layout(tmp_path)
    _write(core / "rules_and_reqs" / "cap" / "requirements.md", "# Requirements\n")
    page = core / "rules_and_reqs" / "cap" / "requirements" / "r.md"
    _write(page, "[overview](../requirements)\n")
    page = page.resolve()

    assert cdl.check_source(_collect(site, tiers)) == [
        f"{page}:1: ../requirements: links to a directory; link to a file"
    ]
    assert cdl.check_source(_collect(site, tiers), fix=True) == []
    assert page.read_text(encoding="utf-8") == "[overview](../requirements.md)\n"


def test_fix_resolves_docnames_and_root_relative_links(tmp_path) -> None:
    site, tiers, core = _layout(tmp_path)
    _write(site / "index.md", "[Guides](guides/guides) [Cap](/rules_and_reqs/cap/cap.md)\n")

    assert cdl.check_source(_collect(site, tiers), fix=True) == []

    assert (site / "index.md").read_text(encoding="utf-8") == (
        "[Guides](guides/guides.md) [Cap](../../tiers/tier_core/simready/foundation/tier_core/rules_and_reqs/cap/cap.md)\n"
    )


# ---------------------------------------------------------------------------
# Built HTML.
# ---------------------------------------------------------------------------
def test_html_reports_missing_files_and_fragments(tmp_path) -> None:
    site = tmp_path / "html"
    _write(
        site / "index.html",
        '<html><body><h1 id="top">Home</h1>\n'
        '<a href="guides/guides.html#intro">ok</a> <a href="guides/">dir</a> <a href="#top">self</a>\n'
        '<a href="https://example.com/x">web</a> <img src="_images/a.png">\n'
        '<a href="guides/missing.html">missing</a>\n'
        '<a href="guides/guides.html#nope">bad fragment</a>\n'
        '<a href="../outside.html">outside</a>\n'
        "</body></html>\n",
    )
    _write(site / "guides" / "guides.html", '<html><body><section id="intro"></section></body></html>\n')
    _write(site / "guides" / "index.html", "<html></html>\n")
    _write(site / "_images" / "a.png", "png")
    _write(site / "_static" / "macros.html", "<a href=\"{{ pathto('x') }}\">template</a>\n")

    assert cdl.check_html(site) == [
        "index.html:4: guides/missing.html: file does not exist",
        "index.html:5: guides/guides.html#nope: no element with id 'nope'",
        "index.html:6: ../outside.html: points outside the built site",
    ]


def test_html_follows_meta_refresh_redirects(tmp_path) -> None:
    site = tmp_path / "html"
    _write(site / "old.html", '<meta http-equiv="refresh" content="0; url=new.html" />\n')

    assert cdl.check_html(site) == ["old.html:1: new.html: file does not exist"]


def test_main_exit_codes(tmp_path, capsys) -> None:
    site = tmp_path / "html"
    _write(site / "index.html", '<a href="index.html">self</a>\n')
    assert cdl.main(["html", str(site)]) == 0

    _write(site / "index.html", '<a href="gone.html">gone</a>\n')
    assert cdl.main(["html", str(site)]) == 1
    assert "gone.html: file does not exist" in capsys.readouterr().out
