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
"""Assembly/Connections validators (`CN.*`)."""

import math

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Kind, Usd, UsdGeom, UsdPhysics

from ..utils import (
    ASSEMBLY_TYPE_ATTR,
    CONNECTIONS_SCOPE,
    INTERFACE_ATTR,
    JOINT_REL,
    MAX_PAYLOAD_ATTR,
    PLUG_REL,
    PLUG_ROLE,
    REALIZATION_ATTR,
    REALIZATION_COMPOUND,
    REALIZATION_JOINTED,
    SOCKET_REL,
    SOCKET_ROLE,
    applied_api_schemas,
    authored_mass,
    authored_token,
    common_ancestor,
    get_connections_scope,
    is_rigid_body_enabled,
    is_in_articulation,
    iter_connections,
    iter_nested_assembly_roots,
    iter_nested_connections,
    massless_bodies,
    read_mate_site,
    relative_transform,
    resolve_mate_body,
    subtree_mass,
    unresolvable_mass,
)

_ASSEMBLY_TYPES = ("robot", "pallet_stack")
_REALIZATIONS = (REALIZATION_COMPOUND, REALIZATION_JOINTED)

# Mate frames are authored coincident, so the joint poses that express them are
# exact up to composition round-off rather than approximate.
_POSITION_TOLERANCE_METERS = 1e-4
_ROTATION_TOLERANCE_DEGREES = 0.1

# CN.011 allows the aggregate to round; it does not allow it to be a different claim.
_MASS_TOLERANCE_FRACTION = 0.01

_PHYSX_JOINT_API = "PhysxJointAPI"
# Swept as a namespace so a `physxJoint:` name that no schema defines, and so
# composes as a custom attribute, is covered alongside the real ones.
_PHYSX_JOINT_NAMESPACE = "physxJoint:"

_NEWTON_JOINT_API = "NewtonJointAPI"
_NEWTON_FIXED_JOINT_APIS = ("NewtonFixedJointAPI",)
_NEWTON_FIXED_JOINT_TYPES = ("NewtonFixedJoint",)
_NEWTON_DOF_ATTRS = (
    "newton:armature",
    "newton:damping",
    "newton:friction",
    "newton:velocityLimit",
    "newton:limitStiffness",
    "newton:limitDamping",
)

_MUJOCO_JOINT_API = "MjcJointAPI"
_MUJOCO_WELD_APIS = ("MjcWeldAPI", "MjcFixedJointAPI")
_MUJOCO_WELD_TYPES = ("MjcWeld", "MjcFixedJoint")
_MUJOCO_ACTUATOR_TYPE = "MjcActuator"
_MUJOCO_ACTUATOR_TARGET_REL = "mjc:target"


def _require_default_prim(checker, stage: Usd.Stage) -> Usd.Prim | None:
    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        checker._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
        return None
    return default_prim


def _stage_position_tolerance(stage: Usd.Stage) -> float:
    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage) or 1.0
    return _POSITION_TOLERANCE_METERS / meters_per_unit


def _quat_angle_degrees(a: Gf.Quatf, b: Gf.Quatf) -> float:
    dot = a.GetReal() * b.GetReal() + Gf.Dot(a.GetImaginary(), b.GetImaginary())
    return math.degrees(2.0 * math.acos(min(1.0, abs(dot))))


def _jointed_connections_with_joints(stage: Usd.Stage):
    """Jointed connections whose `simready:mate:joint` resolves to one prim.

    The runtime variant rules all layer onto the same joint, and all of them
    skip compound connections, which have none.
    """
    for connection in iter_connections(stage):
        if not connection.is_jointed:
            continue
        joint = connection.joint_prim
        if joint is not None:
            yield connection, joint


