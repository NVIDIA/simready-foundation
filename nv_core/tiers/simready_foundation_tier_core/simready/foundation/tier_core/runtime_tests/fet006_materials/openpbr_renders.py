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

"""FET006 OpenPBR Renders (VM.MAT.001 -- rendered material coverage with the mtlx context).

WHAT: Measures bound-material pixel coverage with ``["mtlx"]`` selected.
      A universal fallback or failed shader can still count as covered; the
      pixel ratio does not establish OpenPBR evaluation or appearance quality.
      Registered under FET006_Materials.Openpbr and FET009_MaterialCoverage;
      one run counts toward both.

HOW:  Three probe renders request ``["mtlx"]``. A strong magenta control on a
      test-owned enclosing ancestor supplies the silhouette. Weak magenta and
      cyan controls preserve the asset's root and descendant bindings; only
      silhouette pixels following both colors count as uncovered. Coverage is
      ``1 - uncovered / silhouette``, a color proxy, not binding identity or
      proof of successful shader evaluation. Source layers are unchanged.

WHY:  All probe passes use the same requested context; there is no gate that
      requires an appearance difference from a separately pinned context.
      Universal fallback can still affect the rendered pixels. An earlier
      shape rendered ``["mtlx"]`` against ``[""]``
      and required the frames to differ, which made the verdict depend on
      ``FET_006_STANDARD``: an asset whose preview surface was a faithful
      stand-in for its OpenPBR one converged and failed.

      Nothing here is compared against a colour the renderer chose. The
      control's magenta is authored and it has a surface on all three
      contexts, so it resolves under whichever list is pinned.

PASS: Measured bound-material coverage reaches ``min_material_coverage`` with
      ``["mtlx"]`` selected, and no scoped MaterialX error is captured when
      that optional log check is enabled.
FAIL: The coverage gate is not met, or an enabled log check captures a scoped
      material-document error. Inspect setup and evidence before assigning cause.
SKIP: No material that renderable geometry resolves at the ``full`` purpose
      declares an OpenPBR surface. Kit would render each material's universal
      surface in its place, which ``preview_surface_renders`` already measures.
      FET006_Materials.Openpbr is optional wherever a profile selects it;
      VM.PBR.001 reports an OpenPBR surface the asset is meant to have and lacks.

NO GEOMETRY: A material published on its own has each of its materials
      rendered on a test sphere with ``["mtlx"]`` selected. Only the strong
      pass runs, and coverage is not measured, because the test binds every
      sphere itself. SKIP reads the materials the asset publishes. The
      MaterialX log check below still applies, and it is the only part of the
      run that can fail a material asset.

ALSO: available MaterialX log diagnostics, which the pixels cannot answer -- a
      shader that fails to resolve still wins over the weakly bound control and
      counts as covered. With
      ``--/persistent/app/material/materialx/validate=true`` Kit logs
      ``[Error] [rtx.materialx.plugin] Unable to create document for material:
      '<path>'`` per material it could not build, and this test fails on any
      under the asset root. Absence of a captured error does not prove every
      material built successfully or that the log monitor was available.
      The setting is read at startup, so a run without it reports that the
      question went unanswered. MaterialX is the only context Kit reports this for.

LIMIT: The pin requests a surface context, but does not verify what evaluated
  for each pixel. A material with no ``outputs:mtlx:surface`` falls back to
  its universal one and still wins over the control, so it reads as covered.
  ``VM.PBR.001`` is what requires the surface to be there.

  Presence is the validator's: ``VM.PBR.001`` requires the surface to exist and
  resolve and ``VM.PBR.003`` requires its ``info:id`` to name a declared node.
  Normal planning consumes prior validation evidence; it does not run these
  validators inside this test. ``--features`` diagnostics can bypass absent or
  failed validation, so a benchmark pass is not a substitute for those checks.
"""

from simready.evaluate.core.decorator import test
from simready.foundation.tier_core.runtime_tests.fet006_materials import (
    _scene,
    _surface_test,
    surfaces,
)


@test(
    features=[
        {"id": "FET006_Materials.Openpbr.0-1-0", "version": "*"},
        {"id": "FET006_Materials.Openpbr.0-2-0", "version": "*"},
        {"id": "FET009_MaterialCoverage.0-1-0", "version": "*"},
    ],
    name="openpbr_renders",
    description=(
        "Requests [mtlx] for a strong magenta silhouette and weak magenta/cyan "
        "controls on a test-owned enclosing ancestor, preserving authored root "
        "and descendant bindings. Pixels following both weak colors within the "
        "silhouette form the uncovered proxy; the configured coverage must pass. Coverage "
        "alone does not prove OpenPBR evaluation: bound materials can fall "
        "back to a universal surface or fail evaluation. The "
        "material network under test is left exactly as authored. Also reads "
        "the Kit log for materials whose MaterialX document could not be built, "
        "which the pixels cannot show. Skips an asset with no OpenPBR surface on the "
        "materials its geometry resolves. An asset with no geometry has each material "
        "rendered on a test sphere instead, without a coverage measurement."
    ),
    expected_video=(
        "The asset as authored with the mtlx context selected; the same view with a "
        "strong magenta control, where every pixel the asset draws is magenta by design; "
        "then two frames from separate stages with weak magenta and weak cyan controls. "
        "In the weak frames a fully covered asset shows its own materials, and control "
        "color marks geometry that resolves no material from the asset's own bindings. "
        "An asset material that is itself magenta or cyan matches the control in one "
        "weak frame. A skipped run keeps only the first two frames. An asset with no "
        "geometry shows its materials on test spheres, then the spheres in strong "
        "magenta, and has no weak frames."
    ),
    version="0.5.1",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(_scene.SCENE_DEFAULTS),
)
async def test_openpbr_renders(ctx):
    """Measure material coverage and available MaterialX log diagnostics."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.MTLX,
        requirement="VM.MAT.001",
        fix_hint=_surface_test.BINDING_FIX_HINT,
        owning_feature="FET006_Materials.Openpbr",
        # MaterialX is the one context Kit reports evaluation for. There is no
        # equivalent switch for MDL or for UsdPreviewSurface.
        read_materialx_log=True,
    )
