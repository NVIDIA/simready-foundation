# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Equipment class definitions, loaded from ``config/aif-equipment-<class>.json``.

One file per equipment class, as AM.007 describes. Each file names the class, the
``aif:core:assetClass`` tokens an author may write for it, the ``aif:spec:*``
attributes it must carry, and whether the thermal cooling and AC electrical
features apply to it.

Class availability is versioned. Definitions marked introducedIn 0.3.0 are
available through the AIF 0.3 registry; legacy AM.007 retains its prior classes.
"""
import json
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _check(condition: bool, filename: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{filename}: {message}")


def _validate_identity(doc: dict, filename: str) -> None:
    for key in ("class", "displayName", "assetClassTokens", "attributes"):
        _check(key in doc, filename, f"missing required key '{key}'")

    _check(isinstance(doc["class"], str) and doc["class"], filename, "'class' must be a non-empty string")
    _check(isinstance(doc["displayName"], str), filename, "'displayName' must be a string")

    tokens = doc["assetClassTokens"]
    _check(isinstance(tokens, list) and tokens, filename,
           "'assetClassTokens' must be a non-empty list of strings, not "
           f"{type(tokens).__name__}")
    _check(all(isinstance(t, str) and t.strip() for t in tokens), filename,
           "every entry in 'assetClassTokens' must be a non-empty string")


def _validate(doc: dict, filename: str) -> None:
    """Validate a template with the general thermal and electrical interfaces."""
    _validate_identity(doc, filename)
    for key in ("thermalCooling", "electricalAC"):
        _check(key in doc, filename, f"missing required key '{key}'")

    attributes = doc["attributes"]
    _check(isinstance(attributes, list) and attributes, filename,
           "'attributes' must be a non-empty list of attribute names, not "
           f"{type(attributes).__name__}")
    _check(all(isinstance(a, str) and a.startswith("aif:spec:") for a in attributes), filename,
           "every entry in 'attributes' must be an 'aif:spec:*' name")

    if "introducedIn" in doc:
        _check(doc["introducedIn"] == "0.3.0", filename,
               "'introducedIn' must be '0.3.0' when present")

    thermal = doc["thermalCooling"]
    _check(isinstance(thermal, dict) and "applies" in thermal, filename,
           "'thermalCooling' must be an object with an 'applies' key")
    if thermal["applies"]:
        prefixes = thermal.get("connectionPointPrefixes")
        _check(isinstance(prefixes, list) and prefixes, filename,
               "'thermalCooling.applies' is true, so 'connectionPointPrefixes' "
               "must be a non-empty list")

    electrical = doc["electricalAC"]
    _check(isinstance(electrical, dict) and "applies" in electrical, filename,
           "'electricalAC' must be an object with an 'applies' key")
    if electrical["applies"]:
        for name in ("nominalVoltage", "powerRating", "frequency"):
            _check(isinstance(electrical.get(name), str), filename,
                   f"'electricalAC.applies' is true, so '{name}' must name an attribute")


def _validate_chiller_schema(doc, filename):
    """A versioned chiller sheet defines typed rows and supplies dedicated interface checks."""
    _validate_identity(doc, filename)
    _check(doc.get("introducedIn", "0.3.0") == "0.3.0", filename, "schema version must be 0.3.0")
    fields = doc["attributes"]
    definitions = doc.get("attributeDefinitions")
    required = doc.get("requiredAttributes")
    _check(isinstance(fields, list) and fields
           and all(isinstance(name, str) and name.startswith("aif:spec:") for name in fields),
           filename, "'attributes' must list aif:spec:* names")
    _check(isinstance(definitions, dict) and set(definitions) == set(fields),
           filename, "'attributeDefinitions' must contain the declared fields")
    _check(isinstance(required, list) and all(isinstance(name, str) and name in definitions for name in required),
           filename, "'requiredAttributes' must list declared fields")


def _load() -> dict:
    classes = {}
    version_dir = _CONFIG_DIR / "v0.3"
    paths = [*_CONFIG_DIR.glob("aif-equipment-*.json"), *version_dir.glob("aif-equipment-*-chiller.json")]
    for path in sorted(paths):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}: not valid JSON -- {exc}") from exc
        _check(isinstance(doc, dict), path.name, "must hold a JSON object")
        if path.parent == version_dir:
            _validate_chiller_schema(doc, path.name)
            doc.setdefault("introducedIn", "0.3.0")
        else:
            _validate(doc, path.name)
        key = doc["class"]
        if key in classes:
            raise ValueError(f"duplicate equipment class '{key}' in {path.name}")
        classes[key] = doc
    if not classes:
        raise ValueError(f"no equipment class definitions found in {_CONFIG_DIR}")
    return classes


_CLASSES_03 = _load()
# Published AM.007 class lookup remains unchanged when a 0.3-only class is added.
_CLASSES = {key: doc for key, doc in _CLASSES_03.items()
            if doc.get("introducedIn", "0.1.0") in ("0.1.0", "0.2.0")}
ATTRIBUTES_03 = {key: frozenset(doc["attributes"]) for key, doc in _CLASSES_03.items()}
RECOGNISED_03 = tuple(sorted(_CLASSES_03))

# class -> the aif:spec:* attributes an asset of that class must carry (AM.007).
ATTRIBUTES = {k: frozenset(v["attributes"]) for k, v in _CLASSES.items()}

# The versioned registry supplies a single schema document to all chiller validators.
CHILLER_SCHEMAS = {
    key: doc for key, doc in _CLASSES_03.items()
    if key.endswith("-chiller") and "attributeDefinitions" in doc
}

# class -> human-readable name, for diagnostics.
DISPLAY_NAMES = {k: v["displayName"] for k, v in _CLASSES.items()}

# Every recognised class, in a stable order, for diagnostics.
RECOGNISED = tuple(sorted(_CLASSES))

# Lowercased aif:core:assetClass token -> class. Two classes claiming one token is
# a definition error, so it is caught here rather than resolving arbitrarily.
def _build_tokens(classes: dict) -> dict:
    tokens: dict = {}
    for key, doc in classes.items():
        for token in doc["assetClassTokens"]:
            slug = token.lower().strip()
            if tokens.setdefault(slug, key) != key:
                raise ValueError(
                    f"assetClass token '{slug}' claimed by both '{tokens[slug]}' and '{key}'"
                )
    return tokens


_TOKENS = _build_tokens(_CLASSES)
_TOKENS_03 = _build_tokens(_CLASSES_03)

# Classes the thermal cooling feature applies to (TC.001, TC.002), and the
# connection point name prefixes each of them must carry.
THERMAL_CLASSES = frozenset(k for k, v in _CLASSES.items() if v["thermalCooling"]["applies"])
THERMAL_CP_PREFIXES = {
    k: tuple(v["thermalCooling"]["connectionPointPrefixes"])
    for k, v in _CLASSES.items()
    if v["thermalCooling"]["applies"]
}

# Classes the AC electrical feature applies to (EL.001-EL.004), and the attribute
# name each of them uses for the three AC concepts. The names differ by class.
AC_CLASSES = frozenset(k for k, v in _CLASSES.items() if v["electricalAC"]["applies"])
AC_ATTRIBUTE = {
    k: {
        "nominalVoltage": v["electricalAC"]["nominalVoltage"],
        "powerRating": v["electricalAC"]["powerRating"],
        "frequency": v["electricalAC"]["frequency"],
    }
    for k, v in _CLASSES.items()
    if v["electricalAC"]["applies"]
}


def normalize(raw: str) -> str | None:
    """Resolve an authored ``aif:core:assetClass`` value to a class, or None."""
    return _TOKENS.get(raw.lower().strip())


def normalize_03(raw: str) -> str | None:
    """Resolve an AIF 0.3 class without expanding legacy AM.007 acceptance."""
    return _TOKENS_03.get(raw.lower().strip())
