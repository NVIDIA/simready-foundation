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

"""FET006 MDL Renders (VM.MAT.001 -- rendered material coverage with the mdl context).

WHAT: Measures bound-material pixel coverage with ``["mdl"]`` selected.
      A universal fallback or failed shader can still count as covered; the
      pixel ratio does not establish MDL evaluation or appearance quality.
      Registered under FET006_Materials.MDL and FET009_MaterialCoverage; one
      run counts toward both.

HOW:  Three probe renders request ``["mdl"]``. A strong magenta control on a
      test-owned enclosing ancestor supplies the silhouette. Weak magenta and
      cyan controls preserve the asset's root and descendant bindings; only
      silhouette pixels following both colors count as uncovered. Coverage is
      ``1 - uncovered / silhouette``, a color proxy, not binding identity or
      proof of successful shader evaluation. Source layers are unchanged.

WHY:  All probe passes use the same requested context; there is no gate that
      requires an appearance difference from a separately pinned context.
      Universal fallback can still affect the rendered pixels. An earlier
      shape rendered ``["mdl"]`` against ``[""]``
      and required the frames to differ, which made the verdict depend on
      ``FET_006_STANDARD``: a UsdPreviewSurface is usually baked down from the
      MDL surface it stands in for, so the two converged and the asset failed.

      Nothing here is compared against a colour the renderer chose. The
      control's magenta is authored and it has a surface on all three
      contexts, so it resolves under whichever list is pinned.

PASS: Measured bound-material coverage reaches ``min_material_coverage`` with
      ``["mdl"]`` selected.
FAIL: The coverage gate is not met. Inspect setup and the probe images before
      assigning a binding or shader defect.
SKIP: No material that renderable geometry resolves at the ``full`` purpose
      declares an MDL surface. Kit would render each material's universal
      surface in its place, which ``preview_surface_renders`` already measures.
      FET006_Materials.MDL is optional wherever a profile selects it;
      VM.MDL.003 reports an MDL surface the asset is meant to have and lacks.

NO GEOMETRY: A material published on its own has each of its materials
      rendered on a test sphere with ``["mdl"]`` selected. Only the strong
      pass runs, and coverage is not measured, because the test binds every
      sphere itself. SKIP reads the materials the asset publishes. The
      reported frame shows each MDL surface as Kit renders it. The run passes
      once the spheres render; nothing on them is compared.

LIMIT: The pin requests a surface context, but does not verify what evaluated
  for each pixel. A material with no ``outputs:mdl:surface`` falls back to
  its universal one and still wins over the control, so it reads as covered.
  ``VM.MDL.003`` is what requires the surface to be there.

  Whether a bound material *evaluated* is not visible here either -- a shader that
  fails to resolve still wins over the weak control and counts as covered. The
  MaterialX validation switch that logs such a failure does not cover MDL.

  Presence is the validator's: ``VM.MDL.003`` requires the material a renderable
  Gprim renders with to connect an MDL surface, and ``VM.MDL.001`` requires its
  source asset to name an existing ``.mdl`` file. Normal planning consumes prior
  validation evidence; it does not run these validators inside the test. ``--features`` diagnostics can bypass absent
  or failed validation, so a benchmark pass does not establish that requirement.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet006_materials import (
    _scene,
    _surface_test,
    surfaces,
)


@test(
    features=[
        {"id": "FET006_Materials.MDL.0-1-0", "version": "*"},
        {"id": "FET006_Materials.MDL.0-2-0", "version": "*"},
        {"id": "FET006_Materials.MDL.0-3-0", "version": "*"},
        {"id": "FET009_MaterialCoverage.0-1-0", "version": "*"},
    ],
    name="mdl_renders",
    description=(
        "Requests [mdl] for a strong magenta silhouette and weak magenta/cyan "
        "controls on a test-owned enclosing ancestor, preserving authored root "
        "and descendant bindings. Pixels following both weak colors within the "
        "silhouette form the uncovered proxy; the configured coverage must pass. A bound "
        "material can use a universal fallback or fail evaluation and still "
        "count as covered; the pixel gate does not prove MDL evaluation. "
        "The material network under test is left exactly as authored. Skips an "
        "asset with no MDL surface on the materials its geometry resolves. An asset "
        "with no geometry has each material rendered on a test sphere instead, "
        "without a coverage measurement."
    ),
    expected_video=(
        "The asset as authored with the mdl context selected; the same view with a "
        "strong magenta control, where every pixel the asset draws is magenta by design; "
        "then two frames from separate stages with weak magenta and weak cyan controls. "
        "In the weak frames a fully covered asset shows its own materials, and control "
        "color marks geometry that resolves no material from the asset's own bindings. "
        "An asset material that is itself magenta or cyan matches the control in one "
        "weak frame. A skipped run keeps only the first two frames. An asset with no "
        "geometry shows its materials on test spheres, then the spheres in strong "
        "magenta, and has no weak frames."
    ),
    version="0.4.1",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(_scene.SCENE_DEFAULTS),
)
async def test_mdl_renders(ctx):
    """Measure bound-material pixel coverage with the mdl context selected."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.MDL,
        requirement="VM.MAT.001",
        fix_hint=_surface_test.BINDING_FIX_HINT,
        owning_feature="FET006_Materials.MDL",
    )
