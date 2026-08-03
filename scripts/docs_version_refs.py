# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Resolve git refs to versioned docs paths.

Usage:
    python scripts/docs_version_refs.py fetch
    python scripts/docs_version_refs.py list
    python scripts/docs_version_refs.py version [ref-or-branch-or-tag]
    python scripts/docs_version_refs.py label <version-slug>
    python scripts/docs_version_refs.py stale-dirs [ref-or-branch-or-tag]
    python scripts/docs_version_refs.py cleanup-previews <gh-pages-dir>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "VERSION.md"

# preview_<product>_<major>-<minor>-<patch>  e.g. preview_aif_0-1-0
_PREVIEW_BRANCH_RE = re.compile(
    r"^preview_(?P<product>[a-z0-9]+)_(?P<version>\d+(?:-\d+)*)$",
    re.IGNORECASE,
)
_PREVIEW_SLUG_RE = re.compile(r"^(?P<product>[a-z]+)-(?P<version>\d+(?:\.\d+)*)$", re.IGNORECASE)


def preview_branch_to_slug(branch: str) -> str | None:
    match = _PREVIEW_BRANCH_RE.match(branch)
    if not match:
        return None
    product = match.group("product").lower()
    version = match.group("version").replace("-", ".")
    return f"{product}-{version}"


def preview_slug_to_label(slug: str) -> str | None:
    match = _PREVIEW_SLUG_RE.match(slug)
    if not match:
        return None
    return f"{match.group('product').upper()} {match.group('version')} (Preview)"


def fetch_refs() -> None:
    subprocess.run(
        [
            "git",
            "fetch",
            "origin",
            "+refs/heads/release_*:refs/remotes/origin/release_*",
            "+refs/heads/preview_*:refs/remotes/origin/preview_*",
            "--tags",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def list_branch_refs() -> list[str]:
    fetch_refs()
    refs: set[str] = set()
    for pattern in ("refs/remotes/origin/release_*", "refs/remotes/origin/preview_*"):
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)", pattern],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            name = line.removeprefix("origin/")
            if name:
                refs.add(name)
    return sorted(refs)


def ref_to_branch(ref: str) -> str:
    if ref.startswith("refs/heads/"):
        return ref.removeprefix("refs/heads/")
    if ref.startswith("refs/remotes/origin/"):
        return ref.removeprefix("refs/remotes/origin/")
    return ref


def ref_to_version(ref: str) -> str:
    if ref.startswith("refs/tags/v"):
        return ref.removeprefix("refs/tags/v")
    if ref.startswith("v"):
        return ref[1:]

    branch = ref_to_branch(ref)

    if branch.startswith("release_"):
        return branch.removeprefix("release_").replace("-", ".")
    if branch.startswith("preview_"):
        slug = preview_branch_to_slug(branch)
        if slug:
            return slug
        return branch
    if branch == "main":
        return VERSION_FILE.read_text(encoding="utf-8").strip()

    raise ValueError(f"unsupported ref for docs version: {ref}")


def version_label(version: str) -> str:
    preview_label = preview_slug_to_label(version)
    if preview_label:
        return preview_label

    branch_label = preview_slug_to_label(preview_branch_to_slug(version) or "")
    if branch_label:
        return branch_label

    if version.startswith("preview_"):
        return f"{version} (Preview)"

    return version


def stale_deploy_dirs_for_ref(ref: str) -> list[str]:
    branch = ref_to_branch(ref)
    if not branch.startswith("preview_"):
        return []
    slug = preview_branch_to_slug(branch)
    if slug and slug != branch:
        return [branch]
    return []


def stale_preview_deploy_dirs(deploy_dir: Path) -> list[str]:
    stale: list[str] = []
    for path in sorted(deploy_dir.iterdir()):
        if not path.is_dir() or path.name == "latest":
            continue
        branch = path.name
        if not branch.startswith("preview_"):
            continue
        slug = preview_branch_to_slug(branch)
        if slug and slug != branch and (deploy_dir / slug).is_dir():
            stale.append(branch)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Docs version ref helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("fetch", help="Fetch release_*, preview_*, and tags from origin")

    list_parser = subparsers.add_parser("list", help="List release and preview branch names")
    list_parser.set_defaults(func=lambda _args: print("\n".join(list_branch_refs())))

    version_parser = subparsers.add_parser("version", help="Map a git ref to a docs version slug")
    version_parser.add_argument(
        "ref",
        nargs="?",
        default="",
        help="Git ref, branch name, or tag (defaults to GITHUB_REF when set)",
    )

    label_parser = subparsers.add_parser("label", help="Format a version slug for the switcher UI")
    label_parser.add_argument("version", help="Docs version slug or preview branch name")

    stale_parser = subparsers.add_parser(
        "stale-dirs",
        help="List gh-pages dirs superseded by a mapped preview slug for this ref",
    )
    stale_parser.add_argument(
        "ref",
        nargs="?",
        default="",
        help="Git ref, branch name, or tag (defaults to GITHUB_REF when set)",
    )

    cleanup_parser = subparsers.add_parser(
        "cleanup-previews",
        help="List preview_* dirs on gh-pages superseded by mapped slug folders",
    )
    cleanup_parser.add_argument("deploy_dir", type=Path, help="gh-pages checkout directory")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        fetch_refs()
        return 0

    if args.command == "version":
        ref = args.ref or __import__("os").environ.get("GITHUB_REF", "")
        if not ref:
            print("missing ref", file=sys.stderr)
            return 1
        try:
            print(ref_to_version(ref))
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0

    if args.command == "label":
        print(version_label(args.version))
        return 0

    if args.command == "stale-dirs":
        ref = args.ref or __import__("os").environ.get("GITHUB_REF", "")
        if not ref:
            print("missing ref", file=sys.stderr)
            return 1
        for stale in stale_deploy_dirs_for_ref(ref):
            print(stale)
        return 0

    if args.command == "cleanup-previews":
        for stale in stale_preview_deploy_dirs(args.deploy_dir):
            print(stale)
        return 0

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
