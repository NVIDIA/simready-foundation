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
"""FET006 Preview Surface Renders (com.nvidia.usd.VM.PS.001 -- UsdPreviewSurface conformance).

WHAT: How much of the asset a viewer sees is shaded by the UsdPreviewSurfaces it
      authored on the universal ``outputs:surface``.

HOW:  Two renders, both with Kit's render-context list pinned to the universal
      context alone, differing only in the strength of one binding. A flat
      magenta control material bound on the asset root
      ``strongerThanDescendants`` wins everywhere, so every pixel the asset
      draws comes back magenta: that is the silhouette. Bound
      ``weakerThanDescendants``, any binding the asset authored wins instead,
      and magenta is left only where the asset binds nothing. Coverage is
      ``1 - uncovered / silhouette``.

WHY:  UsdPreviewSurface is the portable baseline: the surface any renderer falls
      back to when it cannot evaluate MDL or MaterialX. That guarantee is only
      worth something if the fallback draws over the whole object, and on an
      asset that also declares MDL and OpenPBR it is the surface least likely to
      be exercised, because Kit's shipped order reaches it last.

      The three tests in this family are the same shape, each pinned to its own
      context and reading no other. Nothing is compared against a colour the
      renderer chose: the control's magenta is authored, and it has a
      surface on all three contexts so it resolves under whichever list is
      pinned.

PASS: The asset's own materials shade at least ``min_material_coverage`` of its
      silhouette under the universal context.
FAIL: They shade less than that, so the remainder resolves no material of the
      asset's at all -- in a viewer with no MDL or MaterialX support, that part
      of the object is the renderer's default material.

LIMIT: A pixel is uncovered when the geometry under it resolves no material of
  the asset's at all. ``com.nvidia.usd.VM.PS.001`` is what requires the UsdPreviewSurface
  itself to be there; the universal context has nothing beneath it in USD's
  resolution chain, so on this one test a material that reaches it has no
  fallback left.

  Whether a bound material *evaluated* is not visible here either -- a shader that
  fails to resolve still wins over the weak control and counts as covered. The
  MaterialX validation switch that logs such a failure does not cover
  UsdPreviewSurface.

  Presence is the validator's: ``com.nvidia.usd.VM.PS.001`` requires the surface to exist and
  resolve, and it runs ahead of this benchmark.
"""

from simready_benchmark.core.decorator import test

from simready_benchmark_kit_suite.fet006_materials import _scene, _surface_test, surfaces

CONFIG = dict(_scene.SCENE_DEFAULTS)


@test(
    features=[{"id": "FET_006_STANDARD", "version": ">=0.1.0"}],
    name="preview_surface_renders",
    description=(
        "Renders the asset twice with Kit's render-context list pinned to the "
        "universal context alone, once with a flat magenta control material "
        "bound over it strongerThanDescendants and once weakerThanDescendants, "
        "and requires the asset's own materials to shade most of its "
        "silhouette. UsdPreviewSurface is the surface a renderer falls back to "
        "when it cannot evaluate MDL or MaterialX, and on an asset that "
        "declares all three it is the one least likely to be exercised."
    ),
    expected_video=(
        "The asset in a mid grey room shaded by its UsdPreviewSurface. This is "
        "the low-fidelity representation and is expected to look simpler than "
        "the MDL or OpenPBR one. Then the same frame with a flat magenta "
        "control bound underneath the asset's own bindings: magenta showing "
        "through is geometry that resolves no UsdPreviewSurface, and is what a "
        "viewer without MDL or MaterialX support draws on its default "
        "material."
    ),
    version="0.4.0",
    engine={"tags": ["kit"], "version": ">=2024.2.0"},
    config_defaults=dict(CONFIG),
)
async def test_preview_surface_renders(ctx):
    """The asset's UsdPreviewSurfaces must shade what the asset draws."""
    await _surface_test.run_coverage_test(
        ctx,
        context=surfaces.UNIVERSAL,
        requirement="com.nvidia.usd.VM.PS.001",
        fix_hint=(
            "- Check the material connects a UsdPreviewSurface shader to the "
            "universal outputs:surface, and that the shader uses only "
            "spec-defined UsdPreviewSurface inputs and types."
        ),
    )
