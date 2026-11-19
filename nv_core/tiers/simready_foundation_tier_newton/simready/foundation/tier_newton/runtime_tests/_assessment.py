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

"""Applicability evidence for a positively established absence of test behavior."""


def not_applicable(reason_code, reason):
    """Build evidence; the caller publishes it before recording its clean skip."""
    return {"status": "not_applicable", "reason_code": reason_code, "reason": reason}


def _log_applicability_gap(ctx, reason):
    """Diagnostics must never turn an unqualified legacy skip into an error."""
    try:
        ctx.log(f"Applicability proof incomplete: {reason}; retaining unmarked skip (Could not assess).")
    except Exception:
        pass
    return False


def _has_complete_asset_composition(stage, asset_prim, *, ctx=None, inspection_includes_instance_proxies=False):
    """Qualify owned composition, not the detector's classification or commands.

    The root must be the full loaded asset, never only its articulation root.
    Proxy-aware composition does not establish a legacy detector inspected those
    sources: callers must separately establish that inspection before opting in.
    """
    try:
        from pxr import Usd

        if stage is None or asset_prim is None:
            return _log_applicability_gap(ctx, "the full asset stage/root is unavailable")
        if (
            not asset_prim
            or not asset_prim.IsValid()
            or asset_prim.IsPseudoRoot()
            or not asset_prim.IsActive()
            or not asset_prim.IsDefined()
            or asset_prim.IsAbstract()
            or asset_prim.GetStage() != stage
            or stage.GetPrimAtPath(asset_prim.GetPath()) != asset_prim
        ):
            return _log_applicability_gap(ctx, "the full asset root is not a valid active concrete same-stage prim")
        if not stage.GetPopulationMask().IncludesSubtree(asset_prim.GetPath()):
            return _log_applicability_gap(ctx, "the population mask does not include the full asset subtree")
        # USD composition-error ownership is not universally attributable. Any
        # unresolved stage error conservatively prevents a positive absence claim.
        if stage.GetCompositionErrors():
            return _log_applicability_gap(ctx, "USD reports unresolved composition errors")
        for prim in Usd.PrimRange(asset_prim, Usd.TraverseInstanceProxies(Usd.PrimIsActive)):
            if not prim.IsValid() or not prim.IsDefined() or prim.IsAbstract() or not prim.IsLoaded():
                return _log_applicability_gap(
                    ctx, "the owned inventory contains unloaded, undefined or abstract content"
                )
            if prim.IsInstanceProxy() and not inspection_includes_instance_proxies:
                return _log_applicability_gap(
                    ctx, "instance-proxy source inspection is not established for this marker"
                )
        return True
    except Exception:
        return _log_applicability_gap(ctx, "the owned composition inventory could not be queried")


def _has_current_coordinate_exclusions(robot, scene_info, *, ctx=None):
    """Recheck cached control exclusions solely to qualify applicability evidence."""
    try:
        stage, asset = scene_info.get("stage"), scene_info.get("asset_prim")
        if not _has_complete_asset_composition(stage, asset, ctx=ctx):
            return False

        from .articulation_phases._independent_dofs import (
            control_ownership,
            excluded_dof_indices,
            validate_indices,
        )
        from .articulation_phases.passive_joints import detect_passive_joints

        names = list(robot.dof_names)
        cached = excluded_dof_indices(scene_info, len(names))
        passive, _ = detect_passive_joints(stage, robot.prim_path, names, asset_prim=asset, strict_sources=True)
        followers, _, loops, _ = control_ownership(stage, asset, robot.prim_path, names, strict_sources=True)
        current = validate_indices([*passive, *followers, *loops], len(names))
        if current != cached:
            return _log_applicability_gap(ctx, "cached coordinate exclusions do not match current control ownership")
        return True
    except Exception:
        return _log_applicability_gap(ctx, "current coordinate control ownership could not be established")


def _has_complete_prim_ancestry(stage, prim, *, ctx=None):
    """Qualify every prim read when resolving an external source or body owner."""
    try:
        if stage is None or not prim or prim.IsPseudoRoot() or stage.GetCompositionErrors():
            return _log_applicability_gap(ctx, "a required source dependency is unavailable or unresolved")
        mask = stage.GetPopulationMask()
        while prim and not prim.IsPseudoRoot():
            if (
                not prim.IsValid()
                or prim.GetStage() != stage
                or stage.GetPrimAtPath(prim.GetPath()) != prim
                or not prim.IsActive()
                or not prim.IsDefined()
                or prim.IsAbstract()
                or not prim.IsLoaded()
                or not mask.IncludesSubtree(prim.GetPath())
            ):
                return _log_applicability_gap(ctx, "required source ancestry is incomplete, masked or non-concrete")
            prim = prim.GetParent()
        return True
    except Exception:
        return _log_applicability_gap(ctx, "required source ancestry could not be queried")


def _has_complete_relationship_sources(stage, relationship, *, ctx=None, _visiting=None):
    """Qualify native forwarding sources without replacing USD target resolution."""
    try:
        if not relationship or not _has_complete_prim_ancestry(stage, relationship.GetPrim(), ctx=ctx):
            return False
        visiting = set() if _visiting is None else set(_visiting)
        path = relationship.GetPath()
        if path in visiting:
            return _log_applicability_gap(ctx, "required relationship forwarding is cyclic")
        visiting.add(path)
        direct = list(relationship.GetTargets())
        for target in direct:
            if not target.IsAbsolutePath():
                return _log_applicability_gap(ctx, "a required relationship target is not absolute")
            if target.IsPropertyPath():
                source = stage.GetPropertyAtPath(target)
                if not source or not _has_complete_prim_ancestry(stage, source.GetPrim(), ctx=ctx):
                    return False
                forwarded = stage.GetRelationshipAtPath(target)
                if forwarded and not _has_complete_relationship_sources(stage, forwarded, ctx=ctx, _visiting=visiting):
                    return False
            elif not target.IsPrimPath() or not _has_complete_prim_ancestry(
                stage, stage.GetPrimAtPath(target), ctx=ctx
            ):
                return False
        if direct and not relationship.GetForwardedTargets():
            return _log_applicability_gap(ctx, "required relationship forwarding did not resolve")
        return True
    except Exception:
        return _log_applicability_gap(ctx, "required relationship forwarding sources could not be queried")


def _has_complete_scene_asset(ctx, *, inspection_includes_instance_proxies=False):
    """Resolve the scene's full asset boundary without changing load state."""
    try:
        import omni.usd

        stage = omni.usd.get_context().get_stage()
        asset = ctx.scene.asset
        root = stage.GetPrimAtPath(asset.prim_path) if stage is not None and asset is not None else None
        return _has_complete_asset_composition(
            stage, root, ctx=ctx, inspection_includes_instance_proxies=inspection_includes_instance_proxies
        )
    except Exception:
        return _log_applicability_gap(ctx, "the scene's full asset stage/root could not be queried")
