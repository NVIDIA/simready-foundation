#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check every ``usd`` example on a requirement page against the rule it illustrates.

An example that does not parse, or that passes where the page says it fails, teaches an
author the wrong thing. This walks the requirement pages, extracts every fenced ``usd``
block, and holds each one to three things:

1. **It parses.** The block is written to a layer and opened. A block that USD cannot read
   is a defect whatever it says.
2. **It is captioned.** The line above the fence says Valid, Invalid or Warned. A block with
   no caption states no expectation, so nothing can be checked against it. Warned is held to
   the same expectation as Valid: a warning maps to ``IssueSeverity.WARNING``, which
   ``simready.validate`` filters out before it splits hard issues from soft, so it reaches
   neither collection and the page's own code must stay silent.
3. **The verdict is what the caption claims.** The page's own requirement code is expected
   to report on an Invalid block and to stay silent on a Valid one.

Every block is reported. Where a verdict cannot be reached in this environment -- an MDL
type check needs a Kit runtime, for instance -- the block is listed as undecided with the
reason rather than passed over, so the coverage number is honest.

Assets a block references are created next to it before validation, since a missing texture
or module would otherwise be reported instead of the defect the example is about. A path
whose file name begins with ``unknown``, ``missing`` or ``nonexistent`` is left absent, which
is how an example says the file is meant not to be there. A ``.png`` is written as a header
carrying the dimensions in the comment above it, where there is one, so a size limit can be
illustrated without committing a large image.

Usage:
    python tests/validate_requirement_examples.py [capability-dir ...]

