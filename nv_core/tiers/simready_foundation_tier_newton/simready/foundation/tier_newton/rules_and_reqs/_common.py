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

"""Tier-local validator helpers for the Newton tier.

These small, generic helpers are duplicated from the Core tier's shared
validators so the Newton validators carry **no import dependency** on
``simready-foundation-tier-core`` (see the tier-newton extraction proposal).
Keep them in sync with their Core originals if those change.
"""

from __future__ import annotations

import math

from pxr import Usd


def _applied_api_schemas(prim: Usd.Prim) -> set[str]:
    """All applied API schema names on ``prim`` (authored + composed opinions).

    Duplicated from tier-core ``physics_bodies`` validators.
    """
    schemas = {str(schema) for schema in prim.GetAppliedSchemas()}
    op = prim.GetMetadata("apiSchemas")
    if op is None:
        return schemas
    for items in (
        op.explicitItems,
        op.prependedItems,
        op.appendedItems,
        op.addedItems,
        op.orderedItems,
    ):
        schemas.update(str(schema) for schema in items)
    return schemas


def _has_applied_api_schema(prim: Usd.Prim, schema_name: str) -> bool:
    """True if ``schema_name`` is applied on ``prim``. Duplicated from tier-core."""
    return schema_name in _applied_api_schemas(prim)


def _as_float(value) -> float | None:
    """Coerce ``value`` to a finite float, or ``None``. Duplicated from tier-core."""
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _authored_value(prim: Usd.Prim, attr_name: str):
    """Authored value of ``attr_name`` on ``prim``, or ``None``. Duplicated from tier-core."""
    attr = prim.GetAttribute(attr_name)
    if not attr.IsValid() or not attr.HasAuthoredValueOpinion():
        return None
    return attr.Get()


def _as_finite_float(value) -> float | None:
    """Coerce ``value`` to a finite float, or ``None``. Duplicated from tier-core.

    Equivalent to :func:`_as_float`; kept as a separate name so moved validators
    match their tier-core originals verbatim.
    """
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def _has_authored_attr(prim: Usd.Prim, attr_name: str) -> bool:
    """True if ``attr_name`` is authored on ``prim``. Duplicated from tier-core."""
    attr = prim.GetAttribute(attr_name)
    return attr.IsValid() and attr.HasAuthoredValueOpinion()
