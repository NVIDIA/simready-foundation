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
"""Assembly/Mates validators (`MC.*`)."""

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Usd, UsdGeom

from ..utils import (
    INSERTION_VECTOR_NAME,
    INTERFACE_ATTR,
    KIND_ATTR,
    MAX_PAYLOAD_ATTR,
    PLUG_ROLE,
    SOCKET_ROLE,
    authored_token,
    iter_connections,
    iter_mate_sites,
    resolve_mate_body,
)

_MECHANICAL_ROLES = (SOCKET_ROLE, PLUG_ROLE)
_KNOWN_KINDS = ("Tool", "Gripper", "Sensor", "ToolChanger", "ManipulatorFlange")


@usd_validation_nvidia.register_rule("MateSiteDeclaration")
@usd_validation_nvidia.register_requirements(
    cap.MatesRequirements.MC_001,
    cap.MatesRequirements.MC_002,
    override=True,
)
class MateSiteDeclarationChecker(usd_validation_nvidia.BaseRuleChecker):
    """MC.001/MC.002: a mate site is an `Xform` with `domain` and a legal `role`."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for site in iter_mate_sites(default_prim):
            if not site.prim.IsA(UsdGeom.Xform):
                self._AddFailedCheck(
                    f"Mate site '{site.path}' is a '{site.prim.GetTypeName()}'; a mate site must be an Xform.",
                    at=site.prim,
                    requirement=cap.MatesRequirements.MC_001,
                )
            for name, value in (("simready:mate:domain", site.domain), ("simready:mate:role", site.role)):
                if not value:
                    self._AddFailedCheck(
                        f"Mate site '{site.path}' does not author a non-empty '{name}'.",
                        at=site.prim,
                        requirement=cap.MatesRequirements.MC_001,
                    )

            if site.is_mechanical and site.role and site.role not in _MECHANICAL_ROLES:
                self._AddFailedCheck(
                    f"Mechanical mate site '{site.path}' has role '{site.role}'; "
                    f"a mechanical role must be {SOCKET_ROLE} or {PLUG_ROLE}.",
                    at=site.prim,
                    requirement=cap.MatesRequirements.MC_002,
                )


@usd_validation_nvidia.register_rule("MechanicalSiteProperties")
@usd_validation_nvidia.register_requirements(
    cap.MatesRequirements.MC_004,
    cap.MatesRequirements.MC_006,
    cap.MatesRequirements.MC_007,
    override=True,
)
class MechanicalSitePropertiesChecker(usd_validation_nvidia.BaseRuleChecker):
    """MC.004/MC.006/MC.007: the `simready:mate:mechanical:` property table."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for site in iter_mate_sites(default_prim):
            if not site.is_mechanical:
                continue
            self._check_interface(site)
            self._check_max_payload(site)
            self._check_kind(site)

    def _check_interface(self, site) -> None:
        interface = authored_token(site.prim, INTERFACE_ATTR)
        if not interface:
            self._AddFailedCheck(
                f"Mechanical mate site '{site.path}' does not author a non-empty '{INTERFACE_ATTR}'.",
                at=site.prim,
                requirement=cap.MatesRequirements.MC_004,
            )

    def _check_max_payload(self, site) -> None:
        if site.role != SOCKET_ROLE:
            return
        attr = site.prim.GetAttribute(MAX_PAYLOAD_ATTR)
        if not attr or not attr.HasAuthoredValue():
            self._AddFailedCheck(
                f"Socket mate site '{site.path}' does not author '{MAX_PAYLOAD_ATTR}'.",
                at=site.prim,
                requirement=cap.MatesRequirements.MC_006,
            )
            return
        value = attr.Get()
        if value is None or float(value) <= 0.0:
            self._AddFailedCheck(
                f"Socket mate site '{site.path}' has {MAX_PAYLOAD_ATTR} = {value}; "
                "the rating must be a positive mass in kilograms.",
                at=attr,
                requirement=cap.MatesRequirements.MC_006,
            )

    def _check_kind(self, site) -> None:
        kind = authored_token(site.prim, KIND_ATTR)
        if kind is None or kind in _KNOWN_KINDS:
            return
        self._AddWarning(
            f"Mechanical mate site '{site.path}' has {KIND_ATTR} = '{kind}', "
            f"which is not one of {', '.join(_KNOWN_KINDS)}.",
            at=site.prim,
            requirement=cap.MatesRequirements.MC_007,
        )


