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

"""Tests for the deterministic tier docs assembler (``assemble_docs.py``).

These tests build a small synthetic tier + site layout under ``tmp_path`` so
they are fast and independent of repo content.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The assembler lives one directory up (the shared _tooling package). It is
# loaded by file path in production, so make it importable here the same way.
_TOOLING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_TOOLING_DIR))

import assemble_docs as ad  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic-layout helpers.
# ---------------------------------------------------------------------------
def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _make_tier(tiers_root: Path, dir_name: str, module: str) -> Path:
    """Create a minimal discoverable tier and return its content module root."""
    tier_dir = tiers_root / dir_name
    _write(tier_dir / "pyproject.toml", f'[project]\nname = "{dir_name}"\n')
    module_root = tier_dir / "simready" / "foundation" / module
    module_root.mkdir(parents=True, exist_ok=True)
    return module_root


def _make_site(site_root: Path) -> None:
    _write(site_root / "index.md", "# Home\n")
    _write(site_root / "guides" / "guides.md", "# Guides\n")
    # package scaffolding that must never reach the Sphinx tree
    _write(site_root / "__init__.py", "raise RuntimeError('not docs')\n")
    _write(site_root / "_plugin.py", "raise RuntimeError('not docs')\n")


def _write_docs_sources(tier_dir: Path, sources) -> None:
    payload = {"schema_version": 1, "sources": sources}
    _write(tier_dir / ad.TIER_DOC_SOURCES_FILENAME, json.dumps(payload, indent=2) + "\n")


def _docnames(output_root: Path) -> set:
    return set(ad.docnames(output_root))


# ---------------------------------------------------------------------------
# 1. Source mapping.
# ---------------------------------------------------------------------------
def test_source_mapping_merges_tiers_shared_and_residual(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    _make_site(site)

    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "capabilities" / "core" / "core.md", "# Core cap\n")
    _write(core / "features" / "FET_001-minimal.md", "# Minimal\n")
    _write(core / "features" / "FET_001-minimal.json", "{}\n")  # non-doc travels along
    _write(core / "profiles" / "prop-neutral.md", "# Neutral\n")

    isaac = _make_tier(tiers, "tier_isaac", "isaac")
    _write(isaac / "capabilities" / "isaac_sim" / "isaac_sim.md", "# Isaac cap\n")
    _write(isaac / "features" / "FET_100-composition.md", "# Composition\n")

    # shared overlay: hubs mapped onto section roots
    _write(site / "shared" / "capabilities" / "capabilities.md", "# Capabilities hub\n")
    _write(site / "shared" / "features" / "features.md", "# Features hub\n")
    _write(site / "shared" / "profiles" / "profiles.md", "# Profiles hub\n")

    manifest = ad.assemble(site, out, tiers, manifest_path=out.parent / "m.json", exclude_logical=())

    names = _docnames(out)
    assert "index" in names  # residual file
    assert "guides/guides" in names  # residual dir
    assert "capabilities/core/core" in names  # core tier
    assert "capabilities/isaac_sim/isaac_sim" in names  # isaac tier
    assert "features/FET_001-minimal" in names  # core tier narrative
    assert "features/FET_100-composition" in names  # isaac tier narrative
    assert "profiles/prop-neutral" in names  # core tier narrative
    assert "capabilities/capabilities" in names  # shared overlay hub
    assert "features/features" in names  # shared overlay hub
    assert "profiles/profiles" in names  # shared overlay hub

    # non-doc payload travels with the section
    assert (out / "features" / "FET_001-minimal.json").is_file()
    # package scaffolding is dropped
    assert not (out / "__init__.py").exists()
    assert not (out / "_plugin.py").exists()

    # manifest source labels are attributed correctly
    assert manifest["capabilities/core/core.md"]["source"] == "tier:tier_core"
    assert manifest["capabilities/isaac_sim/isaac_sim.md"]["source"] == "tier:tier_isaac"
    assert manifest["capabilities/capabilities.md"]["source"] == "shared"
    assert manifest["index.md"]["source"] == "site"


def test_declarative_tier_docs_source_maps_without_tier_specific_code(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    _make_site(site)

    module_root = _make_tier(tiers, "vendor_tier", "vendor")
    tier_dir = module_root.parents[2]
    _write(tier_dir / "vendor_runtime_suite" / "docs" / "index.md", "# Vendor runtime tests\n")
    _write_docs_sources(
        tier_dir,
        [{"path": "vendor_runtime_suite/docs", "destination": "guides/benchmark/vendor-tests"}],
    )

    manifest = ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    logical = "guides/benchmark/vendor-tests/index.md"
    assert (out / logical).read_text(encoding="utf-8") == "# Vendor runtime tests\n"
    assert manifest[logical]["source"] == "tier:vendor_tier:docs:vendor_runtime_suite/docs"


@pytest.mark.parametrize(
    ("source", "destination", "message"),
    [
        ("../outside", "guides/vendor", "must not be absolute or contain traversal"),
        ("vendor_docs", "../guides/vendor", "must not be absolute or contain traversal"),
        ("C:/outside", "guides/vendor", "must not be absolute or contain traversal"),
        ("C:outside", "guides/vendor", "must not be absolute or contain traversal"),
        ("vendor_docs", "C:/guides/vendor", "must not be absolute or contain traversal"),
        ("vendor_docs", "C:guides/vendor", "must not be absolute or contain traversal"),
        ("vendor_docs\\nested", "guides/vendor", "safe POSIX-relative path"),
    ],
)
def test_declarative_tier_docs_source_rejects_unsafe_paths(tmp_path, source, destination, message):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    module_root = _make_tier(tiers, "vendor_tier", "vendor")
    tier_dir = module_root.parents[2]
    _write(tier_dir / "vendor_docs" / "index.md", "# Vendor docs\n")
    _write_docs_sources(tier_dir, [{"path": source, "destination": destination}])

    with pytest.raises(ad.AssembleError, match=message):
        ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())


def test_declarative_tier_docs_source_rejects_missing_directory(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    module_root = _make_tier(tiers, "vendor_tier", "vendor")
    tier_dir = module_root.parents[2]
    _write_docs_sources(tier_dir, [{"path": "missing", "destination": "guides/vendor"}])

    with pytest.raises(ad.AssembleError, match="declared docs source is not a directory"):
        ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())


# ---------------------------------------------------------------------------
# 2. Deterministic output.
# ---------------------------------------------------------------------------
def test_deterministic_output(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "capabilities" / "a.md", "# A\n")
    _write(core / "features" / "b.md", "# B\n")

    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    m1 = ad.assemble(site, out1, tiers, manifest_path=out1.parent / "m1.json", exclude_logical=())
    m2 = ad.assemble(site, out2, tiers, manifest_path=out2.parent / "m2.json", exclude_logical=())

    # identical logical set + identical content hashes
    assert m1 == m2
    for logical, meta in m1.items():
        assert (out1 / logical).read_bytes() == (out2 / logical).read_bytes()
        assert meta["sha256"] == m2[logical]["sha256"]


def test_reassembly_is_clean(tmp_path):
    """A second run must not leave stale files from a prior, larger run."""
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    stale = core / "capabilities" / "stale.md"
    _write(stale, "# stale\n")
    out = tmp_path / "out"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert (out / "capabilities" / "stale.md").exists()

    stale.unlink()  # remove from source, reassemble
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert not (out / "capabilities" / "stale.md").exists()


def test_existing_unowned_output_is_refused_and_preserved(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    _make_tier(tiers, "tier_core", "core")
    out = tmp_path / "existing-user-directory"
    sentinel = out / "do-not-delete.txt"
    _write(sentinel, "user content\n")

    with pytest.raises(ad.AssembleError, match="Refusing to clean unowned"):
        ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    assert sentinel.read_text(encoding="utf-8") == "user content\n"


def test_invalid_ownership_marker_is_refused_and_preserved(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    _make_tier(tiers, "tier_core", "core")
    out = tmp_path / "existing-user-directory"
    sentinel = out / "do-not-delete.txt"
    _write(sentinel, "user content\n")
    _write(out / ad.OUTPUT_OWNERSHIP_MARKER, '{"owner": "someone-else"}\n')

    with pytest.raises(ad.AssembleError, match="mismatched ownership marker"):
        ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    assert sentinel.read_text(encoding="utf-8") == "user content\n"


def test_copied_ownership_marker_cannot_authorize_another_directory(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    _make_tier(tiers, "tier_core", "core")
    owned = tmp_path / "owned"
    ad.assemble(site, owned, tiers, manifest_path=tmp_path / "m1.json", exclude_logical=())

    other = tmp_path / "other"
    sentinel = other / "do-not-delete.txt"
    _write(sentinel, "user content\n")
    marker_text = (owned / ad.OUTPUT_OWNERSHIP_MARKER).read_text(encoding="utf-8")
    _write(other / ad.OUTPUT_OWNERSHIP_MARKER, marker_text)

    with pytest.raises(ad.AssembleError, match="mismatched ownership marker"):
        ad.assemble(site, other, tiers, manifest_path=tmp_path / "m2.json", exclude_logical=())

    assert sentinel.read_text(encoding="utf-8") == "user content\n"


def test_owned_output_with_symlink_is_refused_without_touching_target(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    _make_tier(tiers, "tier_core", "core")
    out = tmp_path / "owned"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m1.json", exclude_logical=())

    outside = tmp_path / "outside"
    sentinel = outside / "do-not-delete.txt"
    _write(sentinel, "external content\n")
    link = out / "external-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(ad.AssembleError, match="link or reparse point"):
        ad.assemble(site, out, tiers, manifest_path=tmp_path / "m2.json", exclude_logical=())

    assert sentinel.read_text(encoding="utf-8") == "external content\n"
    assert link.is_symlink()


# ---------------------------------------------------------------------------
# 3. Duplicate handling.
# ---------------------------------------------------------------------------
def test_divergent_duplicate_raises(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_a", "a")
    isaac = _make_tier(tiers, "tier_b", "b")
    _write(core / "capabilities" / "dup.md", "# version A\n")
    _write(isaac / "capabilities" / "dup.md", "# version B — different!\n")

    with pytest.raises(ad.AssembleError, match="Divergent duplicate"):
        ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())


def test_identical_duplicate_is_allowed(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_a", "a")
    isaac = _make_tier(tiers, "tier_b", "b")
    _write(core / "capabilities" / "dup.md", "# identical\n")
    _write(isaac / "capabilities" / "dup.md", "# identical\n")

    manifest = ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    # first source wins the attribution; no error
    assert manifest["capabilities/dup.md"]["source"] == "tier:tier_a"


# ---------------------------------------------------------------------------
# 4. Missing sources.
# ---------------------------------------------------------------------------
def test_missing_tier_sections_and_overlay_are_tolerated(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)  # no shared/ overlay at all
    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "capabilities" / "only.md", "# only capability\n")
    # no features/ or profiles/ dirs for this tier

    names = _docnames_after(site, tiers, tmp_path)
    assert "capabilities/only" in names
    assert "index" in names
    assert not any(n.startswith("features/") for n in names)
    assert not any(n.startswith("profiles/") for n in names)


def test_missing_site_docs_root_raises(tmp_path):
    with pytest.raises(ad.AssembleError, match="Site docs root not found"):
        ad.assemble(tmp_path / "nope", tmp_path / "out", tmp_path / "tiers", manifest_path=tmp_path / "m.json")


def _docnames_after(site, tiers, tmp_path):
    out = tmp_path / "out"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    return _docnames(out)


# ---------------------------------------------------------------------------
# 5. Logical-prefix exclusion + __init__ dropping.
# ---------------------------------------------------------------------------
def test_exclude_logical_drops_named_subtree(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    isaac = _make_tier(tiers, "tier_isaac", "isaac")
    _write(isaac / "capabilities" / "physics_bodies" / "quarantined" / "capability-quarantined.md", "# q\n")
    _write(isaac / "capabilities" / "isaac_sim" / "isaac_sim.md", "# isaac\n")

    out = tmp_path / "out"
    ad.assemble(
        site,
        out,
        tiers,
        manifest_path=tmp_path / "m.json",
        exclude_logical=("capabilities/physics_bodies/quarantined",),
    )
    names = _docnames(out)
    assert "capabilities/isaac_sim/isaac_sim" in names
    assert not any("quarantined" in n for n in names)

    # nothing is excluded by default
    out2 = tmp_path / "out2"
    ad.assemble(site, out2, tiers, manifest_path=tmp_path / "m2.json")
    assert any("quarantined" in n for n in _docnames(out2))


def test_init_py_is_dropped(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "capabilities" / "__init__.py", "import something\n")
    _write(core / "capabilities" / "a.md", "# a\n")

    out = tmp_path / "out"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert (out / "capabilities" / "a.md").exists()
    assert not (out / "capabilities" / "__init__.py").exists()


# ---------------------------------------------------------------------------
# 6. Escaping-reference rewriting.
# ---------------------------------------------------------------------------
def test_rewrite_escaping_refs_depth_shift(tmp_path):
    # site docs at .../docs (depth N); output at .../out/staged (depth N+1)
    site = tmp_path / "sr" / "docs"
    out = tmp_path / "sr" / "_build" / "docs-src"
    site.mkdir(parents=True)
    out.mkdir(parents=True)

    # a feature page linking OUT to repo-root sample_content, and IN to _static
    text = (
        "See [asset](../../../sample_content/a.usd) and "
        "[video](../_static/v.mp4) and [peer](other.md).\n"
        "```{include} ../../../changelist.md\n```\n"
    )
    logical = "features/FET_x.md"
    result = ad.rewrite_escaping_refs(text, logical, site, out)

    # escaping refs gain exactly one extra ../ (out is one level deeper)
    assert "(../../../../sample_content/a.usd)" in result
    assert "{include} ../../../../changelist.md" in result
    # in-tree refs are untouched
    assert "(../_static/v.mp4)" in result
    assert "(other.md)" in result


def test_rewrite_leaves_urls_and_anchors_alone(tmp_path):
    site = tmp_path / "docs"
    out = tmp_path / "_build" / "docs-src"
    site.mkdir(parents=True)
    out.mkdir(parents=True)
    text = "[web](https://example.com/x) [abs](/root) [anchor](#sec) [peer](sub/a.md#frag)\n"
    result = ad.rewrite_escaping_refs(text, "features/x.md", site, out)
    assert result == text  # nothing escapes, nothing external touched
