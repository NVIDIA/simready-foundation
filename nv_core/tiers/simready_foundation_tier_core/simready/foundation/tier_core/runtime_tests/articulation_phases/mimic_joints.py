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
"""PhysX and Newton mimic-joint detection for the MIM phase.

MCP lookup (resolved 2026-04-24 in plan Task 1 Step 1):
- MCP did not return PhysxMimicJointAPI attribute tokens; accessor names
  verified at test time via PhysxSchema.PhysxMimicJointAPI.Apply on a live
  in-memory stage.
  If the mimic attribute names below do not match the live schema, update
  _read_reference_target, _read_gear, and _read_offset accordingly.
"""

import math
from dataclasses import dataclass

from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_utils import (  # noqa: F401  (imported for parity)
    safe_len,
)


@dataclass(frozen=True)
class MimicJointSpec:
    follower_joint_path: str
    reference_joint_path: str
    gear: float
    offset: float
    follower_dof_index: int | None
    reference_dof_index: int | None
    backend: str = "physx"


def detect_mimic_joints(stage, asset_prim, robot_prim_path, dof_names):
    # type: (Any, Any, str, list[str]) -> list[MimicJointSpec]
    """Return one specification per supported mimic joint under ``asset_prim``.

    Returns [] when stage/asset_prim is invalid or no mimic joints are authored.
    A mimic without exactly one resolved joint inside the asset search root
    is skipped. Native USD relationship forwarding is supported.

    Uses Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate) so instanced robots
    are handled correctly (foundation spec 10.5).
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return []
    try:
        from pxr import UsdPhysics
    except Exception:
        return []
    try:
        from pxr import PhysxSchema
    except Exception:
        try:
            from physx_usd_schemas import PhysxSchema
        except ImportError:
            PhysxSchema = None

    from .joint_identity import joint_for_native_name, selected_joint_prims

    iter_root = asset_prim
    selected_joints = selected_joint_prims(stage, robot_prim_path, dof_names, asset_prim)
    selected_paths = {str(joint.GetPath()) for joint in selected_joints}

    def selected_index(path):
        if path not in selected_paths:
            raise RuntimeError(f"Mimic reference is outside its articulation: {path}")
        indices = [
            index
            for index, name in enumerate(dof_names)
            if (joint := joint_for_native_name(selected_joints, name)) is not None and str(joint.GetPath()) == path
        ]
        if len(indices) > 1:
            raise RuntimeError(f"Mimic joint has ambiguous native coordinates: {path}")
        return indices[0] if indices else None

    results = []
    for prim in selected_joints:
        if not (prim.IsA(UsdPhysics.RevoluteJoint) or prim.IsA(UsdPhysics.PrismaticJoint)):
            continue
        enabled_attr = prim.GetAttribute("physics:jointEnabled")
        if enabled_attr and enabled_attr.Get() is False:
            continue

        # Newton uses a single-apply API and the absolute equation
        # follower = mimicCoef0 + mimicCoef1 * reference.
        try:
            applied_api_schemas = list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        except Exception:
            applied_api_schemas = list(prim.GetAppliedSchemas())
        raw_api_names = _raw_applied_api_names(prim)
        has_newton_mimic = (
            prim.HasAPI("NewtonMimicAPI")
            or "NewtonMimicAPI" in applied_api_schemas
            or "NewtonMimicAPI" in raw_api_names
        )
        newton_enabled = True
        if has_newton_mimic:
            enabled_attr = prim.GetAttribute("newton:mimicEnabled")
            newton_enabled = enabled_attr.Get() if enabled_attr and enabled_attr.HasAuthoredValue() else True
        if has_newton_mimic and newton_enabled:
            rel = prim.GetRelationship("newton:mimicJoint")
            ref_path = _resolve_reference_joint(rel, iter_root)
            if ref_path:
                coef0 = _read_float_attribute(prim, "newton:mimicCoef0", 0.0)
                coef1 = _read_float_attribute(prim, "newton:mimicCoef1", 1.0)
                results.append(
                    MimicJointSpec(
                        follower_joint_path=str(prim.GetPath()),
                        reference_joint_path=ref_path,
                        gear=coef1,
                        offset=coef0,
                        follower_dof_index=selected_index(str(prim.GetPath())),
                        reference_dof_index=selected_index(str(ref_path)),
                        backend="newton",
                    )
                )
            continue

        # PhysxMimicJointAPI is a multi-apply schema where the instance name IS
        # the axis token (rotX/rotY/rotZ for revolute, transX/transY/transZ for
        # prismatic, or the short X/Y/Z spelling). A joint may carry one or more
        # applied instances; iterate
        # them all so prismatic joints and joints on Y/Z axes are not silently
        # ignored.
        #
        # IMPORTANT: We iterate ``GetPrimTypeInfo().GetAppliedAPISchemas()``
        # (the raw apiSchemas metadata) rather than ``GetAppliedSchemas()``,
        # because the public accessor filters to REGISTERED schemas only and
        # some assets carry PhysxMimicJointAPI
        # instances that don't always resolve through the public accessor.
        # The raw metadata accessor never filters and always shows the
        # ``PhysxMimicJointAPI:rotX`` form. We also drop the
        # ``prim.HasAPI(PhysxMimicJointAPI)`` pre-filter (its multi-apply
        # behavior without an instance name is inconsistent across USD
        # versions) and let the schema-name iteration be the only gate.
        try:
            applied_schemas = list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        except Exception:
            applied_schemas = list(prim.GetAppliedSchemas())
        for schema_name in applied_schemas:
            if not schema_name.startswith("PhysxMimicJointAPI:"):
                continue
            if PhysxSchema is None:
                continue
            instance_name = schema_name.split(":", 1)[1]
            # USD token values are not their Python attribute names: Tokens.z
            # is "Z", whereas Tokens.Z does not exist. Keep the authored
            # namespace (including short X/Y/Z allowed by DJ.007) unchanged.
            supported_axes = (
                UsdPhysics.Tokens.rotX,
                UsdPhysics.Tokens.rotY,
                UsdPhysics.Tokens.rotZ,
                UsdPhysics.Tokens.transX,
                UsdPhysics.Tokens.transY,
                UsdPhysics.Tokens.transZ,
                UsdPhysics.Tokens.x,
                UsdPhysics.Tokens.y,
                UsdPhysics.Tokens.z,
            )
            if instance_name not in supported_axes:
                # Unknown instances cannot provide a response pair. Required
                # ownership/discovery callers still check raw authored APIs;
                # this is not evidence that coupling is absent or safe.
                continue

            mimic = PhysxSchema.PhysxMimicJointAPI(prim, instance_name)
            ref_path = _read_reference_target(mimic, iter_root)
            if not ref_path:
                continue
            gear = _read_gear(mimic)
            offset = _read_offset(mimic)

            follower_dof_index = selected_index(str(prim.GetPath()))
            reference_dof_index = selected_index(str(ref_path))

            results.append(
                MimicJointSpec(
                    follower_joint_path=str(prim.GetPath()),
                    reference_joint_path=str(ref_path),
                    gear=float(gear),
                    offset=float(offset),
                    follower_dof_index=follower_dof_index,
                    reference_dof_index=reference_dof_index,
                    backend="physx",
                )
            )
    return results


def detect_mimic_follower_indices(stage, asset_prim, robot_prim_path, dof_names, *, validate_selected=False):
    """Return visible selected dependents after complete raw coupling validation.

    Required setup opts into selected physical/equation validation. The legacy
    raw mode conservatively excludes visible authored followers without
    certifying their equations, for the separate mimic-response diagnostic.
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        raise RuntimeError("Required mimic ownership discovery needs a valid loaded asset")
    from types import SimpleNamespace

    from simready.foundation.tier_core.runtime_tests.articulation_phases.fingertip_discovery import (
        _discovery_scope,
        _validated_mimic_ownership,
    )

    if asset_prim.GetStage() != stage:
        raise RuntimeError("Required mimic ownership discovery asset belongs to a different stage")
    if validate_selected:
        robot = SimpleNamespace(prim_path=robot_prim_path, asset_prim=asset_prim, dof_names=list(dof_names))
        analysis_root, selected_paths = _discovery_scope(stage, robot, None)
        mimics = detect_mimic_joints(stage, asset_prim, robot_prim_path, robot.dof_names)
        validated = _validated_mimic_ownership(stage, robot, asset_prim, mimics, selected_paths, ())
        return {spec.follower_dof_index for spec in validated if spec.follower_dof_index is not None}
    from pxr import UsdPhysics

    names, followers = list(dof_names), set()
    from .joint_identity import joint_for_native_name, selected_joint_prims

    selected = selected_joint_prims(stage, robot_prim_path, names, asset_prim)
    for prim in selected:
        raw_names = set(_raw_applied_api_names(prim)) | set(prim.GetAppliedSchemas())
        if not any(name == "NewtonMimicAPI" or name.startswith("PhysxMimicJointAPI:") for name in raw_names):
            continue
        if not prim.IsA(UsdPhysics.Joint):
            raise RuntimeError("Authored mimic ownership is not on a supported joint: %s" % prim.GetPath())
        if prim.GetAttribute("physics:jointEnabled").Get() is False:
            continue
        if "NewtonMimicAPI" in raw_names:
            enabled = prim.GetAttribute("newton:mimicEnabled")
            if enabled and enabled.HasAuthoredValue() and not enabled.Get():
                if not any(name.startswith("PhysxMimicJointAPI:") for name in raw_names):
                    continue
        indices = [i for i, name in enumerate(names) if joint_for_native_name(selected, name) == prim]
        if len(indices) != 1:
            raise RuntimeError(
                "Authored mimic follower %s cannot be uniquely mapped to a runtime DOF; "
                "independent control ownership is unknown" % prim.GetPath()
            )
        followers.add(indices[0])
    return followers


