# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regenerate gh-pages index.html and versions.json from version subdirs."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "docs_version_refs.py"


def version_sort_key(name: str) -> list[tuple[int, int | str]]:
    key: list[tuple[int, int | str]] = []
    for part in re.split(r"[.-]", name):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return key


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <gh-pages-dir> <pages-url>", file=sys.stderr)
        return 1

    root = Path(sys.argv[1])
    pages_url = sys.argv[2].rstrip("/")
    dirs = sorted(
        [
            path.name
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith(".") and path.name != "latest"
        ],
        key=version_sort_key,
        reverse=True,
    )

    entries = []
    first = True
    for version in dirs:
        label = subprocess.check_output(
            [sys.executable, str(SCRIPT), "label", version],
            text=True,
        ).strip()
        if first and label == version:
            label = f"{version} (latest)"
            first = False
        entries.append(
            {"name": label, "version": version, "url": f"{pages_url}/{version}/"},
        )

    (root / "versions.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")

    index_lines = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>SimReady Foundation Docs</title>",
        "<style>",
        "  body { font-family: system-ui, sans-serif; max-width: 600px;",
        "         margin: 4rem auto; padding: 0 1rem; }",
        "  h1 { font-size: 1.4rem; }",
        "  ul { list-style: none; padding: 0; }",
        "  li { margin: 0.5rem 0; }",
        "  a  { color: #76b900; text-decoration: none; font-weight: 600; }",
        "  a:hover { text-decoration: underline; }",
        "</style></head><body>",
        "<h1>SimReady Foundation Documentation</h1>",
        "<ul>",
        '  <li><a href="latest/">latest</a></li>',
    ]
    for version in dirs:
        label = subprocess.check_output(
            [sys.executable, str(SCRIPT), "label", version],
            text=True,
        ).strip()
        index_lines.append(f'  <li><a href="{version}/">{label}</a></li>')
    index_lines.extend(["</ul></body></html>"])
    (root / "index.html").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
