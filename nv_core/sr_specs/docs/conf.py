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

"""Standalone Sphinx configuration for the SimReady Foundation docs.

This config drives the *public* (GitHub Pages) documentation build launched by
the repo-root ``build_docs.py``. It is deliberately kept in sync with the
internal repoman build, which generates its own ``conf.py`` from
``nv_core/sr_specs/repo.toml`` ``[repo_docs]``; the two pipelines share the same
extensions (notably ``usd_profiles_nvidia.sphinx.ext``, which registers the
``tag`` role and the per-page ``{{profile}}`` / ``{{version}}`` substitutions
used throughout the requirement/profile pages), theme, and MyST settings so
they render equivalently.

``build_docs.py`` assembles the tier docs + shared overlay + residual chrome
into ``nv_core/sr_specs/_build/docs-src`` and copies this file in as that
tree's ``conf.py`` before invoking Sphinx, so ``_static`` and every relative
reference resolve from the staged source root.
"""

from __future__ import annotations

import os

# -- Project information -----------------------------------------------------
project = "Content Capabilities"
copyright = "2025-2026, NVIDIA Corporation"
author = "NVIDIA"

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    # Internal extension (public on PyPI as ``usd-profiles-nvidia``): provides
    # the ``tag`` role, the requirement/feature/profile tables, and the
    # per-page ``{{profile}}`` / ``{{version}}`` substitutions.
    "usd_profiles_nvidia.sphinx.ext",
]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
root_doc = "index"

# Non-document trees that live alongside the docs but must not be treated as
# Sphinx sources.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # Badge/tag/table include fragments are transcluded into capability pages,
    # not rendered standalone. Excluding them avoids "not in any toctree"
    # warnings while ``{include}`` transclusion still reads them from disk.
    # Mirrors nv_core/sr_specs/repo.toml sphinx_exclude_patterns.
    "capabilities/_includes/badges/*.md",
    "capabilities/_includes/badges/**",
    "capabilities/_includes/tags/**",
    "capabilities/_includes/tables/**",
]

# -- MyST configuration ------------------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "deflist",
    "fieldlist",
    "attrs_inline",
    "attrs_block",
    "tasklist",
]
myst_heading_anchors = 4
# Whitelisted custom roles (the ``tag`` role is implemented by the
# usd_profiles_nvidia extension). Mirrors repo.toml's sphinx_conf_py_extra.
myst_custom_roles = ["tag"]
myst_substitutions = {
    "performance": '<span class="tag tag-performance">performance</span>',
}

# -- HTML output -------------------------------------------------------------
html_theme = "nvidia_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["tags.css"]

# -- Versioned deploy / version switcher -------------------------------------
# ``build_docs.py`` / the GitHub workflow export these; the switcher dropdown
# and canonical version label come from them when present.
_docs_version = os.environ.get("DOCS_VERSION", "")
_docs_version_label = os.environ.get("DOCS_VERSION_LABEL", _docs_version)
_docs_versions_json = os.environ.get("DOCS_VERSIONS_JSON", "")

if _docs_version:
    version = _docs_version
    release = _docs_version

html_theme_options = {}
if _docs_versions_json and _docs_version:
    # nvidia-sphinx-theme is pydata-based, so it consumes the standard switcher.
    html_theme_options["switcher"] = {
        "json_url": _docs_versions_json,
        "version_match": _docs_version,
    }
    # versions.json is published after the docs build, so the theme's
    # build-time validation cannot succeed on the first release deployment.
    html_theme_options["check_switcher"] = False
    html_theme_options["navbar_end"] = ["version-switcher", "theme-switcher"]

html_context = {
    "default_mode": "auto",
}
if _docs_version_label:
    html_context["version_label"] = _docs_version_label