def _raw_applied_api_names(prim):
    """Return authored apiSchemas tokens, including schemas unknown to this USD build."""
    try:
        value = prim.GetMetadata("apiSchemas")
        names = []
        for field in ("explicitItems", "prependedItems", "appendedItems", "addedItems"):
            names.extend(str(item) for item in (getattr(value, field, None) or []))
        return names
    except Exception:
        return []


def _coefficient_value(value, default):
    # Only genuine absence/None uses the existing schema fallback. A failed
    # selected query/conversion must never invent a coefficient for the verdict.
    value = float(default if value is None else value)
    if not math.isfinite(value):
        raise RuntimeError("Required mimic coefficient must be finite")
    return value


def _read_float_attribute(prim, name, default):
    attr = prim.GetAttribute(name)
    value = attr.Get() if attr and attr.IsValid() else None
    return _coefficient_value(value, default)


def _read_reference_target(mimic, root_prim):
    # type: (Any, Any) -> Optional[str]
    from pxr import Tf

    try:
        return _resolve_reference_joint(mimic.GetReferenceJointRel(), root_prim)
    except Tf.ErrorException:
        return None


def _resolve_reference_joint(relationship, root_prim):
    """Resolve one bounded joint, never an alias property or arbitrary first target."""
    from pxr import Tf, UsdPhysics

    if not relationship or not relationship.IsValid():
        return None
    try:
        targets = relationship.GetForwardedTargets()
        if len(targets) != 1:
            return None
        target = targets[0]
        if not target.IsAbsolutePath() or not target.IsPrimPath() or not target.HasPrefix(root_prim.GetPath()):
            return None
        joint = relationship.GetStage().GetPrimAtPath(target)
        if not joint or not joint.IsA(UsdPhysics.Joint) or joint == relationship.GetPrim():
            return None
        return str(target)
    except Tf.ErrorException:
        return None


def _read_gear(mimic):
    # type: (Any) -> float
    return _coefficient_value(mimic.GetGearingAttr().Get(), 1.0)


def _read_offset(mimic):
    # type: (Any) -> float
    return _coefficient_value(mimic.GetOffsetAttr().Get(), 0.0)


def _find_dof_index(dof_names, joint_name):
    # type: (list[str], str) -> Optional[int]
    try:
        return dof_names.index(joint_name)
    except ValueError:
        return None
