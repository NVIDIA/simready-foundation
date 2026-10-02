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
"""Fixture tests for the Display Color capability checker.

``validate_sample_content.py`` compares each sample asset's per-feature result against the
same asset's result on ``main``, so it reports regressions in features that exist on both
branches. A feature introduced on a branch has no result on ``main`` to regress from, and its
requirements are only exercised at all once a profile adopts it. FET_010_STANDARD is not
in any profile yet, so nothing there reaches DISP.001, DISP.002 or DISP.003. These tests drive the
checker directly against small stages instead, and do not depend on either.

Run with::

    pip install 'simready-validate>=2026.7.0.dev1' usd-validation-nvidia numpy pytest
    pytest nv_core/tiers/simready_foundation_tier_core/tests/test_display_color_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdGeom

TIER = Path(__file__).resolve().parent.parent / "simready" / "foundation" / "tier_core"

# ``simready.validate`` loads a capabilities tree by putting its parent on ``sys.path`` and
# importing the directory name, so a path-loaded tier's validators land under a top-level
# ``capabilities`` package. An installed tier wheel is imported by its dotted name instead.
CHECKER_MODULES = (
    "capabilities.visualization.display_color.validation",
    "simready.foundation.tier_core.capabilities.visualization.display_color.validation",
)


@pytest.fixture(scope="session")
def checker_class():
    """Load the tier's capabilities and hand back the display colour checker.

    ``simready.validate.initialize`` is what generates the tier's requirements module and
    imports every ``validation.py`` under its capabilities tree, so the checker is only
    importable after it has run. Profiles are loaded because initialize wants them, not
    because any of them reference this feature; none do.
    """
    simready_validate = pytest.importorskip(
        "simready.validate",
        reason="requires simready-validate>=2026.7.0.dev1, which resolves a tier's "
        "requirements module from the tier's pyproject",
    )
    simready_validate.destroy()
    simready_validate.initialize(
        rules_and_requirements_paths=[TIER / "capabilities"],
        features_paths=[TIER / "features"],
        profiles_paths=sorted((TIER / "profiles").glob("*.toml")),
    )
    for name in CHECKER_MODULES:
        module = sys.modules.get(name)
        if module is not None:
            break
    else:
        raise AssertionError(f"display colour checker not loaded; tried {CHECKER_MODULES}")
    yield module.DisplayColorCapabilityChecker
    simready_validate.destroy()


def check(checker_class, usda: str, prim_path: str) -> list[str]:
    """Run the checker over one prim of an inline stage and return its messages."""
    layer = Sdf.Layer.CreateAnonymous(".usda")
    assert layer.ImportFromString(usda), "fixture stage did not parse"
    stage = Usd.Stage.Open(layer)
    prim = stage.GetPrimAtPath(prim_path)
    assert prim, f"fixture stage has no prim at {prim_path}"
    checker = checker_class()
    checker.CheckPrim(prim)
    return [issue.message for issue in checker.GetIssues()]


def codes(checker_class, usda: str, prim_path: str) -> list[str]:
    """The requirement code of each message, for tests that only care which rule fired."""
    layer = Sdf.Layer.CreateAnonymous(".usda")
    assert layer.ImportFromString(usda), "fixture stage did not parse"
    stage = Usd.Stage.Open(layer)
    prim = stage.GetPrimAtPath(prim_path)
    checker = checker_class()
    checker.CheckPrim(prim)
    return [issue.requirement.code for issue in checker.GetIssues()]


HEADER = '#usda 1.0\n(\n    defaultPrim = "World"\n)\n\n'

QUAD = """        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
"""


def stage(body: str) -> str:
    return f'{HEADER}def Xform "World"\n{{\n{body}}}\n'


# ----------------------------------------------------------------------------------
# DISP.001 - a renderable GPrim resolves a display colour
# ----------------------------------------------------------------------------------


def test_disp_001_authored_on_the_gprim(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


def test_disp_001_inherited_from_an_ancestor(checker_class):
    usda = stage(
        f"""    def Xform "Assembly"
    {{
        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )

        def Mesh "bracket"
        {{
{QUAD}        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/Assembly/bracket") == []


def test_disp_001_absent_everywhere_is_reported(checker_class):
    usda = stage(f'    def Mesh "bracket"\n    {{\n{QUAD}    }}\n')
    assert codes(checker_class, usda, "/World/bracket") == ["com.nvidia.simready.DISP.001"]


# ----------------------------------------------------------------------------------
# DISP.002 / DISP.003 - values, and the element count the interpolation implies
# ----------------------------------------------------------------------------------


def test_component_outside_range_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(1.8, 0.4, 0.42)] (
            interpolation = "constant"
        )
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "outside [0, 1]" in messages[0]
    # A static asset's message carries no time qualifier.
    assert "at time" not in messages[0]


def test_constant_interpolation_with_two_elements_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42), (0.1, 0.1, 0.1)] (
            interpolation = "constant"
        )
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "authors 2 elements, expected 1" in messages[0]


