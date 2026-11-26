# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared schema tooling works with any subset of the chiller class extensions."""
import importlib.util
import json
from pathlib import Path

import pytest

from simready.foundation.tier_aif.rules_and_reqs.aif import chiller_schema, equipment_classes


TIER = Path(__file__).resolve().parents[1]


@pytest.fixture
def generator():
    spec = importlib.util.spec_from_file_location("chiller_generator", TIER / "tools/generate_chiller_schema.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registered_classes_match_packaged_schemas():
    config = TIER / "simready/foundation/tier_aif/config/v0.3"
    for path in config.glob("aif-equipment-*-chiller.json"):
        expected = json.loads(path.read_text(encoding="utf-8"))
        for token in expected["assetClassTokens"]:
            assert chiller_schema.schema_for(f" {token.lower()} ") == {**expected, "introducedIn": "0.3.0"}
            assert equipment_classes.normalize_03(token) == expected["class"]
            assert equipment_classes.normalize(token) is None
    assert chiller_schema.schema_for("UnregisteredChiller") is None
    assert not chiller_schema.is_chiller(None)


def test_schema_generation_with_independently_added_classes(tmp_path, generator):
    sources, config = tmp_path / "csvs", tmp_path / "packaged"
    # Shared foundation can be installed before a class has shipped.
    generator.regenerate(sources, config, check=True)
    sources.mkdir()
    for slug in ("example-cooled-chiller", "other-cooled-chiller"):
        source = sources / f"{slug}.csv"
        source.write_text("USD Attribute Namespace,Needed (Required / Optional)\naif:spec:rating_W,Required\n")
        with pytest.raises(ValueError, match="missing or differs"):
            generator.regenerate(sources, config, check=True)
        generator.regenerate(sources, config, check=False)
        generator.regenerate(sources, config, check=True)
        packaged = config / f"aif-equipment-{slug}.json"
        document = json.loads(packaged.read_text())
        assert document["class"] == slug
        assert document["requiredAttributes"] == ["aif:spec:rating_W"]

    packaged.write_text("{}\n")
    with pytest.raises(ValueError, match="missing or differs"):
        generator.regenerate(sources, config, check=True)
    source.unlink()
    with pytest.raises(ValueError, match="no corresponding review CSV"):
        generator.regenerate(sources, config, check=True)


def test_registry_loads_versioned_schemas_without_changing_legacy_classes(tmp_path, monkeypatch):
    legacy_path = TIER / "simready/foundation/tier_aif/config/aif-equipment-cdu.json"
    legacy_doc = json.loads(legacy_path.read_text())
    (tmp_path / legacy_path.name).write_text(json.dumps(legacy_doc))
    schema = {
        "class": "example-chiller",
        "displayName": "Example Chiller",
        "attributes": ["aif:spec:rating_W"],
        "assetClassTokens": ["ExampleChiller"],
        "requiredAttributes": ["aif:spec:rating_W"],
        "attributeDefinitions": {"aif:spec:rating_W": {}},
    }
    versioned = tmp_path / "v0.3"
    versioned.mkdir()
    (versioned / "aif-equipment-example-chiller.json").write_text(json.dumps(schema))
    monkeypatch.setattr(equipment_classes, "_CONFIG_DIR", tmp_path)
    current = equipment_classes._load()
    assert current == {legacy_doc["class"]: legacy_doc, "example-chiller": {**schema, "introducedIn": "0.3.0"}}
    schema["introducedIn"] = "0.2.0"
    (versioned / "aif-equipment-example-chiller.json").write_text(json.dumps(schema))
    with pytest.raises(ValueError, match="schema version must be 0.3.0"):
        equipment_classes._load()