@usd_validation_nvidia.register_rule("ConnectionDeclaration")
@usd_validation_nvidia.register_requirements(
    cap.ConnectionsRequirements.CN_001,
    cap.ConnectionsRequirements.CN_002,
    cap.ConnectionsRequirements.CN_003,
    cap.ConnectionsRequirements.CN_004,
    cap.ConnectionsRequirements.CN_007,
    override=True,
)
class ConnectionDeclarationChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.001-CN.004, CN.007: the connection Scope, its rels, and what they pair."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        scope = get_connections_scope(stage)
        if scope is None:
            self._AddFailedCheck(
                f"Assembly default prim '{default_prim.GetPath()}' has no '{CONNECTIONS_SCOPE}' Scope.",
                at=default_prim,
                requirement=cap.ConnectionsRequirements.CN_001,
            )
            return
        if not scope.IsA(UsdGeom.Scope):
            self._AddWarning(
                f"'{scope.GetPath()}' is a '{scope.GetTypeName()}'; the connections container "
                "is conventionally a Scope.",
                at=scope,
                requirement=cap.ConnectionsRequirements.CN_001,
            )

        nested: dict[str, str] = {}
        for connection in iter_nested_connections(stage):
            for target in (*connection.socket_targets, *connection.plug_targets):
                nested.setdefault(str(target), connection.path)

        occupancy: dict[str, str] = {}
        for connection in iter_connections(stage):
            socket = self._check_rel(connection, SOCKET_REL, connection.has_socket_rel, connection.socket_targets)
            plug = self._check_rel(connection, PLUG_REL, connection.has_plug_rel, connection.plug_targets)
            self._check_exclusivity(connection, occupancy, nested)
            if socket is None or plug is None:
                continue
            socket_site = self._check_target(connection, SOCKET_REL, socket, SOCKET_ROLE)
            plug_site = self._check_target(connection, PLUG_REL, plug, PLUG_ROLE)
            if socket_site and plug_site:
                self._check_interface_match(connection, socket, plug)

    def _check_rel(self, connection, name: str, authored: bool, targets: list) -> Usd.Prim | None:
        """CN.001: exactly one rel with exactly one target. CN.002: it resolves."""
        if not authored:
            self._AddFailedCheck(
                f"Connection '{connection.path}' does not author '{name}'.",
                at=connection.prim,
                requirement=cap.ConnectionsRequirements.CN_001,
            )
            return None
        if len(targets) != 1:
            self._AddFailedCheck(
                f"Connection '{connection.path}' authors '{name}' with {len(targets)} targets; "
                "it must have exactly one.",
                at=connection.prim,
                requirement=cap.ConnectionsRequirements.CN_001,
            )
            return None

        prim = connection.prim.GetStage().GetPrimAtPath(targets[0])
        if not prim or not prim.IsValid():
            self._AddFailedCheck(
                f"Connection '{connection.path}' has '{name}' targeting '{targets[0]}', "
                "which does not resolve on the composed stage.",
                at=connection.prim,
                requirement=cap.ConnectionsRequirements.CN_002,
            )
            return None
        return prim

    def _check_target(self, connection, name: str, prim: Usd.Prim, expected_role: str) -> bool:
        """CN.002: the target is a mechanical mate site. CN.003: with the right role."""
        site = read_mate_site(prim)
        if site is None or not site.is_well_formed:
            self._AddFailedCheck(
                f"Connection '{connection.path}' has '{name}' targeting '{prim.GetPath()}', "
                "which is not a mate site (MC.001).",
                at=prim,
                requirement=cap.ConnectionsRequirements.CN_002,
            )
            return False
        if not site.is_mechanical:
            self._AddFailedCheck(
                f"Connection '{connection.path}' has '{name}' targeting '{prim.GetPath()}', "
                f"which is in the '{site.domain}' domain rather than mechanical (MC.002).",
                at=prim,
                requirement=cap.ConnectionsRequirements.CN_002,
            )
            return False
        if site.role != expected_role:
            self._AddFailedCheck(
                f"Connection '{connection.path}' has '{name}' targeting '{prim.GetPath()}', "
                f"whose role is '{site.role}' rather than '{expected_role}'.",
                at=prim,
                requirement=cap.ConnectionsRequirements.CN_003,
            )
            return False
        return True

    def _check_interface_match(self, connection, socket: Usd.Prim, plug: Usd.Prim) -> None:
        """CN.004: exact string equality of the interface tokens."""
        socket_interface = authored_token(socket, INTERFACE_ATTR)
        plug_interface = authored_token(plug, INTERFACE_ATTR)
        if not socket_interface or not plug_interface:
            # MC.004 reports the missing token; there is nothing to compare here.
            return
        if socket_interface != plug_interface:
            self._AddFailedCheck(
                f"Connection '{connection.path}' pairs interface '{socket_interface}' on the socket "
                f"with '{plug_interface}' on the plug; the tokens must be identical.",
                at=connection.prim,
                requirement=cap.ConnectionsRequirements.CN_004,
            )

    def _check_exclusivity(self, connection, occupancy: dict[str, str], nested: dict[str, str]) -> None:
        """CN.007: no mate site appears in more than one connection, at any nesting depth."""
        for name, targets in ((SOCKET_REL, connection.socket_targets), (PLUG_REL, connection.plug_targets)):
            for target in targets:
                path = str(target)
                inner = nested.get(path)
                if inner is not None:
                    self._AddFailedCheck(
                        f"Mate site '{path}' is used by connection '{connection.path}' and is already "
                        f"paired by nested connection '{inner}'; a site may appear in only one connection.",
                        at=connection.prim,
                        requirement=cap.ConnectionsRequirements.CN_007,
                    )
                    continue
                previous = occupancy.get(path)
                if previous is not None:
                    self._AddFailedCheck(
                        f"Mate site '{path}' is used by connection '{connection.path}' and by "
                        f"'{previous}'; a site may appear in only one connection.",
                        at=connection.prim,
                        requirement=cap.ConnectionsRequirements.CN_007,
                    )
                else:
                    occupancy[path] = connection.path