def test_opacity_outside_range_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "window"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
            interpolation = "constant"
        )
        float[] primvars:displayOpacity = [1.5] (
            interpolation = "constant"
        )
    }}
"""
    )
    assert codes(checker_class, usda, "/World/window") == ["com.nvidia.simready.DISP.003"]


# ----------------------------------------------------------------------------------
# The declared type, wherever the primvar is authored
# ----------------------------------------------------------------------------------

TYPE_CASES = [
    ("color3d[] primvars:displayColor = [(0.4, 0.4, 0.42)]", "Vec3dArray"),
    ("half3[] primvars:displayColor = [(0.4, 0.4, 0.42)]", "Vec3hArray"),
    ("color3f primvars:displayColor = (0.4, 0.4, 0.42)", "Vec3f"),
]


@pytest.mark.parametrize("declaration,resolved", TYPE_CASES)
def test_wrong_type_on_the_gprim_is_reported(checker_class, declaration, resolved):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        {declaration} (
            interpolation = "constant"
        )
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert f"resolves to '{resolved}'" in messages[0]


@pytest.mark.parametrize("declaration,resolved", TYPE_CASES)
def test_wrong_type_on_an_ancestor_gets_the_same_answer(checker_class, declaration, resolved):
    """The GPrim takes the attribute's type name from the schema and an ancestor takes it from
    the author, so a check keyed on that name used to accept on an ancestor what it reported
    on a GPrim."""
    usda = stage(
        f"""    def Xform "Assembly"
    {{
        {declaration} (
            interpolation = "constant"
        )

        def Mesh "bracket"
        {{
{QUAD}        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/Assembly/bracket")
    assert len(messages) == 1
    assert f"resolves to '{resolved}'" in messages[0]


@pytest.mark.parametrize(
    "declaration,resolved",
    [
        ("double[] primvars:displayOpacity = [0.25]", "DoubleArray"),
        ("half[] primvars:displayOpacity = [0.25]", "HalfArray"),
        ("float primvars:displayOpacity = 0.25", "float"),
    ],
)
def test_wrong_opacity_type_is_reported(checker_class, declaration, resolved):
    usda = stage(
        f"""    def Mesh "window"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.8, 0.85, 0.9)] (
            interpolation = "constant"
        )
        {declaration} (
            interpolation = "constant"
        )
    }}
"""
    )
    messages = check(checker_class, usda, "/World/window")
    assert len(messages) == 1
    assert "UsdGeomGprim declares it as 'float[]'" in messages[0]


def test_float3_array_on_an_ancestor_is_accepted(checker_class):
    """``float3[]`` resolves to the same ``VtVec3fArray`` as ``color3f[]``; only the Sdf role
    differs, and a consumer reading the declared type gets its value."""
    usda = stage(
        f"""    def Xform "Assembly"
    {{
        float3[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )

        def Mesh "bracket"
        {{
{QUAD}        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/Assembly/bracket") == []


# ----------------------------------------------------------------------------------
# Indexed primvars, read at the time code the values resolved at
# ----------------------------------------------------------------------------------


def test_static_indexed_primvar_is_accepted(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)] (
            interpolation = "constant"
        )
        int[] primvars:displayColor:indices = [1]
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


def test_static_index_out_of_bounds_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)] (
            interpolation = "constant"
        )
        int[] primvars:displayColor:indices = [7]
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "indexes outside its 2-element value array" in messages[0]


def test_time_sampled_indexed_primvar_is_accepted(checker_class):
    """Values and indices both carry only samples. Reading the index array at the default time
    code while the values came from a sample compared them against an empty array, so this
    reported a count failure against geometry with nothing wrong with it."""
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)],
            1: [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)],
        }}
        int[] primvars:displayColor:indices.timeSamples = {{
            0: [0],
            1: [1],
        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


def test_time_sampled_index_out_of_bounds_gets_the_out_of_bounds_message(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)],
        }}
        int[] primvars:displayColor:indices.timeSamples = {{
            0: [7],
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "indexes outside its 2-element value array" in messages[0]


def test_time_sampled_vertex_indexed_primvar_is_accepted(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor (
            interpolation = "vertex"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.2, 0.3, 0.4), (0.5, 0.5, 0.5)],
        }}
        int[] primvars:displayColor:indices.timeSamples = {{
            0: [0, 1, 1, 0],
        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


# ----------------------------------------------------------------------------------
# Every value the primvar resolves, not only the first
# ----------------------------------------------------------------------------------


def test_later_sample_out_of_range_is_reported(checker_class):
    """Conforming at the default time code and at the first sample, out of range at the
    second. The shape an override layer produces."""
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.4, 0.4, 0.42)],
            5: [(0.4, 9.5, 0.42)],
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "outside [0, 1]" in messages[0]
    assert "at time 5" in messages[0]


def test_later_sample_wrong_element_count_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.4, 0.4, 0.42)],
            2: [(0.4, 0.4, 0.42), (0.1, 0.1, 0.1)],
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "authors 2 elements, expected 1" in messages[0]
    assert "at time 2" in messages[0]


def test_later_opacity_sample_out_of_range_is_reported(checker_class):
    usda = stage(
        f"""    def Mesh "window"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
        float[] primvars:displayOpacity = [1.0] (
            interpolation = "constant"
        )
        float[] primvars:displayOpacity.timeSamples = {{
            0: [1.0],
            4: [-0.5],
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/window")
    assert len(messages) == 1
    assert "outside [0, 1]" in messages[0]
    assert "at time 4" in messages[0]


def test_a_failure_at_every_sample_is_reported_once(checker_class):
    samples = ",\n            ".join(f"{t}: [(2.0, 0.4, 0.42)]" for t in range(6))
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            {samples},
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "at time 0" in messages[0]


def test_conforming_animation_is_accepted(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.4, 0.4, 0.42)],
            1: [(0.5, 0.5, 0.52)],
            2: [(0.6, 0.6, 0.62)],
        }}
        float[] primvars:displayOpacity = [1.0] (
            interpolation = "constant"
        )
        float[] primvars:displayOpacity.timeSamples = {{
            0: [1.0],
            1: [0.5],
            2: [0.0],
        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


DEFORMING = """        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points.timeSamples = {
            0: [(0, 0, 0), (1, 0, 0), (1, 1, 0)],
            1: [(0, 0, 0), (1, 0, 0), (1, 1, 0)],
        }
"""


def test_deforming_mesh_with_matching_vertex_colours_is_accepted(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{DEFORMING}        color3f[] primvars:displayColor (
            interpolation = "vertex"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.1, 0.1, 0.1), (0.2, 0.2, 0.2), (0.3, 0.3, 0.3)],
            1: [(0.1, 0.1, 0.1), (0.2, 0.2, 0.2), (0.3, 0.3, 0.3)],
        }}
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


def test_deforming_mesh_with_a_short_later_sample_is_reported(checker_class):
    """Topology is read at the sample the values came from, so the point count this is
    compared against is the one that coexists with them."""
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{DEFORMING}        color3f[] primvars:displayColor (
            interpolation = "vertex"
        )
        color3f[] primvars:displayColor.timeSamples = {{
            0: [(0.1, 0.1, 0.1), (0.2, 0.2, 0.2), (0.3, 0.3, 0.3)],
            1: [(0.1, 0.1, 0.1), (0.2, 0.2, 0.2)],
        }}
    }}
"""
    )
    messages = check(checker_class, usda, "/World/bracket")
    assert len(messages) == 1
    assert "authors 2 elements, expected 3" in messages[0]
    assert "at time 1" in messages[0]


# ----------------------------------------------------------------------------------
# Scope
# ----------------------------------------------------------------------------------


def test_guide_purpose_geometry_is_out_of_scope(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        uniform token purpose = "guide"
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []


def test_a_non_gprim_is_out_of_scope(checker_class):
    usda = stage('    def Xform "Assembly"\n    {\n    }\n')
    assert check(checker_class, usda, "/World/Assembly") == []


def test_unauthored_opacity_is_not_required(checker_class):
    usda = stage(
        f"""    def Mesh "bracket"
    {{
{QUAD}        color3f[] primvars:displayColor = [(0.4, 0.4, 0.42)] (
            interpolation = "constant"
        )
    }}
"""
    )
    assert check(checker_class, usda, "/World/bracket") == []

    # The primvar exists on every Gprim whether or not a value was authored, which is why
    # the checker distinguishes the two on HasAuthoredValue rather than on the primvar.
    layer = Sdf.Layer.CreateAnonymous(".usda")
    layer.ImportFromString(usda)
    opened = Usd.Stage.Open(layer)
    primvar = UsdGeom.PrimvarsAPI(opened.GetPrimAtPath("/World/bracket")).GetPrimvar("displayOpacity")
    assert primvar
    assert not primvar.GetAttr().HasAuthoredValue()
