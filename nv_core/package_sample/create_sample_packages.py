# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the five sample packages from canonical assets into a new directory.

Requires simready-package, simready-validate, installed Foundation tiers, usd-core,
and blake3. Run from an environment containing this checkout's tier packages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from physx_usd_schemas import PhysxSchema  # Register before opening USD.
from pxr import Sdf, Usd, UsdUtils
import simready.validate as sv
from simready.package import standard, validation

REPO = Path(__file__).resolve().parents[2]
PROPS = REPO / "sample_content/common_assets/props_general"
PACKAGES = REPO / "sample_content/packaging/simple_packages"
sys.path.insert(0, str(REPO / "skills/simready-foundation-create-package/assets/scripts"))
from sr_pkg_sample.wrapp_compat import std_pkg_def as multi_hash

APPLE = PROPS / "apple_a01/simready_usd/sm_apple_a01_01.usd"
ORANGE = PROPS / "obs_orange_a01/simready_usd/sm_obs_orange_a01_01.usd"
SETTINGS = validation.ValidationSettings(
    pre_profiles=("Package-Candidate@1.0.0",), post_profiles=("Package@1.0.0",)
)


def content_path_with_disk_case(root: Path, candidate: Path) -> Path:
    """Resolve each authored component to its on-disk spelling on every OS."""
    relative = candidate.relative_to(root)
    current = root
    for component in relative.parts:
        entries = list(current.iterdir())
        exact = [entry for entry in entries if entry.name == component]
        matches = exact or [entry for entry in entries if entry.name.casefold() == component.casefold()]
        if len(matches) != 1:
            raise FileNotFoundError(f"Missing or ambiguous package dependency: {candidate}")
        current = matches[0]
    return current


def copy_asset(source: Path, destination: Path) -> str:
    """Export the default composed asset as the simple package's static snapshot."""
    source = source.resolve()
    stage = Usd.Stage.Open(str(source))
    # The simple snapshot is a single model hierarchy; expand instance prototypes
    # in a session layer so flattening does not emit additional root prims.
    stage.SetEditTarget(stage.GetSessionLayer())
    while True:
        instances = [prim for prim in stage.Traverse() if prim.IsInstance()]
        if not instances:
            break
        for prim in instances:
            prim.SetInstanceable(False)
    layer = stage.Flatten()
    data = dict(layer.customLayerData)
    metadata = dict(data.get("SimReady_Metadata", {}))
    metadata.pop("Variants", None)
    metadata.pop("validation", None)
    data["SimReady_Metadata"] = metadata
    layer.customLayerData = data
    destination.mkdir(parents=True, exist_ok=True)

    def localize(path: str) -> str:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = Path(Sdf.ComputeAssetPathRelativeToLayer(stage.GetRootLayer(), path))
        resolved = content_path_with_disk_case(source.parent, resolved.resolve())
        relative = resolved.relative_to(source.parent)
        if relative.parts[0].casefold() == "textures":
            relative = Path("textures", *relative.parts[1:])
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, target)
        return "./" + relative.as_posix()

    UsdUtils.ModifyAssetPaths(layer, localize)
    layer.Export(str(destination / source.name))
    thumbnail = Path(".thumbs/256x256") / (source.name + ".png")
    (destination / thumbnail).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.parent / thumbnail, destination / thumbnail)
    if source.with_suffix(".json").is_file():
        shutil.copy2(source.with_suffix(".json"), destination / source.with_suffix(".json").name)
    return source.name


def write_multi_hash(folder: Path, package_id: str, items: list[dict], files: list) -> None:
    """Use the bundled package helper for the BLAKE3 demonstration."""
    if not multi_hash.BLAKE3_AVAILABLE:
        raise RuntimeError("Install blake3 to regenerate the multi-hash sample")
    algorithms = multi_hash.default_hash_algos(False)
    for item in items:
        result = multi_hash.compute_hashes_from_path(str(folder / item["relative_path"]), algorithms)
        item["hash"], item["size"] = result.hashes, result.size
    standard.write_package_files(folder, package_id, "Apache-2.0", items, files)
    definition = standard.read_definition(folder)
    for entry in definition["metadata"]:
        entry["hash"] = multi_hash.compute_hashes_from_path(
            str(folder / standard.METADATA_DIR / entry["name"]), algorithms
        ).hashes
    definition["content_hash"] = multi_hash.compute_content_hash(items, hash_algos=algorithms)
    definition["package_hash"] = multi_hash.compute_package_hash(
        package_id, "Apache-2.0", definition["content_hash"], definition["metadata"], hash_algos=algorithms
    )
    model = standard.PackageStandardDefinition(**definition)
    (folder / standard.DEFINITION_FILE).write_text(standard.package_standard_model_json(model), encoding="utf-8", newline="\n")


def build(output: Path) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    output.mkdir(parents=True)
    sv.initialize([], [], [])
    for name in ("apple_a01_materials", "apple_a01_nobom", "apple_a01_usd_bom",
                 "apple_a01_usd_bom_multi_hash", "fruit_f01_multi_usd"):
        folder = output / name
        folder.mkdir()
        roots = []
        if name == "apple_a01_materials":
            # Preserve the materials-only example's content.
            original = PACKAGES / name
            for rel in standard.content_files(original, standard.Excluder()):
                target = folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original / rel, target)
        else:
            selected = [("apple_a01", APPLE)]
            if name == "fruit_f01_multi_usd":
                selected.append(("orange_a01", ORANGE))
            for asset_name, source in selected:
                relative = Path(asset_name) / "simready_usd"
                filename = copy_asset(source, folder / relative)
                root_usd = (relative / filename).as_posix()
                roots.append(root_usd)
                targets = [sv.ProfileTarget("Robotics-Prop", "3.2.0"),
                           sv.ProfileTarget("Robotics-Prop", "4.0.0")]
                if name == "apple_a01_nobom":
                    targets.append(sv.ProfileTarget("Package-Candidate", "1.0.0"))
                snapshot = Usd.Stage.Open(str(folder / root_usd))
                results = sv.validate_stage_against_profiles(
                    snapshot, targets, write_metadata=True, asset_path=str(folder / root_usd)
                )
                snapshot = None
                if any(r is None or not sv.features_summary_passed(r.features_summary) for r in results):
                    raise RuntimeError(f"Canonical asset failed its profile in {name}: {root_usd}")
        package_id = f"com.nvidia.simready.{name}.1.0.0"
        files = validation.pre_validate(folder, roots, SETTINGS) if roots else []
        if name == "apple_a01_nobom":
            definition = {"format_version": "1.0", "package_id": package_id, "license": "Apache-2.0"}
            (folder / standard.DEFINITION_FILE).write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8", newline="\n")
            settings = validation.ValidationSettings(pre_profiles=SETTINGS.pre_profiles, post_profiles=("Package-NoBOM@1.0.0",))
        else:
            items = standard.bom_items(folder, standard.content_files(folder, standard.Excluder()))
            if name.endswith("_multi_hash"):
                write_multi_hash(folder, package_id, items, files)
            else:
                standard.write_package_files(folder, package_id, "Apache-2.0", items, files)
            problems = standard.verify_package_dir(folder)
            if problems:
                raise RuntimeError(f"{name}: {problems}")
            settings = SETTINGS
        evidence = validation.post_validate(folder, settings)
        for report in evidence:
            path = folder / standard.METADATA_DIR / report.name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(report.data)
        print(f"PASS {name}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New staging directory for the five packages")
    build(parser.parse_args().output)
