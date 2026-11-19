# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Convert binary (crate) USD layers to human-readable .usda.

The SimReady sample assets ship as USD crate -- binary -- even where the file
is named ``.usd``. Crate is the right shipping format (smaller, faster to
open), but it cannot be read in a text editor, grepped, or diffed. This
converts a layer, or a whole tree of them, to ``.usda`` so you can read what
an asset actually authors.

Only ``pxr`` is required, which ``pip install -r requirements.txt`` already
provides via ``usd-core``. The ``usdcat`` command-line tool does the same job
but ships only with a full OpenUSD build or an Omniverse Kit environment, not
with the ``usd-core`` wheel.

Converted files are for human legibility. Do not commit them -- the crate
layer stays the source of truth.

Usage:
    python scripts/usd_to_usda.py <path> [<path> ...] [--outdir DIR] [--force]
    python scripts/usd_to_usda.py --check <path> [<path> ...]

    # one asset, written beside the original as sm_alcohol_a01_01.usda
    python scripts/usd_to_usda.py sample_content/common_assets/props_general/alcohol_a01/simready_usd/sm_alcohol_a01_01.usd

    # a whole tree, collected somewhere scratch so nothing lands in the repo
    python scripts/usd_to_usda.py sample_content/common_assets --outdir /tmp/usda

    # report what is binary and what is already .usda, converting nothing
    python scripts/usd_to_usda.py --check sample_content
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

USD_SUFFIXES = (".usd", ".usda", ".usdc")

CRATE_MAGIC = b"PXR-USDC"
USDA_MAGIC = b"#usda"


def encoding_of(path: Path) -> str:
    """Return 'crate', 'usda', or 'other' by reading the layer's magic bytes.

    This is the same check you can run by hand: ``head -c 8 <file>``. A crate
    layer starts with ``PXR-USDC``, a ``.usda`` one with ``#usda``. The file
    extension does not tell you -- ``.usd`` is either.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(8)
    except OSError:
        return "other"
    if head.startswith(CRATE_MAGIC):
        return "crate"
    if head.startswith(USDA_MAGIC):
        return "usda"
    return "other"


def collect(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a sorted list of USD layers.

    ``.usdz`` is deliberately excluded: it is a zip archive, not a layer, so
    exporting it is a different operation.
    """
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            for suffix in USD_SUFFIXES:
                found.update(path.rglob(f"*{suffix}"))
        elif path.is_file():
            found.add(path)
        else:
            print(f"warning: no such path, skipping: {path}", file=sys.stderr)
    return sorted(found)


def destination(layer: Path, outdir: Path | None, roots: list[Path]) -> Path:
    """Where the .usda for ``layer`` should be written.

    With no --outdir the result sits beside the original. With --outdir the
    tree structure below the input root is preserved, so two assets with the
    same filename do not collide.
    """
    if outdir is None:
        return layer.with_suffix(".usda")
    for root in roots:
        if root.is_dir():
            try:
                return (outdir / layer.relative_to(root)).with_suffix(".usda")
            except ValueError:
                continue
    return (outdir / layer.name).with_suffix(".usda")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert binary (crate) USD layers to human-readable .usda.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="USD files, or directories to search")
    parser.add_argument("--outdir", type=Path, help="write .usda files here instead of beside the originals")
    parser.add_argument("--force", action="store_true", help="overwrite an existing .usda")
    parser.add_argument("--check", action="store_true", help="report each layer's encoding and convert nothing")
    args = parser.parse_args()

    layers = collect(args.paths)
    if not layers:
        print("No USD layers found.", file=sys.stderr)
        return 1

    if args.check:
        counts: dict[str, int] = {}
        for layer in layers:
            encoding = encoding_of(layer)
            counts[encoding] = counts.get(encoding, 0) + 1
            print(f"{encoding:<6} {layer}")
        print("\n" + ", ".join(f"{n} {name}" for name, n in sorted(counts.items())))
        return 0

    # Imported here so --check still works without usd-core installed.
    try:
        from pxr import Sdf
    except ImportError:
        print(
            "usd-core is not installed. Run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    converted = skipped = failed = 0
    for layer_path in layers:
        if encoding_of(layer_path) == "usda":
            skipped += 1
            continue

        out_path = destination(layer_path, args.outdir, args.paths)
        if out_path.exists() and not args.force:
            print(f"exists, skipping (use --force): {out_path}", file=sys.stderr)
            skipped += 1
            continue

        layer = Sdf.Layer.FindOrOpen(str(layer_path))
        if layer is None:
            print(f"could not open: {layer_path}", file=sys.stderr)
            failed += 1
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if layer.Export(str(out_path)):
            print(f"{layer_path} -> {out_path}")
            converted += 1
        else:
            print(f"export failed: {layer_path}", file=sys.stderr)
            failed += 1

    print(f"\n{converted} converted, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
