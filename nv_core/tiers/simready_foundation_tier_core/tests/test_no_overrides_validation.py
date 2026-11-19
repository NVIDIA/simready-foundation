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
"""RC.002 must report genuine attribute overrides and not ordinary definitions.

Requires an installed or editable core tier with generated requirements, pytest,
usd-validation-nvidia, and USD. Run against the tier built from the source under test.
"""

import pytest
import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia as validation
from pxr import Sdf, Usd
from simready.foundation.tier_core.rules_and_reqs.isaac_sim.robot_core.validation import (
    NoOverrides,
)

_BASE = """
def Xform "Asset" {
    def Cube "Cube" {
        double size = 10
    }
}
"""


def _stage(sublayer_name=None, strong=None, base=_BASE):
    """Compose a stage, optionally with a stronger sublayer holding more opinions.

    Args:
        sublayer_name: Identifier for the stronger layer, whose suffix decides
            whether it counts as a physics layer. None composes the base alone.
        strong: Layer body for the stronger layer.
        base: Layer body for the weaker, defining layer.

    Returns:
        The composed stage.
    """
    root = Sdf.Layer.CreateAnonymous("root.usda")
    base_layer = Sdf.Layer.CreateAnonymous("base.usda")
    base_layer.ImportFromString(f"#usda 1.0\n{base}")

    if sublayer_name is not None:
        strong_layer = Sdf.Layer.CreateAnonymous(sublayer_name)
        strong_layer.ImportFromString(f"#usda 1.0\n{strong}")
        root.subLayerPaths.append(strong_layer.identifier)

    root.subLayerPaths.append(base_layer.identifier)
    return Usd.Stage.Open(root)


def _check(stage, path="/Asset/Cube"):
    """Run the rule over one prim and return its issues.

    Args:
        stage: The composed stage to validate.
        path: Path of the prim to check.

    Returns:
        The issues the rule reported.
    """
    checker = NoOverrides()
    assert checker.CheckPrim(stage.GetPrimAtPath(path)) is None
    issues = list(checker.GetIssues())
    for issue in issues:
        assert issue.requirement == cap.RobotCoreRequirements.RC_002
        assert issue.severity == validation.IssueSeverity.FAILURE
    return issues


def test_single_layer_definition_is_not_reported():
    """An asset's own definition is not an override."""
    assert _check(_stage()) == []


def test_over_opinion_is_reported():
    """A value authored on an `over` prim spec is an override."""
    issues = _check(
        _stage(
            "strong.usda",
            """
over "Asset" {
    over "Cube" {
        double size = 20
    }
}
""",
        )
    )

    assert len(issues) == 1
    assert "size" in issues[0].message
    assert "/Asset/Cube" in issues[0].message


def test_masked_definition_is_reported():
    """A stronger layer masking a weaker opinion is an override, whatever the specifier."""
    issues = _check(
        _stage(
            "strong.usda",
            """
def Xform "Asset" {
    def Cube "Cube" {
        double size = 20
    }
}
""",
        )
    )

    assert len(issues) == 1
    assert "size" in issues[0].message


def test_physics_layer_exempts_only_its_physics_attributes():
    """RC.005 and RC.006 require physics opinions in a physics layer, so they are exempt.

    A non-physics attribute in that same layer stays reportable, so no layer earns
    blanket immunity from its name.
    """
    issues = _check(
        _stage(
            "robot_physics.usda",
            """
over "Asset" {
    over "Cube" {
        double physics:mass = 2
        double size = 20
    }
}
""",
        )
    )

    assert len(issues) == 1
    assert "physics:mass" not in issues[0].message
    assert "size" in issues[0].message


def test_non_physics_layer_reports_physics_attributes():
    """Outside a physics layer a physics attribute earns no exemption."""
    issues = _check(
        _stage(
            "strong.usda",
            """
over "Asset" {
    over "Cube" {
        double physics:mass = 2
    }
}
""",
        )
    )

    assert len(issues) == 1
    assert "physics:mass" in issues[0].message


def test_session_layer_opinion_is_not_reported():
    """Session layers carry transient viewport state, not anything authored into the asset."""
    stage = _stage()
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        stage.GetPrimAtPath("/Asset/Cube").GetAttribute("size").Set(99)

    assert _check(stage) == []


def test_validation_engine_reports_rc002_failure():
    """The rule reports through the validation engine, not only when driven directly."""
    stage = _stage(
        "strong.usda",
        """
over "Asset" {
    over "Cube" {
        double size = 20
    }
}
""",
    )
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(NoOverrides)

    issues = list(engine.validate(stage).issues)

    assert len(issues) == 1
    assert issues[0].requirement == cap.RobotCoreRequirements.RC_002
    assert issues[0].severity == validation.IssueSeverity.FAILURE
    assert "/Asset/Cube" in issues[0].message


@pytest.mark.parametrize(
    "attr_name",
    [
        "physics:mass",
        "drive:angular:physics:stiffness",
        "state:angular:physics:position",
        "physxRigidBody:maxLinearVelocity",
        "physxCollision:contactOffset",
    ],
)
def test_physics_namespaces_in_physics_layer_are_allowed(attr_name):
    stage = _stage("physics.usda", f'over "Asset" {{\n over "Cube" {{\n double {attr_name} = 2\n }}\n }}')
    assert _check(stage) == []