@usd_validation_nvidia.register_rule("MateBody")
@usd_validation_nvidia.register_requirements(cap.MatesRequirements.MC_003, override=True)
class MateBodyChecker(usd_validation_nvidia.BaseRuleChecker):
    """MC.003: every mechanical mate site resolves to an enabled rigid-body ancestor."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        for site in iter_mate_sites(default_prim):
            if not site.is_mechanical:
                continue
            if resolve_mate_body(site.prim) is None:
                self._AddFailedCheck(
                    f"Mechanical mate site '{site.path}' has no ancestor with an enabled "
                    "PhysicsRigidBodyAPI, so it has no mate body.",
                    at=site.prim,
                    requirement=cap.MatesRequirements.MC_003,
                )


@usd_validation_nvidia.register_rule("MateInsertionVector")
@usd_validation_nvidia.register_requirements(cap.MatesRequirements.MC_005, override=True)
class MateInsertionVectorChecker(usd_validation_nvidia.BaseRuleChecker):
    """MC.005: an optional `mate_insertion_vector` child must be a usable two-point curve."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            return

        sites = list(iter_mate_sites(default_prim))
        for site in sites:
            child = site.prim.GetChild(INSERTION_VECTOR_NAME)
            if child and child.IsValid():
                self._check_curve(site, child)
        self._check_socket_precedence(stage, sites)

    def _check_curve(self, site, prim: Usd.Prim) -> None:
        requirement = cap.MatesRequirements.MC_005
        curves = UsdGeom.BasisCurves(prim)
        if not curves:
            self._AddFailedCheck(
                f"'{prim.GetPath()}' is a '{prim.GetTypeName()}'; an insertion vector must be a BasisCurves.",
                at=prim,
                requirement=requirement,
            )
            return

        curve_type = curves.GetTypeAttr().Get()
        if curve_type != UsdGeom.Tokens.linear:
            self._AddFailedCheck(
                f"Insertion vector '{prim.GetPath()}' has type '{curve_type}'; it must be 'linear'.",
                at=curves.GetTypeAttr(),
                requirement=requirement,
            )

        counts = curves.GetCurveVertexCountsAttr().Get()
        if list(counts or []) != [2]:
            self._AddFailedCheck(
                f"Insertion vector '{prim.GetPath()}' has curveVertexCounts {list(counts or [])}; "
                "it must be a single two-point segment [2].",
                at=curves.GetCurveVertexCountsAttr(),
                requirement=requirement,
            )
            return

        points = curves.GetPointsAttr().Get()
        if points is None or len(points) != 2:
            self._AddFailedCheck(
                f"Insertion vector '{prim.GetPath()}' declares two vertices but authors "
                f"{0 if points is None else len(points)} points.",
                at=curves.GetPointsAttr(),
                requirement=requirement,
            )
            return

        if Gf.Vec3f(points[1] - points[0]).GetLength() == 0.0:
            self._AddFailedCheck(
                f"Insertion vector '{prim.GetPath()}' has a zero-length direction; "
                "p1 - p0 must be non-zero.",
                at=curves.GetPointsAttr(),
                requirement=requirement,
            )

    def _check_socket_precedence(self, stage: Usd.Stage, sites) -> None:
        """Warn when both sides of a pairing author a vector; the socket wins."""
        with_vector = {
            site.path for site in sites if site.prim.GetChild(INSERTION_VECTOR_NAME)
        }
        for connection in iter_connections(stage):
            socket = connection.socket_prim
            plug = connection.plug_prim
            if not socket or not plug:
                continue
            if str(socket.GetPath()) in with_vector and str(plug.GetPath()) in with_vector:
                self._AddWarning(
                    f"Connection '{connection.path}' has an insertion vector on both the socket "
                    f"'{socket.GetPath()}' and the plug '{plug.GetPath()}'; the socket vector wins.",
                    at=plug,
                    requirement=cap.MatesRequirements.MC_005,
                )
