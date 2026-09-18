# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Loader for the open dataset taxonomies bundled with this capability.

Each taxonomy is a single ``taxonomies/<slug>.json`` data file (data kept out of the validator code so
adding a new taxonomy is "drop in a JSON file"). This module turns one of those files into the two
lookups the membership checker needs:

- ``canonical``: the set of exact canonical label names. A value in this set is accepted silently.
- ``lookup``: a normalized-form -> canonical-name map built from each label's ``name``, ``display_name``
  and ``aliases``. A value that only matches here (different case, spacing, or an alias/display name) is
  accepted with a warning suggesting the canonical name.

Normalization is intentionally lenient: lowercase, trim, and treat ``_``/``-`` as spaces with collapsed
whitespace, so ``"Traffic_Light"`` resolves to the canonical ``"traffic light"``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_log = logging.getLogger(__name__)

_TAXONOMIES_DIR = Path(__file__).parent / "taxonomies"
_WS_RE = re.compile(r"[\s_\-]+")


def normalize(value: str) -> str:
    """Lenient, case/spacing-insensitive normal form used to match a value to a canonical label."""
    return _WS_RE.sub(" ", value.strip().lower())


@dataclass(frozen=True)
class Taxonomy:
    slug: str
    name: str
    version: str
    canonical: frozenset[str]
    lookup: dict[str, str]

    def resolve(self, value: str) -> tuple[str, str | None]:
        """Classify ``value`` against this taxonomy.

        Returns ``(status, canonical)`` where status is:
        - ``"exact"``   -> value is an exact canonical name (canonical is the value),
        - ``"alias"``   -> value matched only after normalization / via an alias (canonical suggested),
        - ``"unknown"`` -> value is not a member of this taxonomy (canonical is None).
        """
        if value in self.canonical:
            return "exact", value
        canonical = self.lookup.get(normalize(value))
        if canonical is not None:
            return "alias", canonical
        return "unknown", None


@lru_cache(maxsize=None)
def load_taxonomy(slug: str) -> Taxonomy:
    """Load and cache the taxonomy for ``slug`` (the ``SemanticsLabelsAPI`` instance name)."""
    data = json.loads((_TAXONOMIES_DIR / f"{slug}.json").read_text(encoding="utf-8"))

    canonical: set[str] = set()
    lookup: dict[str, str] = {}
    seen_names: dict[str, int] = {}
    seen_normalized: dict[str, str] = {}
    collisions: list[str] = []

    for entry in data.get("labels", []):
        name = entry.get("name")
        if not name:
            continue

        # A taxonomy keyed on ``name`` can only distinguish classes that have distinct names.
        # Two entries sharing one -- exactly, or after normalization -- collapse into a single
        # canonical value, so the checker accepts a label that cannot say which class it means.
        # Collected and warned about below rather than raised: membership is still a true
        # statement about a colliding label, and refusing to load would take a whole taxonomy
        # out of service over a handful of classes.
        if name in seen_names:
            collisions.append(f"{name!r} appears more than once")
        seen_names[name] = seen_names.get(name, 0) + 1

        norm = normalize(name)
        if norm in seen_normalized and seen_normalized[norm] != name:
            collisions.append(f"{name!r} and {seen_normalized[norm]!r} normalize to {norm!r}")
        seen_normalized.setdefault(norm, name)

        canonical.add(name)
        # First writer wins for a given normalized form so the canonical ``name`` is preferred as the
        # suggested spelling over a display name or alias that normalizes to the same thing.
        for surface in (name, entry.get("display_name"), *(entry.get("aliases") or [])):
            if not surface:
                continue
            lookup.setdefault(normalize(surface), name)

    if collisions:
        _log.warning(
            "taxonomy %r has %d label collision(s), so those classes cannot be told apart by "
            "label alone: %s. Membership still validates -- a colliding label is a real member of "
            "the vocabulary -- but it does not identify which class it means. Give each class a "
            "unique canonical name, preferring the dataset's own stable identifier, and move the "
            "ambiguous human-readable form to display_name or aliases.",
            slug,
            len(collisions),
            "; ".join(sorted(set(collisions))),
        )

    return Taxonomy(
        slug=slug,
        name=data.get("taxonomy_name", slug),
        version=str(data.get("taxonomy_version", "")),
        canonical=frozenset(canonical),
        lookup=lookup,
    )