@pytest.mark.parametrize("attr_name", ["notphysics:bogus", "myphysics:mass", "physicsish"])
def test_similar_namespace_does_not_exempt_override(attr_name):
    stage = _stage("physics.usda", f'over "Asset" {{\n over "Cube" {{\n double {attr_name} = 2\n }}\n }}')
    issues = _check(stage)
    assert len(issues) == 1
    assert attr_name in issues[0].message


def test_plain_converted_physics_and_actuator_defs_pass_engine(tmp_path):
    stage = Usd.Stage.CreateNew(str(tmp_path / "converted.usda"))
    stage.DefinePrim("/Robot", "Xform")
    stage.DefinePrim("/Robot/Physics", "Scope")
    joint = stage.DefinePrim("/Robot/Physics/left_wheel", "PhysicsRevoluteJoint")
    joint.CreateAttribute("physics:axis", Sdf.ValueTypeNames.Token).Set("Y")
    actuator = stage.DefinePrim("/Robot/Physics/left_wheel_actuator", "MjcActuator")
    actuator.CreateAttribute("mjc:gear", Sdf.ValueTypeNames.Double).Set(1)
    actuator.CreateRelationship("mjc:target").SetTargets([joint.GetPath()])
    stage.GetRootLayer().Save()
    stage = Usd.Stage.Open(str(tmp_path / "converted.usda"))
    assert all(s.specifier == Sdf.SpecifierDef for p in stage.Traverse() for s in p.GetPrimStack())
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(NoOverrides)
    assert list(engine.validate(stage).issues) == []


@pytest.mark.parametrize("arc", ["reference", "payload"])
@pytest.mark.parametrize("local_override", [False, True])
def test_asset_arc_opinions_are_external_but_local_overrides_reported(arc, local_override):
    source = Sdf.Layer.CreateAnonymous("source.usda")
    source.ImportFromString('#usda 1.0\ndef Cube "Source" {\n double size = 10\n }')
    stage = Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim("/Asset/Cube", "Cube")
    editor = prim.GetReferences() if arc == "reference" else prim.GetPayloads()
    if arc == "reference":
        editor.AddReference(source.identifier, "/Source")
    else:
        editor.AddPayload(source.identifier, "/Source")
    if local_override:
        # Use an over spec in the root stack above the referenced definition.
        stage.GetRootLayer().GetPrimAtPath(prim.GetPath()).specifier = Sdf.SpecifierOver
        prim.GetAttribute("size").Set(20)
    issues = _check(stage)
    assert len(issues) == (1 if local_override else 0)
    if local_override:
        assert "size" in issues[0].message


@pytest.mark.parametrize("path,expected", [("/Render/Cube", 0), ("/RenderMesh", 1)])
def test_render_exemption_matches_path_component(path, expected):
    stage = Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim(path, "Cube")
    prim.CreateAttribute("size", Sdf.ValueTypeNames.Double).Set(10)
    layer = Sdf.Layer.CreateAnonymous("tweaks.usda")
    stage.GetRootLayer().subLayerPaths.append(layer.identifier)
    with Usd.EditContext(stage, layer):
        prim.GetAttribute("size").Set(20)
    assert len(_check(stage, path)) == expected


def test_single_over_opinion_in_selected_variant_is_reported():
    stage = Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim("/Asset/Cube", "Cube")
    variants = prim.GetVariantSets().AddVariantSet("configuration")
    variants.AddVariant("default")
    variants.SetVariantSelection("default")
    with variants.GetVariantEditContext():
        prim.CreateAttribute("size", Sdf.ValueTypeNames.Double).Set(20)
    issues = _check(stage)
    assert len(issues) == 1
    assert "size" in issues[0].message


@pytest.mark.parametrize(
    "attr_name", ["physics:mass", "drive:angular:physics:stiffness", "physxRigidBody:maxLinearVelocity"]
)
@pytest.mark.parametrize("specifier", ["def Xform", "over"])
@pytest.mark.parametrize(
    "strong_name,weak_name,expected_failures",
    [
        ("robot.usda", "physics.usda", 1),
        ("physics.usda", "robot.usda", 0),
        ("robot_physics.usda", "physics.usda", 0),
    ],
)
def test_physics_exemption_preserves_weaker_override_evidence(
    attr_name, specifier, strong_name, weak_name, expected_failures
):
    """A physics layer may supply overrides; it must not hide overrides from other layers."""
    weak = Sdf.Layer.CreateAnonymous(weak_name)
    weak.ImportFromString(f'#usda 1.0\ndef Xform "Robot" {{\n double {attr_name} = 1\n}}')
    root = Sdf.Layer.CreateAnonymous(strong_name)
    root.ImportFromString(f'#usda 1.0\n{specifier} "Robot" {{\n double {attr_name} = 99\n}}')
    root.subLayerPaths.append(weak.identifier)
    stage = Usd.Stage.Open(root)
    assert stage.GetPrimAtPath("/Robot").GetAttribute(attr_name).Get() == 99
    engine = validation.ValidationEngine(init_rules=False)
    engine.enable_rule(NoOverrides)
    issues = list(engine.validate(stage).issues)
    assert len(issues) == expected_failures
    if expected_failures:
        assert issues[0].requirement == cap.RobotCoreRequirements.RC_002
        assert issues[0].severity == validation.IssueSeverity.FAILURE
        assert attr_name in issues[0].message
