#!/usr/bin/env python3
"""Regenerate the committed sample packages under ``sample_content/packaging/simple_packages/``.

The five samples are built deterministically from the canonical source
assets in ``simready_foundations/sample_content/common_assets/props_general/``:

* ``apple_a01_materials``      — WRAPP, no USD files, materials + textures only.
* ``apple_a01_nobom``          — no-WRAPP, single sha256, ``apple_a01/simready_usd/``.
* ``apple_a01_usd_bom``        — WRAPP, single sha256, ``apple_a01/simready_usd/``.
* ``apple_a01_usd_bom_multi_hash`` — WRAPP, sha256 + blake3, same content as above.
* ``fruit_f01_multi_usd``      — WRAPP, single sha256, two USD trees
                                 (``apple_a01/simready_usd/`` and
                                 ``orange_a01/simready_usd/``).

Every package is built in a temporary working directory: the relevant
subset of the source assets is copied into ``<tmp>/<sample>_src/``, then
the ``sr_pkg_sample`` Python API is driven directly (the same path
``create_simready_package.py`` takes from the CLI).  WRAPP-backed samples
are first published into a temp ``<tmp>/<sample>_repo`` and then
``wrapp.install`` lays them out into the final destination under
``simple_packages/<sample>/``; no-WRAPP samples are stamped in place and
the temp source folder *is* the final package, copied verbatim into
``simple_packages/<sample>/``.

Usage
-----
::

    # From an activated package_sample venv (the one at
    # simready_foundations/nv_core/package_sample/.venv).  blake3 must be
    # importable for apple_a01_usd_bom_multi_hash.
    python create_sample_packages.py

    # Regenerate a subset:
    python create_sample_packages.py apple_a01_usd_bom_multi_hash fruit_f01_multi_usd

    # Keep the temp working directory around for inspection:
    python create_sample_packages.py --keep-temp

The script wipes the existing ``simple_packages/<sample>/`` folder for
every sample it touches and rebuilds it from scratch — re-running it is
the supported way to refresh the committed samples after a producer or
spec change.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

# Quiet the asset-validator INFO chatter.  Keep WARNING+ so genuine
# producer or validation issues still bubble up.
logging.basicConfig(level=logging.WARNING)

import simready.validate as sv  # noqa: E402

from sr_pkg_sample import (  # noqa: E402
    FOUNDATIONS_DOCS_DIR,
    ValidationFailed,
    post_validate,
    pre_validate,
)
from sr_pkg_sample.create_package_definition import create_package_definition  # noqa: E402

LICENSE_ID = "LicenseRef-NVIDIA-Proprietary"
PACKAGE_VERSION = "1.0.0"

_PACKAGE_SAMPLE_DIR = Path(__file__).resolve().parent
_FOUNDATIONS_DIR = _PACKAGE_SAMPLE_DIR.parent.parent
_PROPS_GENERAL = (
    _FOUNDATIONS_DIR
    / "sample_content"
    / "common_assets"
    / "props_general"
)
_APPLE_SRC = _PROPS_GENERAL / "apple_a01"
_ORANGE_SRC = _PROPS_GENERAL / "obs_orange_a01"
_SIMPLE_PACKAGES_DIR = (
    _FOUNDATIONS_DIR
    / "sample_content"
    / "packaging"
    / "simple_packages"
)


# ---------------------------------------------------------------------------
# Sample build descriptions — declarative inputs to the same async builder.
# ---------------------------------------------------------------------------


@dataclass
class SampleSpec:
    """Inputs for one sample-package build."""

    name: str
    use_wrapp: bool
    sha256_only: bool
    root_usds: list[str] = field(default_factory=list)
    allow_no_usd_files: bool = False
    #: Filesystem-layout populator — copies the asset subset into
    #: ``src_dir`` (which already exists and is empty when this is called).
    populate: Callable[[Path], None] = field(default=lambda _: None)


def _ensure_thumbnails(usd_dir: Path) -> None:
    """Create ``.thumbs/256x256/<file>.png`` for every USD in *usd_dir*.

    The committed sample assets may ship a legacy thumbnail
    (e.g. ``.thumbs/<stem>_thumbnail.png``) but not the SR.002
    ``256x256/<file>.usd.png`` layout.  This copies the legacy file
    when available or writes a minimal placeholder PNG header.
    """
    thumbs = usd_dir / ".thumbs"
    dest_dir = thumbs / "256x256"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for usd in usd_dir.glob("*.usd"):
        expected = dest_dir / f"{usd.name}.png"
        if expected.exists():
            continue
        legacy = next(thumbs.glob("*.png"), None) if thumbs.is_dir() else None
        if legacy:
            shutil.copy2(legacy, expected)
        else:
            expected.write_bytes(b"\x89PNG")


def _populate_apple_simready_usd(src_dir: Path) -> None:
    """Copy ``props_general/apple_a01/simready_usd/`` into ``src_dir/apple_a01/simready_usd/``."""
    target = src_dir / "apple_a01" / "simready_usd"
    shutil.copytree(_APPLE_SRC / "simready_usd", target)
    _ensure_thumbnails(target)


def _populate_apple_materials_only(src_dir: Path) -> None:
    """Copy ``simready_usd/{materials,textures}`` into ``src_dir/`` (flat)."""
    src = _APPLE_SRC / "simready_usd"
    shutil.copytree(src / "materials", src_dir / "materials")
    shutil.copytree(src / "textures", src_dir / "textures")


def _populate_fruit_multi(src_dir: Path) -> None:
    """Copy apple + orange ``simready_usd/`` trees side by side."""
    apple = src_dir / "apple_a01" / "simready_usd"
    orange = src_dir / "orange_a01" / "simready_usd"
    shutil.copytree(_APPLE_SRC / "simready_usd", apple)
    shutil.copytree(_ORANGE_SRC / "simready_usd", orange)
    _ensure_thumbnails(apple)
    _ensure_thumbnails(orange)


SAMPLES: list[SampleSpec] = [
    SampleSpec(
        name="apple_a01_materials",
        use_wrapp=True,
        sha256_only=True,
        root_usds=[],
        allow_no_usd_files=True,
        populate=_populate_apple_materials_only,
    ),
    SampleSpec(
        name="apple_a01_nobom",
        use_wrapp=False,
        sha256_only=True,
        root_usds=["apple_a01/simready_usd/sm_apple_a01_01.usd"],
        populate=_populate_apple_simready_usd,
    ),
    SampleSpec(
        name="apple_a01_usd_bom",
        use_wrapp=True,
        sha256_only=True,
        root_usds=["apple_a01/simready_usd/sm_apple_a01_01.usd"],
        populate=_populate_apple_simready_usd,
    ),
    SampleSpec(
        name="apple_a01_usd_bom_multi_hash",
        use_wrapp=True,
        sha256_only=False,
        root_usds=["apple_a01/simready_usd/sm_apple_a01_01.usd"],
        populate=_populate_apple_simready_usd,
    ),
    SampleSpec(
        name="fruit_f01_multi_usd",
        use_wrapp=True,
        sha256_only=True,
        root_usds=[
            "apple_a01/simready_usd/sm_apple_a01_01.usd",
            "orange_a01/simready_usd/sm_obs_orange_a01_01.usd",
        ],
        populate=_populate_fruit_multi,
    ),
]


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------


async def _build_wrapp(spec: SampleSpec, src_dir: Path, repo_dir: Path, dest_dir: Path) -> None:
    """WRAPP path: pre_validate → create_package → post_validate → wrapp.install."""
    import wrapp

    from sr_pkg_sample.create_package_using_wrapp import create_package

    pre = await pre_validate(
        src_dir,
        root_usds=spec.root_usds or None,
        write_metadata=True,
        allow_no_usd_files=spec.allow_no_usd_files,
        sha256_only=spec.sha256_only,
    )
    if not pre.passed:
        raise RuntimeError(
            f"pre_validate failed for {spec.name}: {sorted(pre.failed_features)}"
        )

    created = await create_package(
        spec.name,
        PACKAGE_VERSION,
        LICENSE_ID,
        str(src_dir),
        str(repo_dir),
        sha256_only=spec.sha256_only,
    )

    pkg_def = repo_dir / ".packages" / spec.name / PACKAGE_VERSION / "com.nvidia.simready.packaging.json"
    post = await post_validate(pkg_def, write_evidence=True)
    if not post.passed:
        raise RuntimeError(
            f"post_validate failed for {spec.name}: {sorted(post.failed_features)}"
        )

    # Patch the post-validation evidence files into the WRAPP catalog so
    # the next ``wrapp.install`` carries them along.  Mirrors what
    # ``sr_pkg_sample.create_simready_package`` does in the high-level
    # workflow path.
    if post.evidence_paths and created.marker_url is not None:
        from sr_pkg_sample.wrapp_compat.catalog_patch import augment_wrapp_catalog
        from sr_pkg_sample.wrapp_compat.create_and_emit import METADATA_FOLDER

        pkg_dir_url = created.pkg_def_url.rsplit("/", 1)[0]
        evidence_files = [
            (
                f"{METADATA_FOLDER}/{path.name}",
                f"{pkg_dir_url}/{METADATA_FOLDER}/{path.name}",
                path.read_bytes(),
            )
            for path in post.evidence_paths
        ]
        async with wrapp.ContextManager():
            await augment_wrapp_catalog(
                created.marker_url,
                files=evidence_files,
                context=wrapp.CommandParameters(),
            )

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    async with wrapp.ContextManager() as scheduler:
        await wrapp.install(
            spec.name,
            PACKAGE_VERSION,
            destination=str(dest_dir),
            repo=str(repo_dir),
            scheduler=scheduler,
        )

    # ``wrapp.install`` leaves a ``.<name>.wrapp`` install marker in the
    # destination so subsequent installs of the same package short-circuit.
    # The committed samples are static fixtures — strip the marker so the
    # samples are byte-for-byte the package layout, not "an installed copy".
    marker = dest_dir / f".{spec.name}.wrapp"
    if marker.exists():
        marker.unlink()


async def _build_no_wrapp(spec: SampleSpec, src_dir: Path, dest_dir: Path) -> None:
    """No-WRAPP path: pre_validate(stamp_usd) → create_package_definition → post_validate."""
    pre = await pre_validate(
        src_dir,
        root_usds=spec.root_usds or None,
        stamp_usd=True,
        allow_no_usd_files=spec.allow_no_usd_files,
    )
    if not pre.passed:
        raise RuntimeError(
            f"pre_validate failed for {spec.name}: {sorted(pre.failed_features)}"
        )

    await create_package_definition(
        spec.name,
        PACKAGE_VERSION,
        LICENSE_ID,
        str(src_dir),
    )

    pkg_def = src_dir / "com.nvidia.simready.packaging.json"
    post = await post_validate(pkg_def, profiles=["Package-NoBOM"])
    if not post.passed:
        raise RuntimeError(
            f"post_validate failed for {spec.name}: {sorted(post.failed_features)}"
        )

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    # In the no-WRAPP flow the source folder *is* the package; copy the
    # whole tree (including any ``.metadata/`` written by post_validate)
    # into the final destination under simple_packages/.
    shutil.copytree(src_dir, dest_dir)


async def _build_one(spec: SampleSpec, work_dir: Path) -> None:
    """Drive one sample build from a clean temp working directory."""
    src_dir = work_dir / f"{spec.name}_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    spec.populate(src_dir)

    dest_dir = _SIMPLE_PACKAGES_DIR / spec.name

    if spec.use_wrapp:
        repo_dir = work_dir / f"{spec.name}_repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        await _build_wrapp(spec, src_dir, repo_dir, dest_dir)
    else:
        await _build_no_wrapp(spec, src_dir, dest_dir)


# ---------------------------------------------------------------------------
# Runtime + CLI
# ---------------------------------------------------------------------------


def _initialize_runtime() -> None:
    """Mirror the orchestrator's runtime setup: sv.initialize()."""
    sv.initialize(
        rules_and_requirements_paths=[FOUNDATIONS_DOCS_DIR / "capabilities"],
        features_paths=[FOUNDATIONS_DOCS_DIR / "features"],
        profiles_paths=[FOUNDATIONS_DOCS_DIR / "profiles" / "profiles.toml"],
    )