@usd_validation_nvidia.register_rule("MateRealization")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_006, override=True)
class MateRealizationChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.006: `realization` is authored and agrees with how the mate bodies resolve."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if _require_default_prim(self, stage) is None:
            return

        requirement = cap.ConnectionsRequirements.CN_006
        for connection in iter_connections(stage):
            if connection.realization is None:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' does not author '{REALIZATION_ATTR}'.",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue
            if connection.realization not in _REALIZATIONS:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' has {REALIZATION_ATTR} = "
                    f"'{connection.realization}'; it must be {' or '.join(_REALIZATIONS)}.",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue

            if connection.is_compound and connection.has_joint_rel:
                self._AddFailedCheck(
                    f"Compound connection '{connection.path}' authors '{JOINT_REL}'; "
                    "a compound has no joint.",
                    at=connection.prim,
                    requirement=requirement,
                )

            socket = connection.socket_prim
            plug = connection.plug_prim
            if not socket or not plug:
                # CN.001/CN.002 report the unusable rels.
                continue

            socket_body = resolve_mate_body(socket)
            plug_body = resolve_mate_body(plug)
            if socket_body is None or plug_body is None:
                # MC.003 reports the site with no mate body.
                continue

            shared = socket_body == plug_body
            if shared and connection.is_jointed:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' is jointed, but both sites resolve to the same "
                    f"mate body '{socket_body.GetPath()}'; a body cannot be jointed to itself.",
                    at=connection.prim,
                    requirement=requirement,
                )
            elif not shared and connection.is_compound:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' is compound, but the sites resolve to distinct "
                    f"mate bodies '{socket_body.GetPath()}' and '{plug_body.GetPath()}'; "
                    "nothing holds the pairing.",
                    at=connection.prim,
                    requirement=requirement,
                )


@usd_validation_nvidia.register_rule("CompoundBody")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_011, override=True)
class CompoundBodyChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.011: the body a compound connection shares is assembly-local and carries the aggregate."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        # One compound body per compound island; a stage of jointed connections has none.
        # Resolving from the sites' common ancestor rather than from agreement between
        # the two walks keeps the body identifiable when a part was left enabled, which
        # is one of the conditions this requirement has to report.
        bodies: dict[str, Usd.Prim] = {}
        for connection in iter_connections(stage):
            if not connection.is_compound:
                continue
            socket = connection.socket_prim
            plug = connection.plug_prim
            if not socket or not plug:
                continue
            shared = common_ancestor(socket, plug)
            body = resolve_mate_body(shared) if shared is not None else None
            if body is not None:
                bodies[str(body.GetPath())] = body

        for body in bodies.values():
            self._check_body(default_prim, body)

    def _check_body(self, default_prim: Usd.Prim, body: Usd.Prim) -> None:
        requirement = cap.ConnectionsRequirements.CN_011
        path = body.GetPath()

        if body == default_prim:
            self._AddFailedCheck(
                f"Compound body '{path}' is the assembly default prim; the shared actor must be "
                "a prim below it so one assembly can hold several compound groups.",
                at=body,
                requirement=requirement,
            )
        elif not path.HasPrefix(default_prim.GetPath()):
            self._AddFailedCheck(
                f"Compound body '{path}' is not a descendant of the assembly default prim "
                f"'{default_prim.GetPath()}'.",
                at=body,
                requirement=requirement,
            )

        if body.HasAuthoredReferences() or body.HasAuthoredPayloads():
            self._AddFailedCheck(
                f"Compound body '{path}' carries a reference or payload arc, so the aggregate mass "
                "would read as one part's mass rather than as the fused group's.",
                at=body,
                requirement=requirement,
            )

        self._check_demoted_parts(body, requirement)
        self._check_aggregate_mass(body, requirement)

    def _check_demoted_parts(self, body: Usd.Prim, requirement) -> None:
        for prim in Usd.PrimRange(body):
            if prim == body:
                continue
            if prim.IsA(UsdPhysics.Joint):
                self._AddFailedCheck(
                    f"'{prim.GetPath()}' in the subtree of compound body '{body.GetPath()}' is a joint; "
                    "a part that contains a joint joins only through a jointed connection.",
                    at=prim,
                    requirement=requirement,
                )
                continue
            if is_rigid_body_enabled(prim):
                self._AddFailedCheck(
                    f"'{prim.GetPath()}' in the subtree of compound body '{body.GetPath()}' still has "
                    "an enabled rigid body; each fused part must author physics:rigidBodyEnabled = false.",
                    at=prim,
                    requirement=requirement,
                )

    def _check_aggregate_mass(self, body: Usd.Prim, requirement) -> None:
        aggregate = authored_mass(body)
        if aggregate is None:
            self._check_derivable_mass(body, requirement)
            return

        if not body.HasAPI(UsdPhysics.MassAPI):
            self._AddFailedCheck(
                f"Compound body '{body.GetPath()}' authors physics:mass without applying "
                "PhysicsMassAPI.",
                at=body,
                requirement=requirement,
            )

        incomplete = massless_bodies(body, include_root=False)
        if incomplete:
            self._AddWarning(
                f"Compound body '{body.GetPath()}' has parts with no authored mass "
                f"({', '.join(str(p.GetPath()) for p in incomplete)}), so its aggregate of "
                f"{aggregate} cannot be checked against a complete sum.",
                at=body,
                requirement=requirement,
            )
            return

        parts_total = subtree_mass(body, include_root=False)
        if parts_total == 0.0:
            # No parts contribute mass and none are rigid bodies; nothing to compare.
            return

        if abs(aggregate - parts_total) > _MASS_TOLERANCE_FRACTION * parts_total:
            self._AddFailedCheck(
                f"Compound body '{body.GetPath()}' authors physics:mass = {aggregate}, but its parts "
                f"sum to {parts_total}; the aggregate must match within "
                f"{_MASS_TOLERANCE_FRACTION:.0%}.",
                at=body.GetAttribute(UsdPhysics.Tokens.physicsMass),
                requirement=requirement,
            )

    def _check_derivable_mass(self, body: Usd.Prim, requirement) -> None:
        """A compound may omit the aggregate only when the runtime derives the same total."""
        inert = unresolvable_mass(body, include_root=False)
        if inert:
            self._AddFailedCheck(
                f"Compound body '{body.GetPath()}' authors no physics:mass, and its parts author "
                f"mass on prims the runtime cannot read it from "
                f"({', '.join(str(p.GetPath()) for p in inert)}); the compound body must author "
                "the aggregate.",
                at=body,
                requirement=requirement,
            )
            return

        if subtree_mass(body, include_root=False) == 0.0:
            self._AddFailedCheck(
                f"Compound body '{body.GetPath()}' authors no physics:mass and neither do its "
                "parts' colliders, so the fused actor states no mass at all.",
                at=body,
                requirement=requirement,
            )


