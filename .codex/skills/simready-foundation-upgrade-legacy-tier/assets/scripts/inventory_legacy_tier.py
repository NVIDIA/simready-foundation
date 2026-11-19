#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Inventory legacy SimReady tier references without modifying scanned roots."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".txt",
    ".usd",
    ".usda",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "_build",
    "build",
    "dist",
    "node_modules",
    "venv",
}
GENERATED_DIRS = {"foundations2"}

TOKEN_PATTERNS = {
    "legacy_fet": re.compile(r"\bFET_?\d{3}(?:_[A-Z][A-Z0-9]*)+\b"),
    "dotted_fet": re.compile(
        r"\bFET\d{3}(?:_[A-Za-z0-9_-]+)?\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    ),
    "capability": re.compile(
        r"\bCAP[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){0,2}\b"
    ),
    "aif_or_dsx": re.compile(r"\b(?:AIF|DSX)\b", re.IGNORECASE),
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic, read-only inventory of legacy SimReady "
            "tier manifests, IDs, profiles, validators, tests, adapters, and caches."
        )
    )
    parser.add_argument("roots", nargs="+", type=Path, help="Files or directories to scan")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout")
    parser.add_argument(
        "--max-occurrences",
        type=int,
        default=50,
        help="Maximum stored occurrences per token (default: 50)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Skip individual files larger than this many bytes (default: 10 MiB)",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Include generated foundations2 directories",
    )
    args = parser.parse_args(argv)
    if args.max_occurrences < 1:
        parser.error("--max-occurrences must be positive")
    if args.max_bytes < 1:
        parser.error("--max-bytes must be positive")
    return args


def iter_files(root: Path, include_generated: bool) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    skipped = SKIP_DIRS if include_generated else SKIP_DIRS | GENERATED_DIRS
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name.casefold() not in skipped
        )
        for file_name in sorted(file_names):
            path = Path(directory) / file_name
            if path.suffix.casefold() in TEXT_SUFFIXES or file_name == "pyproject.toml":
                yield path


def read_text(path: Path, max_bytes: int) -> tuple[str | None, str | None]:
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None, f"larger than --max-bytes ({size} bytes)"
        data = path.read_bytes()
    except OSError as exc:
        return None, str(exc)
    if b"\x00" in data[:8192]:
        return None, "binary content"
    return data.decode("utf-8", errors="replace"), None


def roles_for(path: Path, text: str) -> list[str]:
    normalized = path.as_posix().casefold()
    name = path.name.casefold()
    roles: set[str] = set()
    if "/features/" in normalized or "feature" in name:
        roles.add("feature_catalog")
    if "/profiles/" in normalized or "profile" in name:
        roles.add("profile_catalog")
    if "validation.py" in normalized or "validator" in normalized:
        roles.add("validator")
    if any(term in normalized for term in ("runtime_test", "benchmark", "test_definition")):
        roles.add("runtime_test")
    if any(term in normalized for term in ("asset_handler_modules", "adapter", "upgrade")):
        roles.add("adapter_or_upgrader")
    if any(term in normalized for term in ("cache", "stamp", "report", "result")):
        roles.add("stamp_cache_or_report")
    if path.suffix.casefold() in {".usd", ".usda"}:
        roles.add("asset_metadata")
    if name in {"pyproject.toml", "_tier.py", "_plugin.py"}:
        roles.add("tier_registration")
    if path.suffix.casefold() in {".md", ".rst"}:
        roles.add("documentation")
    if TOKEN_PATTERNS["aif_or_dsx"].search(text):
        roles.add("aif_or_dsx")
    return sorted(roles)


def sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    return 1 if value else 0


def manifest_hint(path: Path, text: str) -> dict[str, Any] | None:
    if path.suffix.casefold() != ".json":
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    feature_id = data.get("id")
    if not isinstance(feature_id, str) or not feature_id.startswith("FET"):
        return None
    runtime_test_count = sequence_count(data.get("runtime_tests"))
    is_source = data.get("source") is True
    if runtime_test_count:
        classification = "runtime-fet-candidate"
    elif is_source:
        classification = "source-fet-candidate-needs-tested-derived-reference"
    else:
        classification = "needs-runtime-evidence-or-capability"
    requirements = data.get("requirements", data.get("additional_requirements"))
    dependencies = data.get("dependencies", data.get("feature_dependencies"))
    return {
        "path": str(path.resolve()),
        "id": feature_id,
        "legacy_version": data.get("version"),
        "source": is_source,
        "runtime_test_count": runtime_test_count,
        "requirement_count": sequence_count(requirements),
        "dependency_count": sequence_count(dependencies),
        "classification_hint": classification,
    }


def scan(args: argparse.Namespace) -> dict[str, Any]:
    roots = [root.resolve() for root in args.roots]
    missing = [str(root) for root in roots if not root.exists()]
    if missing:
        raise FileNotFoundError("Missing scan roots: " + ", ".join(missing))

    scanned: set[str] = set()
    skipped_files: list[dict[str, str]] = []
    role_paths: dict[str, set[str]] = defaultdict(set)
    references: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    occurrence_totals: Counter[tuple[str, str]] = Counter()
    manifest_hints: list[dict[str, Any]] = []

    for root in roots:
        for path in iter_files(root, args.include_generated):
            resolved = str(path.resolve())
            if resolved in scanned:
                continue
            scanned.add(resolved)
            text, error = read_text(path, args.max_bytes)
            if text is None:
                skipped_files.append({"path": resolved, "reason": error or "unknown"})
                continue
            for role in roles_for(path, text):
                role_paths[role].add(resolved)
            hint = manifest_hint(path, text)
            if hint:
                manifest_hints.append(hint)
            lines = text.splitlines()
            for line_number, line in enumerate(lines, start=1):
                for kind, pattern in TOKEN_PATTERNS.items():
                    for match in pattern.finditer(line):
                        token = match.group(0)
                        if kind == "aif_or_dsx":
                            token = token.upper()
                        key = (kind, token)
                        occurrence_totals[key] += 1
                        if len(references[key]) < args.max_occurrences:
                            references[key].append(
                                {
                                    "path": resolved,
                                    "line": line_number,
                                    "column": match.start() + 1,
                                }
                            )

    reference_rows = []
    kind_counts: Counter[str] = Counter()
    for (kind, token), occurrences in sorted(references.items()):
        total = occurrence_totals[(kind, token)]
        kind_counts[kind] += total
        reference_rows.append(
            {
                "kind": kind,
                "token": token,
                "total_occurrences": total,
                "occurrences": occurrences,
                "truncated": total > len(occurrences),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "roots": [str(root) for root in roots],
        "summary": {
            "files_scanned": len(scanned) - len(skipped_files),
            "files_skipped": len(skipped_files),
            "feature_manifest_hints": len(manifest_hints),
            "occurrences_by_kind": dict(sorted(kind_counts.items())),
            "files_by_role": {
                role: len(paths) for role, paths in sorted(role_paths.items())
            },
        },
        "feature_manifest_hints": sorted(
            manifest_hints, key=lambda row: (row["path"], row["id"])
        ),
        "references": reference_rows,
        "files_by_role": {
            role: sorted(paths) for role, paths in sorted(role_paths.items())
        },
        "skipped_files": sorted(skipped_files, key=lambda row: row["path"]),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = scan(args)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, indent=2, sort_keys=False) + "\n"
    if args.output:
        output = args.output.resolve()
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write report {output}: {exc}", file=sys.stderr)
            return 2
        print(output)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
