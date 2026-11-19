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

Adding an equipment class is adding a file. No validator changes, no requirement
code, no feature JSON edit.
"""
import json
from pathlib import Path
from typing import Optional

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _check(condition: bool, filename: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{filename}: {message}")


def _validate(doc: dict, filename: str) -> None:
    """Check one class definition before anything indexes into it.

    Every field is read at module scope, so an unchecked shape surfaces as a
    bare KeyError during plugin startup rather than as a message naming the
    file. A wrong JSON type is worse than a missing key: `"attributes"` given
    as a string makes frozenset() yield one entry per character, and every
    asset of that class then fails AM.007 against nonsense.
    """
    for key in ("class", "displayName", "assetClassTokens", "attributes",
                "thermalCooling", "electricalAC"):
        _check(key in doc, filename, f"missing required key '{key}'")

    _check(isinstance(doc["class"], str) and doc["class"], filename, "'class' must be a non-empty string")
    _check(isinstance(doc["displayName"], str), filename, "'displayName' must be a string")

    tokens = doc["assetClassTokens"]
    _check(isinstance(tokens, list) and tokens, filename,
           "'assetClassTokens' must be a non-empty list of strings, not "
           f"{type(tokens).__name__}")
    _check(all(isinstance(t, str) and t.strip() for t in tokens), filename,
           "every entry in 'assetClassTokens' must be a non-empty string")

    attributes = doc["attributes"]
    _check(isinstance(attributes, list) and attributes, filename,
           "'attributes' must be a non-empty list of attribute names, not "
           f"{type(attributes).__name__}")
    _check(all(isinstance(a, str) and a.startswith("aif:spec:") for a in attributes), filename,
           "every entry in 'attributes' must be an 'aif:spec:*' name")

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


def _load() -> dict:
    classes = {}
    for path in sorted(_CONFIG_DIR.glob("aif-equipment-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}: not valid JSON -- {exc}") from exc
        _check(isinstance(doc, dict), path.name, "must hold a JSON object")
        _validate(doc, path.name)
        key = doc["class"]
        if key in classes:
            raise ValueError(f"duplicate equipment class '{key}' in {path.name}")
        classes[key] = doc
    if not classes:
        raise ValueError(f"no equipment class definitions found in {_CONFIG_DIR}")
    return classes


_CLASSES = _load()

# class -> the aif:spec:* attributes an asset of that class must carry (AM.007).
ATTRIBUTES = {k: frozenset(v["attributes"]) for k, v in _CLASSES.items()}

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


def normalize(raw: str) -> Optional[str]:
    """Resolve an authored ``aif:core:assetClass`` value to a class, or None."""
    return _TOKENS.get(raw.lower().strip())