With no argument it checks the visual materials capability. A capability under
the AIF tier is checked against the AIF-Entity profile instead of Robotics-Prop.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re
import shutil
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _first(*candidates: Path) -> Path:
    """The first path that exists. The spec tree has two layouts: requirements,
    features and profiles under ``nv_core/sr_specs/docs``, or under a tier package.
    Both are looked for so this runs either side of that move."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


_TIER = REPO / "nv_core" / "tiers" / "simready_foundation_tier_core" / "simready" / "foundation" / "tier_core"
_DOCS = REPO / "nv_core" / "sr_specs" / "docs"
CAPABILITIES = _first(_TIER / "capabilities", _DOCS / "capabilities")
FEATURES = _first(_TIER / "features", _DOCS / "features")
PROFILES = _first(_TIER / "profiles", _DOCS / "profiles")
TIER_MODULE = "simready.foundation.tier_core"
REVERSE_DOMAIN = "com.nvidia.simready"
DEFAULT_CAPABILITIES = [CAPABILITIES / "visualization" / "materials"]

# The AIF tier. Its requirement pages are checked the same way, but against the
# AIF-Entity profile: Robotics-Prop selects no AIF feature, so an AIF code would
# never report under it. Both published versions are tried, because CP.010-012
# exist only at 0.2.0 while CP.001-006 are 0.1.0 requirements.
_TIER_AIF_ROOT = REPO / "nv_core" / "tiers" / "simready_foundation_tier_aif"
_TIER_AIF = _TIER_AIF_ROOT / "simready" / "foundation" / "tier_aif"
AIF_CAPABILITIES = _TIER_AIF / "capabilities"
AIF_FEATURES = _TIER_AIF / "features"
AIF_PROFILES = _TIER_AIF / "profiles"
AIF_TIER_MODULE = "simready.foundation.tier_aif"
AIF_PROFILE_VERSIONS = (("AIF-Entity", "0.1.0"), ("AIF-Entity", "0.2.0"))


def _is_aif(path: Path) -> bool:
    try:
        path.resolve().relative_to(AIF_CAPABILITIES.resolve())
        return True
    except ValueError:
        return False


def _capabilities_root(path: Path) -> Path:
    return AIF_CAPABILITIES if _is_aif(path) else CAPABILITIES

FENCE_OPEN = re.compile(r"^```usd(?P<mode>\s+payload)?\s*$")
HEADING = re.compile(r"^#{1,6}\s+\S")
FENCE_CLOSE = re.compile(r"^```\s*$")
CODE_ROW = re.compile(r"^\|\s*Code\s*\|\s*([A-Z0-9.]+)\s*\|", re.MULTILINE)
VERDICT = re.compile(r"\b(invalid|valid|warned)\b", re.IGNORECASE)
ASSET_REF = re.compile(r"@([^@]+)@")
PIXEL_DIMS = re.compile(r"(\d+)\s*[x×]\s*(\d+)\s*pixels")
ABSENT_ON_PURPOSE = ("unknown", "missing", "nonexistent")

ROOT_PRIM = re.compile(r'^(?:def|over|class)\s+\w*\s*"([^"]+)"')


def layer_text(body: str) -> str:
    """The block, wrapped in the stage metadata a validator expects to find."""
    default_prim = ""
    for line in body.splitlines():
        match = ROOT_PRIM.match(line)
        if match:
            default_prim = f'    defaultPrim = "{match.group(1)}"\n'
            break
    return f'#usda 1.0\n(\n{default_prim}    metersPerUnit = 1\n    upAxis = "Z"\n)\n\n{body}'


@dataclass
class Block:
    page: Path
    line: int
    code: str
    caption: str
    body: str
    verdict: str | None = None
    parsed: bool = False
    parse_error: str = ""
    reported: bool = False
    findings: list[str] = field(default_factory=list)
    undecided: str = ""


def png_header(width: int, height: int) -> bytes:
    """A PNG carrying the given dimensions. Pillow reads size from IHDR alone."""
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def read_blocks(page: Path) -> list[Block]:
    text = page.read_text()
    code_match = CODE_ROW.search(text)
    code = code_match.group(1) if code_match else ""
    lines = text.splitlines()
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        if not FENCE_OPEN.match(lines[index]):
            index += 1
            continue
        start = index
        end = start + 1
        while end < len(lines) and not FENCE_CLOSE.match(lines[end]):
            end += 1
        above = start - 1
        while above >= 0 and not lines[above].strip():
            above -= 1
        caption = lines[above].strip() if above >= 0 else ""
        match = VERDICT.search(caption)
        blocks.append(
            Block(
                page=page,
                line=start + 1,
                code=code,
                caption=caption,
                body="\n".join(lines[start + 1 : end]) + "\n",
                verdict=match.group(1).lower() if match else None,
            )
        )
        index = end + 1
    return blocks


def materialise_assets(block: Block, directory: Path) -> None:
    """Create the files a block references, so their absence is not the finding."""
    for line in block.body.splitlines():
        for raw in ASSET_REF.findall(line):
            ref = raw.strip()
            if not ref or ref.startswith(("/", "http:", "https:", "omniverse:")):
                continue
            name = Path(ref).name
            if name.lower().startswith(ABSENT_ON_PURPOSE):
                continue
            target = (directory / ref).resolve()
            if directory.resolve() not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                continue
            if target.suffix.lower() == ".png":
                dims = PIXEL_DIMS.search(line)
                width, height = (int(dims.group(1)), int(dims.group(2))) if dims else (8, 8)
                target.write_bytes(png_header(width, height))
            elif target.suffix.lower() == ".mdl":
                target.write_text("mdl 1.6;\n")
            else:
                target.write_bytes(b"")


def ensure_aif_requirements_module(destination: Path) -> None:
    """Generate the AIF tier's requirements enums and attach them to the package.

    The AIF validators use relative imports (``from .. import _stage``), so the
    package has to be the real one from the source tree, not a namespace stub
    assembled from the generated directory alone. The tier root goes on
    ``sys.path`` ahead of any installed copy, and the generated ``requirements``
    subpackage is added to the package's ``__path__`` so the source tree is not
    written to.
    """
    import importlib

    from usd_profiles_nvidia.codegen import PythonGenerator

    destination.mkdir(parents=True, exist_ok=True)
    PythonGenerator(
        capabilities_root=str(AIF_CAPABILITIES),
        destination_dir=str(destination),
        package_name=f"{AIF_TIER_MODULE}.requirements",
        reverse_domain=REVERSE_DOMAIN,
    ).generate()
    sys.path.insert(0, str(_TIER_AIF_ROOT))
    package = importlib.import_module(AIF_TIER_MODULE)
    generated = destination.joinpath(*AIF_TIER_MODULE.split("."))
    if str(generated) not in package.__path__:
        package.__path__.append(str(generated))


def merged_capabilities_root(destination: Path) -> Path:
    """One rules root holding the Core and AIF capabilities together.

    The loader imports a rules root by its directory name and evicts that name
    from ``sys.modules`` before each import, so two roots both called
    ``capabilities`` cannot be loaded in one session: the second import resolves
    to the first root again and re-registers its rules. AIF-Entity selects Core
    features, so the AIF session needs both. The Core tree is copied, the AIF
    ``aif/`` capability and its ``config/`` are added, and the two ``__init__``
    files are concatenated so every validator module is imported.
    """
    root = destination / "capabilities"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(CAPABILITIES, root, ignore=ignore)
    shutil.copytree(AIF_CAPABILITIES / "aif", root / "aif", ignore=ignore)
    # AM.007 and the electrical rules read config/aif-equipment-*.json from the
    # package directory above capabilities/, so the merged root gets it too.
    shutil.copytree(_TIER_AIF / "config", destination / "config", ignore=ignore)
    init = (CAPABILITIES / "__init__.py").read_text() + "\n" + (AIF_CAPABILITIES / "__init__.py").read_text()
    (root / "__init__.py").write_text(init)
    return root


def ensure_requirements_module(destination: Path) -> None:
    """Generate the tier's requirements enums and put them on the path.

    Every capability's ``validation.py`` starts with
    ``import simready.foundation.tier_core.requirements``. That module is generated from the
    committed requirement markdown at build time and is not in the tree, so a checkout that
    has not been built cannot import a single capability -- which is what CI is. Generating it
    here is the same call the tier's hatchling hook makes, so the script runs against a bare
    checkout with only the published wheels installed.
    """
    from usd_profiles_nvidia.codegen import PythonGenerator

    destination.mkdir(parents=True, exist_ok=True)
    PythonGenerator(
        capabilities_root=str(CAPABILITIES),
        destination_dir=str(destination),
        package_name=f"{TIER_MODULE}.requirements",
        reverse_domain=REVERSE_DOMAIN,
    ).generate()
    sys.path.insert(0, str(destination))


def main(argv: list[str]) -> int:
    logging.disable(logging.CRITICAL)
    generated = tempfile.mkdtemp(prefix="requirement-enums-")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        ensure_requirements_module(Path(generated))
    import simready.validate as sv
    from pxr import Usd

    capabilities = [Path(a).resolve() for a in argv[1:]] or DEFAULT_CAPABILITIES
    with_aif = any(_is_aif(c) for c in capabilities)
    if with_aif:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ensure_aif_requirements_module(Path(tempfile.mkdtemp(prefix="aif-requirement-enums-")))

    blocks: list[Block] = []
    for capability in capabilities:
        for page in sorted(capability.rglob("requirements/*.md")):
            blocks.extend(read_blocks(page))

    # AIF-Entity selects Core features, so an AIF page needs both tiers' rules
    # registered; see merged_capabilities_root for why that is one merged root.
    features_paths = [FEATURES] + ([AIF_FEATURES] if with_aif else [])
    profiles_paths = sorted(PROFILES.glob("*.toml")) + (sorted(AIF_PROFILES.glob("*.toml")) if with_aif else [])

    sink = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="requirement-examples-") as tmp:
        root = Path(tmp)
        rules_root = merged_capabilities_root(root / "merged") if with_aif else CAPABILITIES
        sv.destroy()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            sv.initialize(
                rules_and_requirements_paths=[rules_root],
                features_paths=features_paths,
                profiles_paths=profiles_paths,
            )
        for number, block in enumerate(blocks):
            directory = root / f"block{number:03d}"
            directory.mkdir()
            layer = directory / "example.usda"
            layer.write_text(layer_text(block.body))
            materialise_assets(block, directory)

            try:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    stage = Usd.Stage.Open(str(layer))
                block.parsed = stage is not None and any(stage.Traverse())
                if not block.parsed:
                    block.parse_error = "opened but holds no prims"
            except Exception as error:  # noqa: BLE001 - the message is the report
                block.parse_error = str(error).strip().splitlines()[-1][:160]

            if not block.parsed:
                continue

            profiles = AIF_PROFILE_VERSIONS if _is_aif(block.page) else (("Robotics-Prop", "4.0.0"),)
            results = []
            for profile_id, profile_version in profiles:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    result = sv.validate_asset(
                        sv.AssetValidationConfig(
                            asset_path=str(layer),
                            profile_id=profile_id,
                            profile_version=profile_version,
                        )
                    )
                if result:
                    results.append(result)
            if not results:
                block.undecided = "no validation result"
                continue
            for result in results:
                for issue in list(result.issues) + list(result.soft_issues):
                    code = str(getattr(getattr(issue, "requirement", None), "code", "") or "")
                    if code.endswith("." + block.code):
                        block.reported = True
                        finding = str(getattr(issue, "message", issue))[:140]
                        if finding not in block.findings:
                            block.findings.append(finding)

    # ---------------------------------------------------------------- report
    failures: list[str] = []
    undecided: list[Block] = []
    print(f"{len(blocks)} usd blocks across {len({b.page for b in blocks})} requirement pages\n")
    for block in blocks:
        where = f"{block.page.relative_to(_capabilities_root(block.page))}:{block.line}"
        if block.parse_error:
            print(f"  DOES NOT PARSE  {where}\n                  {block.parse_error}")
            failures.append(where)
            continue
        if block.verdict is None:
            print(f"  NO CAPTION      {where}  (caption read: {block.caption[:60]!r})")
            failures.append(where)
            continue
        if block.undecided:
            print(f"  undecided       {where}  {block.code} {block.verdict}: {block.undecided}")
            undecided.append(block)
            continue
        expected = block.verdict == "invalid"
        if block.reported == expected:
            print(f"  ok              {where}  {block.code} {block.verdict}")
        else:
            claim = "reports nothing" if expected else f"reports {len(block.findings)}"
            print(f"  WRONG VERDICT   {where}  {block.code} {block.verdict} but {claim}")
            for finding in block.findings[:3]:
                print(f"                  {finding}")
            failures.append(where)

    checked = len(blocks) - len(undecided)
    print(f"\n{checked}/{len(blocks)} blocks decided, {len(failures)} failing")
    if undecided:
        print("undecided in this environment:")
        for block in undecided:
            print(f"  {block.page.relative_to(_capabilities_root(block.page))}:{block.line}  {block.undecided}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