@usd_validation_nvidia.register_rule("ConnectionJoint")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_009, override=True)
class ConnectionJointChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.009: a jointed connection points at a fixed joint on the right bodies and poses."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if _require_default_prim(self, stage) is None:
            return

        requirement = cap.ConnectionsRequirements.CN_009
        tolerance = _stage_position_tolerance(stage)

        for connection in iter_connections(stage):
            if not connection.is_jointed:
                continue

            if not connection.has_joint_rel:
                self._AddFailedCheck(
                    f"Jointed connection '{connection.path}' does not author '{JOINT_REL}'.",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue
            if len(connection.joint_targets) != 1:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' authors '{JOINT_REL}' with "
                    f"{len(connection.joint_targets)} targets; it must have exactly one.",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue

            joint_prim = connection.joint_prim
            if joint_prim is None:
                self._AddFailedCheck(
                    f"Connection '{connection.path}' has '{JOINT_REL}' targeting "
                    f"'{connection.joint_targets[0]}', which does not resolve on the composed stage.",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue

            if not joint_prim.IsA(UsdPhysics.FixedJoint):
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' is a '{joint_prim.GetTypeName()}'; "
                    "a connection is a rigid attachment and must be a UsdPhysicsFixedJoint.",
                    at=joint_prim,
                    requirement=requirement,
                )
                continue

            self._check_bodies_and_poses(connection, joint_prim, tolerance, requirement)
            self._check_attach_strength(joint_prim, requirement)

    def _check_attach_strength(self, joint_prim, requirement) -> None:
        """Break thresholds are `UsdPhysicsJoint` attributes every runtime reads.

        The schema fallback is `inf`, so `HasAuthoredValue` separates a
        deliberately permanent attachment from an unstated one.
        """
        joint = UsdPhysics.Joint(joint_prim)
        for label, attr in (
            ("physics:breakForce", joint.GetBreakForceAttr()),
            ("physics:breakTorque", joint.GetBreakTorqueAttr()),
        ):
            if not attr or not attr.HasAuthoredValue():
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' does not author '{label}'; "
                    "the schema fallback of inf makes an unbreakable attachment "
                    "indistinguishable from an unauthored one.",
                    at=joint_prim,
                    requirement=requirement,
                )

    def _check_bodies_and_poses(self, connection, joint_prim, tolerance, requirement) -> None:
        socket = connection.socket_prim
        plug = connection.plug_prim
        if not socket or not plug:
            return
        socket_body = resolve_mate_body(socket)
        plug_body = resolve_mate_body(plug)
        if socket_body is None or plug_body is None:
            return

        joint = UsdPhysics.Joint(joint_prim)
        body0 = self._single_body(joint.GetBody0Rel(), joint_prim)
        body1 = self._single_body(joint.GetBody1Rel(), joint_prim)

        # Body order is not significant, so accept either assignment of the pair.
        if {body0, body1} != {socket_body, plug_body}:
            self._AddFailedCheck(
                f"Connection joint '{joint_prim.GetPath()}' joins "
                f"'{self._name(body0)}' and '{self._name(body1)}', but the connection's mate bodies "
                f"are '{socket_body.GetPath()}' and '{plug_body.GetPath()}'.",
                at=joint_prim,
                requirement=requirement,
            )
            return

        if body0 == socket_body:
            pairs = ((0, socket, socket_body), (1, plug, plug_body))
        else:
            pairs = ((0, plug, plug_body), (1, socket, socket_body))

        for index, site, body in pairs:
            self._check_pose(joint, joint_prim, index, site, body, tolerance, requirement)

    def _check_pose(self, joint, joint_prim, index, site, body, tolerance, requirement) -> None:
        expected = relative_transform(site, body).RemoveScaleShear()
        expected_pos = Gf.Vec3f(expected.ExtractTranslation())
        expected_rot = Gf.Quatf(expected.ExtractRotationQuat())

        pos_attr = joint.GetLocalPos0Attr() if index == 0 else joint.GetLocalPos1Attr()
        rot_attr = joint.GetLocalRot0Attr() if index == 0 else joint.GetLocalRot1Attr()
        pos_value = pos_attr.Get() if pos_attr else None
        rot_value = rot_attr.Get() if rot_attr else None
        actual_pos = Gf.Vec3f(pos_value) if pos_value is not None else Gf.Vec3f(0.0, 0.0, 0.0)
        actual_rot = Gf.Quatf(rot_value) if rot_value is not None else Gf.Quatf(1.0)

        if (actual_pos - expected_pos).GetLength() > tolerance:
            self._AddFailedCheck(
                f"Connection joint '{joint_prim.GetPath()}' has physics:localPos{index} = {actual_pos}, "
                f"but mate site '{site.GetPath()}' sits at {expected_pos} in body "
                f"'{body.GetPath()}'.",
                at=pos_attr,
                requirement=requirement,
            )

        if _quat_angle_degrees(actual_rot, expected_rot) > _ROTATION_TOLERANCE_DEGREES:
            self._AddFailedCheck(
                f"Connection joint '{joint_prim.GetPath()}' has physics:localRot{index} = {actual_rot}, "
                f"but mate site '{site.GetPath()}' is oriented {expected_rot} in body "
                f"'{body.GetPath()}'.",
                at=rot_attr,
                requirement=requirement,
            )

    @staticmethod
    def _single_body(rel, joint_prim) -> Usd.Prim | None:
        targets = rel.GetTargets() if rel else []
        if len(targets) != 1:
            return None
        prim = joint_prim.GetStage().GetPrimAtPath(targets[0])
        return prim if prim and prim.IsValid() else None

    @staticmethod
    def _name(prim: Usd.Prim | None) -> str:
        return str(prim.GetPath()) if prim else "<unresolved>"


