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

"""FET006 Preview Surface Renders (VM.MAT.001 -- rendered material coverage with the universal context).

WHAT: Measures bound-material pixel coverage with the universal context
      selected. The pixel ratio does not establish successful UsdPreviewSurface
      evaluation, correct networks, textures or appearance. Registered under
      FET006_Materials and FET009_MaterialCoverage; one run counts
      toward both.

HOW:  Three probe renders request the universal context. A strong magenta
      control on a test-owned enclosing ancestor supplies the silhouette. Weak
      magenta and cyan controls preserve authored root/descendant bindings;
      only silhouette pixels following both colors count as uncovered. Coverage
      is ``1 - uncovered / silhouette``, not binding identity or proof of
      successful shader evaluation. Source layers are unchanged.

WHY:  UsdPreviewSurface is the portable baseline: the surface any renderer falls
      back to when it cannot evaluate MDL or MaterialX. That guarantee is only
      worth something if the fallback draws over the whole object, and on an
      asset that also declares MDL and OpenPBR it is the surface least likely to
      be exercised, because Kit's shipped order reaches it last.

      The three tests in this family use the same probe shape with one context
      requested per test, not a gate comparing separately pinned contexts.
      The MDL/MaterialX probes can still render universal fallback surfaces.
      Nothing is compared against a colour the
      renderer chose: the control's magenta is authored, and it has a
      surface on all three contexts so it resolves under whichever list is
      pinned.

PASS: Measured bound-material coverage reaches ``min_material_coverage`` with
      the universal context selected.
FAIL: The coverage gate is not met. Inspect setup and the probe images before
      assigning a binding or shader defect.

NO GEOMETRY: A material published on its own has each of its materials
      rendered on a test sphere with the universal context selected. Only the
      strong pass runs, and coverage is not measured, because the test binds
      every sphere itself. The reported frame shows each material as Kit
      renders it. The run passes once the spheres render; nothing on them is
      compared.

LIMIT: A pixel is uncovered when the geometry under it resolves no material of
  the asset's at all. ``VM.PS.002`` (from ``FET006_Materials`` 0-2-0) is
  what requires the UsdPreviewSurface itself to be there; the universal context has nothing beneath it in USD's
  resolution chain, so on this one test a material that reaches it has no
  fallback left.

  Whether a bound material *evaluated* is not visible here either -- a shader that
  fails to resolve still wins over the weak control and counts as covered. The
  MaterialX validation switch that logs such a failure does not cover
  UsdPreviewSurface.

  Presence is the validator's: ``VM.PS.002`` requires the material a renderable
  Gprim renders with to connect a UsdPreviewSurface, and
  ``com.nvidia.usd.VM.PS.001`` checks its inputs. Normal planning consumes prior
  validation evidence; it does not run these validators inside the test. ``--features`` diagnostics can
  bypass absent or failed validation, so a benchmark pass does not establish it.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet006_materials import (
    _scene,
    _surface_test,
    surfaces,
)

CONFIG = dict(_scene.SCENE_DEFAULTS)


@test(
    features=[
        {"id": "FET006_Materials.0-1-0", "version": "*"},
        {"id": "FET006_Materials.0-2-0", "version": "*"},
        {"id": "FET006_Materials.0-3-0", "version": "*"},
        {"id": "FET009_MaterialCoverage.0-1-0", "version": "*"},
    ],
    name="preview_surface_renders",
    description=(
        "Requests the universal context for a strong magenta silhouette and weak "
        "magenta/cyan controls on a test-owned enclosing ancestor, preserving "
        "authored root and descendant bindings. Pixels following both weak "
        "colors within the silhouette form the uncovered proxy. UsdPreviewSurface "
        "is the surface a renderer falls back to "
        "when it cannot evaluate MDL or MaterialX, and on an asset that "
        "declares all three it is the one least likely to be exercised. A valid "
        "colored asset surface alone no longer matches both weak controls; "
        "coverage remains a color proxy, not proof of shader evaluation. An asset "
        "with no geometry has each material rendered on a test sphere instead, "
        "without a coverage measurement."
    ),
    expected_video=(
        "The asset as authored with the universal context selected; the same view with a "
        "strong magenta control, where every pixel the asset draws is magenta by design; "
        "then two frames from separate stages with weak magenta and weak cyan controls. "
        "In the weak frames a fully covered asset shows its own materials, and control "
        "color marks geometry that resolves no material from the asset's own bindings. "
        "An asset material that is itself magenta or cyan matches the control in one "
        "weak frame. An asset with no geometry shows its materials on test spheres, "
        "then the spheres in strong magenta, and has no weak frames."
    ),
    version="0.5.1",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(CONFIG),
)
async def test_preview_surface_renders(ctx):
    """Measure bound-material coverage with the universal context selected."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.UNIVERSAL,
        requirement="VM.MAT.001",
        fix_hint=_surface_test.BINDING_FIX_HINT,
    )