async def _run(specs: Sequence[SampleSpec], keep_temp: bool) -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="sr_sample_packages_"))
    try:
        for spec in specs:
            print(f"\n=== Building {spec.name} ===")
            await _build_one(spec, work_dir)
            print(f"OK: {spec.name} → {_SIMPLE_PACKAGES_DIR / spec.name}")
    finally:
        if keep_temp:
            print(f"\n[--keep-temp] Working directory preserved at: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "samples",
        nargs="*",
        metavar="NAME",
        help=(
            "Sample names to (re)build.  Defaults to all five.  "
            "Choices: " + ", ".join(s.name for s in SAMPLES)
        ),
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Don't delete the temporary working directory after the run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the known sample names and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.list:
        for spec in SAMPLES:
            kind = "WRAPP" if spec.use_wrapp else "no-WRAPP"
            algos = "sha256" if spec.sha256_only else "sha256+blake3"
            print(f"  {spec.name:32s}  {kind:8s}  {algos}")
        return 0

    by_name = {s.name: s for s in SAMPLES}
    if args.samples:
        unknown = [n for n in args.samples if n not in by_name]
        if unknown:
            print(
                f"error: unknown sample(s): {unknown}.  "
                f"Known: {sorted(by_name)}",
                file=sys.stderr,
            )
            return 2
        specs = [by_name[n] for n in args.samples]
    else:
        specs = SAMPLES

    _initialize_runtime()

    try:
        asyncio.run(_run(specs, keep_temp=args.keep_temp))
    except ValidationFailed as exc:
        print(f"\nFAIL: validation failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