@usd_validation_nvidia.register_rule("PayloadCapacity")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_005, override=True)
class PayloadCapacityChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.005: a jointed socket's rating covers the mass hanging off it."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if _require_default_prim(self, stage) is None:
            return

        requirement = cap.ConnectionsRequirements.CN_005
        for connection in iter_connections(stage):
            # A compound has no joint to rate; CN.011 checks its aggregate instead.
            if not connection.is_jointed:
                continue

            socket = connection.socket_prim
            plug = connection.plug_prim
            if not socket or not plug:
                continue

            attr = socket.GetAttribute(MAX_PAYLOAD_ATTR)
            if not attr or not attr.HasAuthoredValue():
                # MC.006 reports the socket with no rating.
                continue
            max_payload = attr.Get()
            if max_payload is None or float(max_payload) <= 0.0:
                continue

            plug_body = resolve_mate_body(plug)
            if plug_body is None:
                continue

            incomplete = massless_bodies(plug_body)
            if incomplete:
                self._AddWarning(
                    f"Connection '{connection.path}' cannot be rated: rigid bodies in the plug "
                    f"subtree author no mass ({', '.join(str(p.GetPath()) for p in incomplete)}).",
                    at=connection.prim,
                    requirement=requirement,
                )
                continue

            plug_mass = subtree_mass(plug_body)
            if plug_mass > float(max_payload):
                self._AddFailedCheck(
                    f"Connection '{connection.path}' hangs {plug_mass} kg off socket "
                    f"'{socket.GetPath()}', which is rated for {float(max_payload)} kg.",
                    at=connection.prim,
                    requirement=requirement,
                )


