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
they are fast. One publishing regression also checks committed tier mappings
and navigation before exercising them in an isolated synthetic layout.
"""

from __future__ import annotations

import json
import sys
import tempfile
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


def _write_docs_sources(tier_dir: Path, sources, exclude=None) -> None:
    payload = {"schema_version": 1, "sources": sources}
    if exclude is not None:
        payload["exclude"] = exclude
    _write(tier_dir / ad.TIER_DOC_SOURCES_FILENAME, json.dumps(payload, indent=2) + "\n")


def _docnames(output_root: Path) -> set:
    return set(ad.docnames(output_root))


# ---------------------------------------------------------------------------
# 1. Source mapping.
# ---------------------------------------------------------------------------
def test_module_root_ignores_caches_beside_the_module(tmp_path):
    """A ``__pycache__`` sibling must not make the tier undiscoverable.

    A tier that ships modules directly under ``simready/foundation`` gets a
    cache directory there as soon as anything imports them, and counting it
    drops that tier's entire documentation with no error.
    """
    module_root = _make_tier(tmp_path, "core_tier", "tier_core")
    foundation = module_root.parent
    (foundation / "contracts.py").write_text("", encoding="utf-8")
    (foundation / "__pycache__").mkdir()
    (foundation / ".pytest_cache").mkdir()

    assert ad.tier_docs_module_root(module_root.parents[2]) == module_root


def test_module_root_is_none_when_two_real_modules_exist(tmp_path):
    module_root = _make_tier(tmp_path, "core_tier", "tier_core")
    (module_root.parent / "tier_other").mkdir()

    assert ad.tier_docs_module_root(module_root.parents[2]) is None


def test_known_edits_records_never_assemble_but_drafts_do(tmp_path):
    """`features/known_edits/` is provenance, not documentation.

    The records live inside `features/`, where the docs spec parser reads every
    file as a feature descriptor, so copying one fails the whole build on its
    missing `id` key. `features/drafts/` is the counter-case: every other
    subdirectory of `features/` is documentation and is copied.
    """
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    _make_site(site)

    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "features" / "FET006_Materials.MDL.md", "# Materials\n")
    _write(core / "features" / "drafts" / "FET006-draft-card.md", "# Draft\n")
    _write(
        core / "features" / "known_edits" / "FET006_Materials.MDL.0-1-0.toml",
        '[edit]\nfeature = "FET006_Materials.MDL.0-1-0"\n',
    )
    _write(site / "shared" / "features" / "features.md", "# Features hub\n")

    ad.assemble(site, out, tiers, manifest_path=out.parent / "m.json", exclude_logical=())

    assert not list(out.rglob("known_edits"))
    assert not list(out.rglob("FET006_Materials.MDL.0-1-0.toml"))
    assert (out / "features" / "drafts" / "FET006-draft-card.md").is_file()
    assert (out / "features" / "FET006_Materials.MDL.md").is_file()


def test_source_mapping_merges_tiers_shared_and_residual(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    _make_site(site)

    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "rules_and_reqs" / "core" / "core.md", "# Core cap\n")
    _write(core / "features" / "FET_001-minimal.md", "# Minimal\n")
    _write(core / "features" / "FET_001-minimal.json", "{}\n")  # non-doc travels along
    _write(core / "profiles" / "prop-neutral.md", "# Neutral\n")

    isaac = _make_tier(tiers, "tier_isaac", "isaac")
    _write(isaac / "rules_and_reqs" / "isaac_sim" / "isaac_sim.md", "# Isaac cap\n")
    _write(isaac / "features" / "FET_100-composition.md", "# Composition\n")

    # shared overlay: hubs mapped onto section roots
    _write(site / "shared" / "rules_and_reqs" / "rules_and_reqs.md", "# Rules and Requirements hub\n")
    _write(site / "shared" / "features" / "features.md", "# Features hub\n")
    _write(site / "shared" / "profiles" / "profiles.md", "# Profiles hub\n")

    manifest = ad.assemble(site, out, tiers, manifest_path=out.parent / "m.json", exclude_logical=())

    names = _docnames(out)
    assert "index" in names  # residual file
    assert "guides/guides" in names  # residual dir
    assert "rules_and_reqs/core/core" in names  # core tier
    assert "rules_and_reqs/isaac_sim/isaac_sim" in names  # isaac tier
    assert "features/FET_001-minimal" in names  # core tier narrative
    assert "features/FET_100-composition" in names  # isaac tier narrative
    assert "profiles/prop-neutral" in names  # core tier narrative
    assert "rules_and_reqs/rules_and_reqs" in names  # shared overlay hub
    assert "features/features" in names  # shared overlay hub
    assert "profiles/profiles" in names  # shared overlay hub

    # non-doc payload travels with the section
    assert (out / "features" / "FET_001-minimal.json").is_file()
    # package scaffolding is dropped
    assert not (out / "__init__.py").exists()
    assert not (out / "_plugin.py").exists()

    # manifest source labels are attributed correctly
    assert manifest["rules_and_reqs/core/core.md"]["source"] == "tier:tier_core"
    assert manifest["rules_and_reqs/isaac_sim/isaac_sim.md"]["source"] == "tier:tier_isaac"
    assert manifest["rules_and_reqs/rules_and_reqs.md"]["source"] == "shared"
    assert manifest["index.md"]["source"] == "site"


def test_tier_module_discovery_ignores_cache_directories(tmp_path):
    tiers = tmp_path / "tiers"
    module_root = _make_tier(tiers, "tier_core", "tier_core")
    (module_root.parent / "__pycache__").mkdir()

    assert ad.tier_docs_module_root(module_root.parents[2]) == module_root


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
        [{"path": "vendor_runtime_suite/docs", "destination": "guides/evaluate/vendor-tests"}],
    )

    manifest = ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    logical = "guides/evaluate/vendor-tests/index.md"
    assert (out / logical).read_text(encoding="utf-8") == "# Vendor runtime tests\n"
    assert manifest[logical]["source"] == "tier:vendor_tier:docs:vendor_runtime_suite/docs"


def test_newton_runtime_guide_is_published_and_linked(tmp_path):
    tiers_root = _TOOLING_DIR.parent
    newton_root = tiers_root / "simready_foundation_tier_newton"
    source = "simready/foundation/tier_newton/runtime_tests/docs"
    destination = "guides/evaluate/newton-tests"
    assert (newton_root / source, destination, source) in ad.tier_doc_sources(newton_root)
    for tier in ("simready_foundation_tier_core", "simready_foundation_tier_sensors"):
        assert destination not in {entry[1] for entry in ad.tier_doc_sources(tiers_root / tier)}

    # Links are written between the real source locations, so the synthetic
    # layout keeps the site docs and the tiers at their real relative positions.
    site = tmp_path / "nv_core" / "sr_specs" / "docs"
    tiers = tmp_path / "nv_core" / "tiers"
    out = tmp_path / "out"
    _make_site(site)
    real_site = tiers_root.parent / "sr_specs" / "docs"
    for page in ("evaluate.md", "overview.md"):
        relative = Path("guides/evaluate") / page
        _write(site / relative, (real_site / relative).read_text(encoding="utf-8"))

    newton = _make_tier(tiers, "simready_foundation_tier_newton", "tier_newton").parents[2]
    guide = "runtime-tests.md"
    _write(newton / source / guide, (newton_root / source / guide).read_text(encoding="utf-8"))
    _write_docs_sources(newton, [{"path": source, "destination": destination}])

    core = _make_tier(tiers, "simready_foundation_tier_core", "tier_core").parents[2]
    core_source = "simready/foundation/tier_core/runtime_tests/docs"
    core_page = "fet022-driven-joints.md"
    _write(
        core / core_source / core_page,
        (tiers_root / "simready_foundation_tier_core" / core_source / core_page).read_text(encoding="utf-8"),
    )
    _write_docs_sources(core, [{"path": core_source, "destination": "guides/evaluate/tests"}])

    manifest = ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    logical = destination + "/" + guide
    assert logical[:-3] in _docnames(out)
    assert manifest[logical]["source"] == "tier:simready_foundation_tier_newton:docs:" + source
    benchmark = out / "guides" / "evaluate"
    assert "Newton Runtime Tests <newton-tests/runtime-tests>" in (benchmark / "evaluate.md").read_text(
        encoding="utf-8"
    )
    assert "[Newton Runtime Tests](newton-tests/runtime-tests.md)" in (benchmark / "overview.md").read_text(
        encoding="utf-8"
    )
    core_text = (benchmark / "tests" / core_page).read_text(encoding="utf-8")
    assert "[Newton Runtime Tests](../newton-tests/runtime-tests.md)" in core_text
    assert (benchmark / "tests" / "../newton-tests/runtime-tests.md").resolve() == (out / logical).resolve()
    assert (out / logical).is_file()


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


def test_tier_exclude_keeps_codegen_pages_out_of_another_tiers_capability(tmp_path) -> None:
    """A tier can keep a codegen-only capability page out of the docs tree.

    The Newton tier needs its own capability page for requirement codegen in a
    capability the Core tier documents. Excluding it by source file keeps the
    Core page at the same logical path, and the Newton requirement page still
    assembles.
    """
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    newton = _make_tier(tiers, "tier_newton", "newton")
    _write(core / "rules_and_reqs" / "cap" / "capability-cap.md", "# Core cap\n")
    _write(newton / "rules_and_reqs" / "cap" / "capability-cap.md", "# Newton cap\n")
    _write(newton / "rules_and_reqs" / "cap" / "requirements" / "newton-req.md", "# Newton req\n")
    _write_docs_sources(
        newton.parents[2], [], exclude=["simready/foundation/newton/rules_and_reqs/cap/capability-cap.md"]
    )

    manifest = ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    assert (out / "rules_and_reqs" / "cap" / "capability-cap.md").read_text(encoding="utf-8") == "# Core cap\n"
    assert manifest["rules_and_reqs/cap/capability-cap.md"]["source"] == "tier:tier_core"
    assert manifest["rules_and_reqs/cap/requirements/newton-req.md"]["source"] == "tier:tier_newton"


def test_tier_exclude_rejects_missing_file(tmp_path) -> None:
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    module_root = _make_tier(tiers, "vendor_tier", "vendor")
    _write_docs_sources(module_root.parents[2], [], exclude=["simready/foundation/vendor/missing.md"])

    with pytest.raises(ad.AssembleError, match="excluded path is not a file"):
        ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())


# ---------------------------------------------------------------------------
# 2. Deterministic output.
# ---------------------------------------------------------------------------
def test_deterministic_output(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "rules_and_reqs" / "a.md", "# A\n")
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
    stale = core / "rules_and_reqs" / "stale.md"
    _write(stale, "# stale\n")
    out = tmp_path / "out"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert (out / "rules_and_reqs" / "stale.md").exists()

    stale.unlink()  # remove from source, reassemble
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert not (out / "rules_and_reqs" / "stale.md").exists()


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
    _write(core / "rules_and_reqs" / "dup.md", "# version A\n")
    _write(isaac / "rules_and_reqs" / "dup.md", "# version B — different!\n")

    with pytest.raises(ad.AssembleError, match="Divergent duplicate"):
        ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())


def test_identical_duplicate_is_allowed(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_a", "a")
    isaac = _make_tier(tiers, "tier_b", "b")
    _write(core / "rules_and_reqs" / "dup.md", "# identical\n")
    _write(isaac / "rules_and_reqs" / "dup.md", "# identical\n")

    manifest = ad.assemble(site, tmp_path / "out", tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    # first source wins the attribution; no error
    assert manifest["rules_and_reqs/dup.md"]["source"] == "tier:tier_a"


def test_rejected_rebuild_preserves_prior_output_and_manifest_integrity(tmp_path):
    """A late shared-overlay collision must not leave a truncated tree beside a prior manifest."""
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    manifest_file = tmp_path / "m.json"
    _make_site(site)

    tier_a = _make_tier(tiers, "tier_a", "a")
    tier_b = _make_tier(tiers, "tier_b", "b")
    _write(tier_a / "rules_and_reqs" / "a.md", "# Cap A\n")
    _write(tier_a / "features" / "f.md", "# Feature F\n")
    _write(tier_b / "rules_and_reqs" / "b.md", "# Cap B\n")
    _write(tier_b / "profiles" / "p.md", "# Profile P\n")

    shared_f = site / "shared" / "features" / "f.md"
    _write(shared_f, "# Feature F\n")  # identical overlap on baseline
    _write(site / "shared" / "features" / "hub.md", "# Features Hub\n")
    _write(site / "shared" / "profiles" / "zz-shared.md", "# Shared Profile\n")
    _write(site / "shared" / "zz-tail.md", "# Shared Tail\n")

    baseline_manifest = ad.assemble(site, out, tiers, manifest_path=manifest_file, exclude_logical=())
    assert len(baseline_manifest) == 9
    baseline_manifest_bytes = manifest_file.read_bytes()
    baseline_tree = {rel: (out / rel).read_bytes() for rel in baseline_manifest}

    # Mutate the shared feature so step (4) fails mid-way, before profiles/zz-shared.md and zz-tail.md.
    _write(shared_f, "# Feature F (divergent shared edit)\n")
    with pytest.raises(ad.AssembleError, match="Divergent duplicate"):
        ad.assemble(site, out, tiers, manifest_path=manifest_file, exclude_logical=())

    # Retained manifest and retained staged output must remain 100% consistent.
    retained = json.loads(manifest_file.read_text(encoding="utf-8"))["files"]
    actual_files = {rel: (out / rel).read_bytes() for rel, _ in ad._iter_files(out) if rel != ad.OUTPUT_OWNERSHIP_MARKER}
    assert set(retained) == set(actual_files)
    assert "profiles/zz-shared.md" in actual_files
    assert "zz-tail.md" in actual_files
    assert manifest_file.read_bytes() == baseline_manifest_bytes
    assert actual_files == baseline_tree

    # Restore the fixture and confirm reassembly succeeds with identical bytes.
    _write(shared_f, "# Feature F\n")
    ad.assemble(site, out, tiers, manifest_path=manifest_file, exclude_logical=())
    assert manifest_file.read_bytes() == baseline_manifest_bytes
    assert {rel: (out / rel).read_bytes() for rel in baseline_manifest} == baseline_tree


# ---------------------------------------------------------------------------
# 4. Missing sources.
# ---------------------------------------------------------------------------
def test_missing_tier_sections_and_overlay_are_tolerated(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)  # no shared/ overlay at all
    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "rules_and_reqs" / "only.md", "# only capability\n")
    # no features/ or profiles/ dirs for this tier

    names = _docnames_after(site, tiers, tmp_path)
    assert "rules_and_reqs/only" in names
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
# 5. Logical-prefix exclusion + Python dropping.
# ---------------------------------------------------------------------------
def test_exclude_logical_drops_named_subtree(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    isaac = _make_tier(tiers, "tier_isaac", "isaac")
    _write(isaac / "rules_and_reqs" / "physics_bodies" / "quarantined" / "capability-quarantined.md", "# q\n")
    _write(isaac / "rules_and_reqs" / "isaac_sim" / "isaac_sim.md", "# isaac\n")

    out = tmp_path / "out"
    ad.assemble(
        site,
        out,
        tiers,
        manifest_path=tmp_path / "m.json",
        exclude_logical=("rules_and_reqs/physics_bodies/quarantined",),
    )
    names = _docnames(out)
    assert "rules_and_reqs/isaac_sim/isaac_sim" in names
    assert not any("quarantined" in n for n in names)

    # nothing is excluded by default
    out2 = tmp_path / "out2"
    ad.assemble(site, out2, tiers, manifest_path=tmp_path / "m2.json")
    assert any("quarantined" in n for n in _docnames(out2))


def test_python_files_are_dropped(tmp_path) -> None:
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "core")
    newton = _make_tier(tiers, "tier_newton", "newton")
    _write(core / "rules_and_reqs" / "__init__.py", "import something\n")
    _write(core / "rules_and_reqs" / "cap" / "requirements.md", "# reqs\n")
    _write(core / "rules_and_reqs" / "cap" / "validation.py", "# core validators\n")
    _write(newton / "rules_and_reqs" / "cap" / "validation.py", "# newton validators\n")

    out = tmp_path / "out"
    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())
    assert (out / "rules_and_reqs" / "cap" / "requirements.md").exists()
    assert not (out / "rules_and_reqs" / "__init__.py").exists()
    assert not (out / "rules_and_reqs" / "cap" / "validation.py").exists()


# ---------------------------------------------------------------------------
# 6. Link rewriting.
# ---------------------------------------------------------------------------
def _repo_layout(tmp_path: Path):
    """Return ``(site, tiers, out, core module root)`` laid out like the repository."""
    site = tmp_path / "nv_core" / "sr_specs" / "docs"
    tiers = tmp_path / "nv_core" / "tiers"
    out = tmp_path / "nv_core" / "sr_specs" / "_build" / "docs-src"
    _make_site(site)
    core = _make_tier(tiers, "tier_core", "tier_core")
    return site, tiers, out, core


def test_source_relative_links_are_repointed_at_the_assembled_layout(tmp_path) -> None:
    site, tiers, out, core = _repo_layout(tmp_path)
    newton = _make_tier(tiers, "tier_newton", "tier_newton")
    _write(tmp_path / "sample_content" / "a.usda", "#usda 1.0\n")
    _write(core / "rules_and_reqs" / "cap" / "cap.md", "# Cap\n")
    _write(core / "rules_and_reqs" / "_includes" / "badges" / "cap.md", "badge\n")
    _write(newton / "rules_and_reqs" / "cap" / "newton-req.md", "# Newton req\n")
    _write(
        core / "features" / "F.md",
        "[cap](../rules_and_reqs/cap/cap.md#reqs) "
        "[newton](../../../../../tier_newton/simready/foundation/tier_newton/rules_and_reqs/cap/newton-req.md) "
        "[guide](../../../../../../sr_specs/docs/guides/guides.md) "
        "![asset](<../../../../../../../sample_content/a.usda>)\n",
    )
    _write(
        core / "rules_and_reqs" / "cap" / "requirements.md",
        "```{include} ../_includes/badges/cap.md\n```\n",
    )
    _write(
        site / "shared" / "features" / "features.md",
        "[F](../../../../tiers/tier_core/simready/foundation/tier_core/features/F.md)\n",
    )

    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    assert (out / "features" / "F.md").read_text(encoding="utf-8") == (
        "[cap](../rules_and_reqs/cap/cap.md#reqs) "
        "[newton](../rules_and_reqs/cap/newton-req.md) "
        "[guide](../guides/guides.md) "
        "![asset](<../../../../../sample_content/a.usda>)\n"
    )
    assert (out / "rules_and_reqs" / "cap" / "requirements.md").read_text(encoding="utf-8") == (
        "```{include} ../_includes/badges/cap.md\n```\n"
    )
    assert (out / "features" / "features.md").read_text(encoding="utf-8") == "[F](F.md)\n"
    staged_asset = (out / "features" / "../../../../../sample_content/a.usda").resolve()
    assert staged_asset == (tmp_path / "sample_content" / "a.usda").resolve()


def test_links_that_do_not_resolve_in_source_are_left_as_written(tmp_path) -> None:
    site, tiers, out, core = _repo_layout(tmp_path)
    text = (
        "[web](https://example.com/x) [abs](/rules_and_reqs/x.md) [anchor](#sec) "
        "[missing](missing.md) [sub]({{version}}) [mail](mailto:a@b.c)\n"
    )
    _write(core / "features" / "F.md", text)

    ad.assemble(site, out, tiers, manifest_path=tmp_path / "m.json", exclude_logical=())

    assert (out / "features" / "F.md").read_text(encoding="utf-8") == text


def test_path_refs_skip_code_and_comments_but_not_directive_bodies() -> None:
    text = (
        "[a](a.md) `[b](b.md)` <!-- [c](c.md) -->\n"
        "```usda\n[d](d.md)\n```\n"
        "````{note}\n[e](e.md)\n```python\n[f](f.md)\n```\n````\n"
        "```{include} g.md\n:start-after: x\n```\n"
        ":::{figure} h.png\n[i](i.md)\n:::\n"
        "```{toctree}\nj\n```\n"
        "[k]: <k dir/k.md>\n[^l]: footnote\n"
    )

    refs = [(text[start:end], kind) for start, end, kind in ad.iter_path_refs(text)]

    assert refs == [
        ("a.md", "link"),
        ("e.md", "link"),
        ("g.md", "directive"),
        ("h.png", "directive"),
        ("i.md", "link"),
        ("k dir/k.md", "link"),
    ]


# ---------------------------------------------------------------------------
# 7. Legacy feature route compatibility stubs.
# ---------------------------------------------------------------------------
def test_legacy_june_routes_emit_redirects_in_foundations1_layout(tmp_path):
    site = tmp_path / "docs"
    tiers = tmp_path / "tiers"
    out = tmp_path / "out"
    manifest_file = tmp_path / "m.json"
    _make_site(site)

    core = _make_tier(tiers, "tier_core", "core")
    _write(core / "features" / "FET_001_STANDARD.md", "# Minimal\n")
    _write(core / "features" / "FET_003_STANDARD.md", "# RBD Standard\n")
    _write(core / "features" / "FET_003_PHYSX.md", "# RBD PhysX\n")

    manifest = ad.assemble(site, out, tiers, manifest_path=manifest_file, exclude_logical=())
    names = _docnames(out)

    assert "features/FET_001_STANDARD" in names
    assert "features/FET_001-minimal" in names
    assert "features/FET_001-minimal.md" in manifest
    assert manifest["features/FET_001-minimal.md"]["source"] == "compat:2026.06"

    minimal_stub = (out / "features" / "FET_001-minimal.md").read_text(encoding="utf-8")
    assert minimal_stub.startswith("---\norphan: true\n---\n")
    assert "url=FET_001_STANDARD.html" in minimal_stub
    assert "[`FET_001_STANDARD`](FET_001_STANDARD.md)" in minimal_stub

    rbd_stub = (out / "features" / "FET_003-rigid_body_physics.md").read_text(encoding="utf-8")
    assert "url=FET_003_STANDARD.html" in rbd_stub
    assert "[`FET_003_STANDARD`](FET_003_STANDARD.md)" in rbd_stub
    assert "[`FET_003_PHYSX`](FET_003_PHYSX.md)" in rbd_stub


def test_committed_tiers_preserve_all_18_june_and_foundations1_feature_routes() -> None:
    tiers_root = _TOOLING_DIR.parent
    site_docs_root = tiers_root.parent / "sr_specs" / "docs"
    repo_root = tiers_root.parent.parent

    # The committed docs include files above the docs root, which are rewritten
    # with os.path.relpath; on Windows that requires the output on the repo's drive.
    with tempfile.TemporaryDirectory(dir=repo_root, prefix=".pytest-assemble-") as tmp:
        out = Path(tmp) / "docs"
        manifest_file = Path(tmp) / "manifest.json"

        manifest = ad.assemble(
            site_docs_root=site_docs_root,
            output_root=out,
            tiers_root=tiers_root,
            manifest_path=manifest_file,
        )
        names = _docnames(out)
        manifest_text = manifest_file.read_text(encoding="utf-8")

        assert len(ad.LEGACY_JUNE_FEATURE_ROUTES) == 18
        assert "features/FET_001-minimal" in names
        assert "features/FET_001_STANDARD" in names
        assert "features/FET_001-minimal" in manifest_text

        for june_stem, f1_stems in ad.LEGACY_JUNE_FEATURE_ROUTES:
            june_docname = f"features/{june_stem}"
            june_logical = f"{june_docname}.md"
            assert june_docname in names
            assert june_logical in manifest
            assert (out / june_logical).is_file()
            for f1_stem in f1_stems:
                assert f"features/{f1_stem}" in names
                assert f"features/{f1_stem}.md" in manifest

