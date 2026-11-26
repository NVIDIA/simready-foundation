# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Regenerate packaged AIF 0.3 chiller schemas from the class CSVs in this checkout."""
import argparse
import csv
import json
from pathlib import Path


def schema_document(csv_path):
    csv_path = Path(csv_path)
    slug = csv_path.stem
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    names = [row["USD Attribute Namespace"] for row in rows]
    if not names or len(names) != len(set(names)) or "" in names:
        raise ValueError(f"{csv_path}: expected nonempty, unique attribute names")
    return {
        "class": slug,
        "displayName": slug.removesuffix("-chiller").title() + " Chiller",
        "assetClassTokens": [slug.title().replace("-", "")],
        "attributes": names,
        "requiredAttributes": [row["USD Attribute Namespace"] for row in rows
                               if row["Needed (Required / Optional)"].startswith("Required")],
        "attributeDefinitions": dict(zip(names, rows, strict=True)),
    }


def regenerate(csv_dir, config_dir, *, check):
    csvs = {path.stem: path for path in csv_dir.glob("*-chiller.csv")}
    for target in sorted(config_dir.glob("aif-equipment-*-chiller.json")):
        if target.stem.removeprefix("aif-equipment-") not in csvs:
            raise ValueError(f"{target.name} has no corresponding review CSV")
    for slug, csv_path in sorted(csvs.items()):
        target = config_dir / f"aif-equipment-{slug}.json"
        text = json.dumps(schema_document(csv_path), ensure_ascii=False, indent=2) + "\n"
        if check:
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                raise ValueError(f"Packaged {slug} schema is missing or differs from the CSV; regenerate it")
        else:
            config_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    tier = Path(__file__).resolve().parents[1]
    csv_dir = tier.parents[2] / "standards/equipment-classes/aif-v0.3"
    config_dir = tier / "simready/foundation/tier_aif/config/v0.3"
    try:
        regenerate(csv_dir, config_dir, check=args.check)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