@usd_validation_nvidia.register_rule("AssemblyChildReferences")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_010, override=True)
class AssemblyChildReferencesChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.010: every connected site arrives through a reference or payload arc."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_010
        for connection in iter_connections(stage):
            for name, site in ((SOCKET_REL, connection.socket_prim), (PLUG_REL, connection.plug_prim)):
                if site is None:
                    continue
                if not self._composed_in(site, default_prim):
                    self._AddFailedCheck(
                        f"Mate site '{site.GetPath()}' on connection '{connection.path}' ({name}) is "
                        "authored inline; no prim between it and the assembly default prim introduces "
                        "a reference or payload arc to a separately published asset.",
                        at=site,
                        requirement=requirement,
                    )

    @staticmethod
    def _composed_in(site: Usd.Prim, default_prim: Usd.Prim) -> bool:
        prim = site
        while prim and prim != default_prim and not prim.IsPseudoRoot():
            if prim.HasAuthoredReferences() or prim.HasAuthoredPayloads():
                return True
            prim = prim.GetParent()
        return False


@usd_validation_nvidia.register_rule("AssemblyModelHierarchy")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_012, override=True)
class AssemblyModelHierarchyChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.012: an `assembly` root over `component` or `assembly` children, contiguously."""

    _CHILD_KINDS = (Kind.Tokens.component, Kind.Tokens.assembly)

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_012
        root_kind = Usd.ModelAPI(default_prim).GetKind()
        if root_kind != Kind.Tokens.assembly:
            self._AddFailedCheck(
                f"Assembly default prim '{default_prim.GetPath()}' has kind '{root_kind}'; "
                "it must be 'assembly'.",
                at=default_prim,
                requirement=requirement,
            )

        it = iter(Usd.PrimRange(default_prim))
        for prim in it:
            if prim == default_prim:
                continue
            if prim.HasAuthoredReferences() or prim.HasAuthoredPayloads():
                self._check_child_root(prim, requirement)
                it.PruneChildren()
                self._check_subtree(prim, default_prim, requirement)
                continue
            self._check_contiguous(prim, default_prim, requirement)

    def _check_child_root(self, prim: Usd.Prim, requirement) -> None:
        kind = Usd.ModelAPI(prim).GetKind()
        if kind not in self._CHILD_KINDS:
            self._AddFailedCheck(
                f"Child asset root '{prim.GetPath()}' has kind '{kind}'; a composed-in asset root "
                "must be 'component' or 'assembly'.",
                at=prim,
                requirement=requirement,
            )

    def _check_subtree(self, root: Usd.Prim, default_prim: Usd.Prim, requirement) -> None:
        for prim in Usd.PrimRange(root):
            self._check_contiguous(prim, default_prim, requirement)

    def _check_contiguous(self, prim: Usd.Prim, default_prim: Usd.Prim, requirement) -> None:
        """A prim with a model kind is a model only if every ancestor is a group-kinded model.

        Only the topmost prim below each break is reported.
        """
        if not self._is_broken_model(prim) or self._is_broken_model(prim.GetParent()):
            return
        kind = Usd.ModelAPI(prim).GetKind()
        breaker = prim.GetParent()
        while breaker and breaker != default_prim and breaker.IsGroup():
            breaker = breaker.GetParent()
        breaker_kind = Usd.ModelAPI(breaker).GetKind() if breaker else ""
        self._AddFailedCheck(
            f"'{prim.GetPath()}' has kind '{kind}', but its ancestor '{breaker.GetPath()}' has kind "
            f"'{breaker_kind}'; a model's ancestors must all be 'group' or 'assembly'.",
            at=prim,
            requirement=requirement,
        )

    @staticmethod
    def _is_broken_model(prim: Usd.Prim) -> bool:
        if not prim or prim.IsPseudoRoot():
            return False
        kind = Usd.ModelAPI(prim).GetKind()
        return bool(kind) and Kind.Registry.IsA(kind, Kind.Tokens.model) and not prim.IsModel()


@usd_validation_nvidia.register_rule("AssemblyType")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_008, override=True)
class AssemblyTypeChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.008: the default prim classifies the assembly with a token from the closed list."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_008
        assembly_type = authored_token(default_prim, ASSEMBLY_TYPE_ATTR)
        if assembly_type is None:
            self._AddFailedCheck(
                f"Assembly default prim '{default_prim.GetPath()}' does not author "
                f"'{ASSEMBLY_TYPE_ATTR}'.",
                at=default_prim,
                requirement=requirement,
            )
        elif assembly_type not in _ASSEMBLY_TYPES:
            self._AddFailedCheck(
                f"Assembly default prim '{default_prim.GetPath()}' has {ASSEMBLY_TYPE_ATTR} = "
                f"'{assembly_type}'; the closed list is {', '.join(_ASSEMBLY_TYPES)}.",
                at=default_prim,
                requirement=requirement,
            )

        # The token classifies an assembly, so it belongs only on assembly roots: the
        # default prim, and the root of each composed-in assembly, which keeps its own.
        nested_roots = {prim.GetPath() for prim in iter_nested_assembly_roots(stage)}
        for prim in Usd.PrimRange(default_prim):
            if prim == default_prim or prim.GetPath() in nested_roots:
                continue
            if authored_token(prim, ASSEMBLY_TYPE_ATTR) is not None:
                self._AddFailedCheck(
                    f"'{prim.GetPath()}' authors '{ASSEMBLY_TYPE_ATTR}'; the token belongs on an "
                    "assembly root.",
                    at=prim,
                    requirement=requirement,
                )


@usd_validation_nvidia.register_rule("PhysxConnectionJoint")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_PHYSX_001, override=True)
class PhysxConnectionJointChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.PHYSX.001: a standard fixed joint with no PhysX DOF tuning and one surviving root.

    PhysX maps `UsdPhysicsFixedJoint` directly, so this rule constrains what may
    accompany the standard joint. Attach strength is `CN.009`, since
    `physics:breakForce` / `physics:breakTorque` are `UsdPhysicsJoint` attributes.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_PHYSX_001
        for connection, joint_prim in _jointed_connections_with_joints(stage):
            if not joint_prim.IsA(UsdPhysics.FixedJoint):
                # CN.009 reports the wrong joint type.
                continue

            schemas = applied_api_schemas(joint_prim)
            if _PHYSX_JOINT_API in schemas:
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' applies {_PHYSX_JOINT_API}, which "
                    "tunes a degree of freedom; a fixed connection joint has none.",
                    at=joint_prim,
                    requirement=requirement,
                )
            for attr in joint_prim.GetAuthoredAttributes():
                if not attr.GetName().startswith(_PHYSX_JOINT_NAMESPACE):
                    continue
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' authors '{attr.GetName()}'; a fixed "
                    "connection joint has no degree of freedom to tune. Attach strength is "
                    "physics:breakForce / physics:breakTorque (CN.009).",
                    at=attr,
                    requirement=requirement,
                )

            _check_contact_filtered(self, joint_prim, requirement)
            self._check_articulation(connection, joint_prim, default_prim, requirement)

    def _check_articulation(self, connection, joint_prim, default_prim, requirement) -> None:
        """The joint belongs to the articulation it fuses, which owns one root."""
        attr = UsdPhysics.Joint(joint_prim).GetExcludeFromArticulationAttr()
        if attr and bool(attr.Get()):
            self._AddFailedCheck(
                f"Connection joint '{joint_prim.GetPath()}' authors "
                "physics:excludeFromArticulation = true; the joint is part of the articulation it "
                "fuses and must be solved with it.",
                at=attr,
                requirement=requirement,
            )

        _check_single_articulation_root(self, connection, default_prim, requirement)


@usd_validation_nvidia.register_rule("NewtonConnectionJoint")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_NEWTON_001, override=True)
class NewtonConnectionJointChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.NEWTON.001: a standard fixed joint with no Newton DOF tuning and one surviving root."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_NEWTON_001
        for connection, joint_prim in _jointed_connections_with_joints(stage):
            schemas = applied_api_schemas(joint_prim)

            for name in _NEWTON_FIXED_JOINT_APIS:
                if name in schemas:
                    self._AddFailedCheck(
                        f"Connection joint '{joint_prim.GetPath()}' applies '{name}', which is not in "
                        "the Newton schema; Newton maps UsdPhysicsFixedJoint directly.",
                        at=joint_prim,
                        requirement=requirement,
                    )
            if str(joint_prim.GetTypeName()) in _NEWTON_FIXED_JOINT_TYPES:
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' uses the invented type "
                    f"'{joint_prim.GetTypeName()}'; it must be a UsdPhysicsFixedJoint.",
                    at=joint_prim,
                    requirement=requirement,
                )

            if not joint_prim.IsA(UsdPhysics.FixedJoint):
                # CN.009 reports the wrong joint type.
                continue

            if _NEWTON_JOINT_API in schemas:
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' applies {_NEWTON_JOINT_API}, which "
                    "tunes a degree of freedom; a fixed connection joint has none.",
                    at=joint_prim,
                    requirement=requirement,
                )
            for name in _NEWTON_DOF_ATTRS:
                attr = joint_prim.GetAttribute(name)
                if attr and attr.HasAuthoredValue():
                    self._AddFailedCheck(
                        f"Connection joint '{joint_prim.GetPath()}' authors '{name}', which describes "
                        "the behavior of a degree of freedom the joint does not have.",
                        at=attr,
                        requirement=requirement,
                    )

            _check_contact_filtered(self, joint_prim, requirement)
            _check_single_articulation_root(self, connection, default_prim, requirement)


@usd_validation_nvidia.register_rule("MuJoCoConnectionJoint")
@usd_validation_nvidia.register_requirements(cap.ConnectionsRequirements.CN_MUJOCO_001, override=True)
class MuJoCoConnectionJointChecker(usd_validation_nvidia.BaseRuleChecker):
    """CN.MUJOCO.001: a standard fixed joint that is not presented to MuJoCo as a DOF."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = _require_default_prim(self, stage)
        if default_prim is None:
            return

        requirement = cap.ConnectionsRequirements.CN_MUJOCO_001
        joint_paths: dict[str, Usd.Prim] = {}

        for _connection, joint_prim in _jointed_connections_with_joints(stage):
            joint_paths[str(joint_prim.GetPath())] = joint_prim
            schemas = applied_api_schemas(joint_prim)

            for name in _MUJOCO_WELD_APIS:
                if name in schemas:
                    self._AddFailedCheck(
                        f"Connection joint '{joint_prim.GetPath()}' applies '{name}', which is not in "
                        "the mjcPhysics schema; MuJoCo has no fixed joint to map it to.",
                        at=joint_prim,
                        requirement=requirement,
                    )
            if str(joint_prim.GetTypeName()) in _MUJOCO_WELD_TYPES:
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' uses the invented type "
                    f"'{joint_prim.GetTypeName()}'; it must be a UsdPhysicsFixedJoint.",
                    at=joint_prim,
                    requirement=requirement,
                )

            if not joint_prim.IsA(UsdPhysics.FixedJoint):
                # CN.009 reports the wrong joint type.
                continue

            if _MUJOCO_JOINT_API in schemas:
                self._AddFailedCheck(
                    f"Connection joint '{joint_prim.GetPath()}' applies {_MUJOCO_JOINT_API}, which "
                    "marks a joint as a MuJoCo articulation degree of freedom.",
                    at=joint_prim,
                    requirement=requirement,
                )

            _check_contact_filtered(self, joint_prim, requirement)

        if joint_paths:
            self._check_actuators(default_prim, joint_paths, requirement)

    def _check_actuators(self, default_prim, joint_paths, requirement) -> None:
        for prim in Usd.PrimRange(default_prim):
            if str(prim.GetTypeName()) != _MUJOCO_ACTUATOR_TYPE:
                continue
            rel = prim.GetRelationship(_MUJOCO_ACTUATOR_TARGET_REL)
            if not rel:
                continue
            for target in rel.GetTargets():
                if str(target) in joint_paths:
                    self._AddFailedCheck(
                        f"MuJoCo actuator '{prim.GetPath()}' targets connection joint '{target}'; "
                        "a rigid attachment is not a controllable degree of freedom.",
                        at=prim,
                        requirement=requirement,
                    )


