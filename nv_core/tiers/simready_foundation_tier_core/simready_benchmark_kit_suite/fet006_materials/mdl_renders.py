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
"""FET006 MDL Renders (VM.MDL.001 -- MDL final surface).

WHAT: How much of the asset a viewer sees is shaded by the MDL surfaces it
      authored on ``outputs:mdl:surface``.

HOW:  Two renders, both with Kit's render-context list pinned to ``["mdl"]``,
      differing only in the strength of one binding. A flat magenta control
      material bound on the asset root ``strongerThanDescendants`` wins
      everywhere, so every pixel the asset draws comes back magenta: that is the
      silhouette. Bound ``weakerThanDescendants``, any binding the asset
      authored wins instead, and magenta is left only where the asset binds
      nothing. Coverage is ``1 - uncovered / silhouette``.

WHY:  The pin names one context and the measurement reads no other, so the
      result does not depend on what the asset authored for MaterialX or for the
      universal context. An earlier shape rendered ``["mdl"]`` against ``[""]``
      and required the frames to differ, which made the verdict depend on
      ``FET_006_STANDARD``: a UsdPreviewSurface is usually baked down from the
      MDL surface it stands in for, so the two converged and the asset failed.

      Nothing here is compared against a colour the renderer chose. The
      control's magenta is authored and it has a surface on all three
      contexts, so it resolves under whichever list is pinned.

PASS: The asset's own materials shade at least ``min_material_coverage`` of its
      silhouette under ``["mdl"]``.
FAIL: They shade less than that, so the remainder resolves no material of the
      asset's at all.

LIMIT: The pin decides which surface a covered pixel is shaded by, not what
  counts as covered. A material with no ``outputs:mdl:surface`` falls back to
  its universal one and still wins over the control, so it reads as covered.
  ``VM.MDL.001`` is what requires the surface to be there.

  Whether a bound material *evaluated* is not visible here either -- a shader that
  fails to resolve still wins over the weak control and counts as covered. The
  MaterialX validation switch that logs such a failure does not cover MDL.

  Presence is the validator's: ``VM.MDL.001`` requires the surface to exist and
  resolve, and it runs ahead of this benchmark.
"""

from simready_benchmark.core.decorator import test

from simready_benchmark_kit_suite.fet006_materials import _scene, _surface_test, surfaces


@test(
    features=[{"id": "FET_006_MDL", "version": ">=0.1.0"}],
    name="mdl_renders",
    description=(
        "Renders the asset twice with Kit's render-context list pinned to "
        "[mdl], once with a flat magenta control material bound over it "
        "strongerThanDescendants and once weakerThanDescendants, and requires "
        "the asset's own materials to shade most of its silhouette. The two "
        "frames differ only in the strength of that one binding, so what is "
        "left magenta is geometry the asset binds no MDL surface to. The "
        "material network under test is left exactly as authored."
    ),
    expected_video=(
        "The asset in a mid grey room shaded by its MDL surface, normally its "
        "full textured appearance, then the same frame with a flat magenta "
        "control bound underneath the asset's own bindings. Magenta showing "
        "through is geometry that resolves no material of the asset's under "
        "the mdl render context."
    ),
    version="0.3.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(_scene.SCENE_DEFAULTS),
)
async def test_mdl_renders(ctx):
    """The asset's MDL surfaces must shade what the asset draws."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.MDL,
        requirement="VM.MDL.001",
        fix_hint=(
            "- Check info:mdl:sourceAsset names a .mdl file that exists and "
            "that info:mdl:sourceAsset:subIdentifier names a material in it."
        ),
    )
