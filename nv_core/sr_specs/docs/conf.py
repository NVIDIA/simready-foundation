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
import logging
import os
from pathlib import Path

_root = Path(__file__).resolve().parent
_repo_root = _root.parents[2]

# -- Project information -----------------------------------------------------

project = "SimReady Foundation"
copyright = "2026, NVIDIA Corporation"
author = "NVIDIA"

_version_file = _repo_root / "VERSION.md"
_default_version = _version_file.read_text().strip() if _version_file.exists() else "0.0.0"
version = os.environ.get("DOCS_VERSION", _default_version).strip() or _default_version
release = version
_display_version = os.environ.get("DOCS_VERSION_LABEL", "").strip()

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx.ext.githubpages",
    "sphinxcontrib.mermaid",
]

# The internal repo_usd_profiles extension is only available via packman.
# Skip gracefully so the public build still works.
try:
    import omni.usd_profiles.sphinx.ext  # noqa: F401

    extensions.append("omni.usd_profiles.sphinx.ext")
except ImportError:
    pass

suppress_warnings = [
    "myst.role_unknown",
    "myst.directive_unknown",
]

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "capabilities/_includes/badges/*.md",
    "capabilities/_includes/badges/**",
    "capabilities/_includes/tags/**",
    "capabilities/_includes/tables/**",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"

# -- MyST configuration ------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "deflist",
]

myst_custom_roles = {"tag": "raw"}

myst_substitutions = {
    "performance": '<span class="tag tag-performance">performance</span>',
}

myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]

# -- HTML output -------------------------------------------------------------

html_theme = "nvidia_sphinx_theme"
html_baseurl = os.environ.get("DOCS_BASE_URL", "")

_switcher_url = os.environ.get("DOCS_VERSIONS_JSON", "")

html_theme_options = {
    "secondary_sidebar_items": ["page-toc"],
    "copyright_override": {"start": 2025},
    "pygments_light_style": "tango",
    "pygments_dark_style": "monokai",
    "navigation_depth": 2,
}

if _switcher_url:
    html_theme_options["check_switcher"] = False
    html_theme_options["switcher"] = {
        "json_url": _switcher_url,
        "version_match": version,
    }
    html_theme_options["navbar_end"] = [
        "version-switcher",
        "theme-switcher",
        "navbar-icon-links",
    ]

html_title = (
    f"{project} {_display_version}"
    if _display_version
    else f"{project} v{version}"
)

html_static_path = ["_static"]
html_css_files = ["tags.css"]

html_show_sourcelink = False

# -- Sphinx-copybutton -------------------------------------------------------

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True