def _check_contact_filtered(checker, joint_prim: Usd.Prim, requirement) -> None:
    """Coincident coupling faces overlap, so contact on the pair fights the joint.

    All three runtime variants require the value to be authored rather than left
    to an importer default.
    """
    attr = UsdPhysics.Joint(joint_prim).GetCollisionEnabledAttr()
    if not attr or not attr.HasAuthoredValue():
        checker._AddFailedCheck(
            f"Connection joint '{joint_prim.GetPath()}' does not author "
            "physics:collisionEnabled = false; the coupling faces are coincident.",
            at=joint_prim,
            requirement=requirement,
        )
        return
    if bool(attr.Get()):
        checker._AddFailedCheck(
            f"Connection joint '{joint_prim.GetPath()}' has physics:collisionEnabled = true on "
            "coincident coupling faces; contact on that pair works against the joint.",
            at=attr,
            requirement=requirement,
        )


def _check_single_articulation_root(checker, connection, default_prim: Usd.Prim, requirement) -> None:
    """A connection between two articulated mate bodies fuses them into one articulation.

    The fused result is one articulation, so one root may survive. PhysX and Newton
    both require it; the plug asset's root is the one the assembly gives up.
    """
    socket = connection.socket_prim
    plug = connection.plug_prim
    if not socket or not plug:
        return
    socket_body = resolve_mate_body(socket)
    plug_body = resolve_mate_body(plug)
    if socket_body is None or plug_body is None:
        return
    if not (is_in_articulation(socket_body) and is_in_articulation(plug_body)):
        return

    roots = [
        prim for prim in Usd.PrimRange(default_prim) if prim.HasAPI(UsdPhysics.ArticulationRootAPI)
    ]
    if len(roots) > 1:
        checker._AddFailedCheck(
            f"Connection '{connection.path}' fuses two articulations, but the composed assembly "
            f"carries {len(roots)} articulation roots "
            f"({', '.join(str(p.GetPath()) for p in roots)}); exactly one may survive.",
            at=roots,
            requirement=requirement,
        )
