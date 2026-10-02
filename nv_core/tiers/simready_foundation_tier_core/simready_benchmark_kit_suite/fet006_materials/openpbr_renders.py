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
"""FET006 OpenPBR Renders (VM.PBR.001 -- OpenPBR final surface).

WHAT: How much of the asset a viewer sees is shaded by the OpenPBR surfaces it
      authored on ``outputs:mtlx:surface``.

HOW:  Two renders, both with Kit's render-context list pinned to ``["mtlx"]``,
      differing only in the strength of one binding. A flat magenta control
      material bound on the asset root ``strongerThanDescendants`` wins
      everywhere, so every pixel the asset draws comes back magenta: that is the
      silhouette. Bound ``weakerThanDescendants``, any binding the asset
      authored wins instead, and magenta is left only where the asset binds
      nothing. Coverage is ``1 - uncovered / silhouette``.

WHY:  The pin names one context and the measurement reads no other, so the
      result does not depend on what the asset authored for MDL or for the
      universal context. An earlier shape rendered ``["mtlx"]`` against ``[""]``
      and required the frames to differ, which made the verdict depend on
      ``FET_006_STANDARD``: an asset whose preview surface was a faithful
      stand-in for its OpenPBR one converged and failed.

      Nothing here is compared against a colour the renderer chose. The
      control's magenta is authored and it has a surface on all three
      contexts, so it resolves under whichever list is pinned.

PASS: The asset's own materials shade at least ``min_material_coverage`` of its
      silhouette under ``["mtlx"]``.
FAIL: They shade less than that, so the remainder resolves no material of the
      asset's at all.

ALSO: whether the materials evaluated, which the pixels cannot answer -- a
      shader that fails to resolve still wins over the weakly bound control and
      counts as covered. With
      ``--/persistent/app/material/materialx/validate=true`` Kit logs
      ``[Error] [rtx.materialx.plugin] Unable to create document for material:
      '<path>'`` per material it could not build, and this test fails on any
      under the asset root. The setting is read at startup, so a run without it
      reports that the question went unanswered. MaterialX is the only context
      Kit reports this for.

LIMIT: The pin decides which surface a covered pixel is shaded by, not what
  counts as covered. A material with no ``outputs:mtlx:surface`` falls back to
  its universal one and still wins over the control, so it reads as covered.
  ``VM.PBR.001`` is what requires the surface to be there.

  Presence is the validator's: ``VM.PBR.001`` requires the surface to exist and
  resolve and ``VM.PBR.003`` requires its ``info:id`` to name a declared node,
  and both run ahead of this benchmark.
"""

from simready_benchmark.core.decorator import test

from simready_benchmark_kit_suite.fet006_materials import _scene, _surface_test, surfaces


@test(
    features=[{"id": "FET_006_OPENPBR", "version": ">=0.1.0"}],
    name="openpbr_renders",
    description=(
        "Renders the asset twice with Kit's render-context list pinned to "
        "[mtlx], once with a flat magenta control material bound over it "
        "strongerThanDescendants and once weakerThanDescendants, and requires "
        "the asset's own materials to shade most of its silhouette. The two "
        "frames differ only in the strength of that one binding, so what is "
        "left magenta is geometry the asset binds no OpenPBR surface to. The "
        "material network under test is left exactly as authored. Also reads "
        "the Kit log for materials whose MaterialX document could not be built, "
        "which the pixels cannot show."
    ),
    expected_video=(
        "The asset in a mid grey room shaded by its OpenPBR surface, then the "
        "same frame with a flat magenta control bound underneath the asset's "
        "own bindings. Magenta showing through is geometry that resolves no "
        "material of the asset's under the mtlx render context."
    ),
    version="0.4.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(_scene.SCENE_DEFAULTS),
)
async def test_openpbr_renders(ctx):
    """The asset's OpenPBR surfaces must shade what the asset draws."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.MTLX,
        requirement="VM.PBR.001",
        fix_hint=(
            "- Check the material connects an OpenPBR surface to "
            "outputs:mtlx:surface, and that it connects to the nodedef's "
            "declared output, which is 'out' rather than 'surface'."
        ),
        # MaterialX is the one context Kit reports evaluation for. There is no
        # equivalent switch for MDL or for UsdPreviewSurface.
        read_materialx_log=True,
    )
