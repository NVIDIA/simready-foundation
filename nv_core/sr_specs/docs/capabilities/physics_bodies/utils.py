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

from omni.asset_validator import BaseRuleChecker

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdUtils


def get_stage_id(stage: Usd.Stage):
    stage_id = UsdUtils.StageCache.Get().GetId(stage).ToLongInt()
    if stage_id == -1:
        stage_id = UsdUtils.StageCache.Get().Insert(stage).ToLongInt()
    return stage_id


def _is_dynamic_body(usd_prim: Usd.Prim) -> bool:
    rb_api = UsdPhysics.RigidBodyAPI(usd_prim)
    if rb_api:
        is_api_schema_enabled = rb_api.GetRigidBodyEnabledAttr().Get()
        return is_api_schema_enabled
    return False


class BaseRuleCheckerWCache(BaseRuleChecker):
    def __init__(self, verbose: bool, consumerLevelChecks: bool, assetLevelChecks: bool):
        super().__init__(verbose, consumerLevelChecks, assetLevelChecks)
        self.InitCaches()

    def InitCaches(self):
        self._xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        self._is_a_or_under_a_dynamic_body_cache = dict()
        self._is_under_articulation_root_cache = dict()

    def ResetCaches(self):
        self._xform_cache.Clear()
        self._is_a_or_under_a_dynamic_body_cache.clear()
        self._is_under_articulation_root_cache.clear()

    def _cache_value_to_list(self, cache: dict, value: tuple[bool, Usd.Prim], prim_paths: list[Sdf.Path]):
        for path in prim_paths:
            cache[path] = value

    def _is_under_articulation_root(self, usd_prim: Usd.Prim) -> bool:
        path = usd_prim.GetPath()
        prim_list = []
        current = usd_prim.GetParent()
        while current and current != usd_prim.GetStage().GetPseudoRoot():
            prim_list.append(path)
            path = current.GetPath()
            cached = self._is_under_articulation_root_cache.get(path)
            if cached is not None:
                self._cache_value_to_list(self._is_under_articulation_root_cache, cached, prim_list)
                return cached

            art_api = UsdPhysics.ArticulationRootAPI(current)
            if art_api:
                self._cache_value_to_list(self._is_under_articulation_root_cache, True, prim_list)
                return True

            current = current.GetParent()

        self._cache_value_to_list(self._is_under_articulation_root_cache, False, prim_list)
        return False

    def _scale_is_uniform(self, scale: Gf.Vec3d) -> bool:
        eps = 1.0e-5
        # Find min and max scale values
        if scale[0] < scale[1]:
            lo, hi = scale[0], scale[1]
        else:
            lo, hi = scale[1], scale[0]

        if scale[2] < lo:
            lo = scale[2]
        elif scale[2] > hi:
            hi = scale[2]

        if lo * hi < 0.0:
            return False  # opposite signs

        return hi - lo <= eps * lo if hi > 0.0 else lo - hi >= eps * hi

    def _check_non_uniform_scale(self, xformable: UsdGeom.Xformable) -> bool:
        tr = Gf.Transform(self._xform_cache.GetLocalToWorldTransform(xformable.GetPrim()))
        sc = tr.GetScale()
        return self._scale_is_uniform(sc)

    def _has_dynamic_body_parent(self, usd_prim: Usd.Prim, rb_api: UsdPhysics.RigidBodyAPI) -> tuple[bool, Usd.Prim]:
        # early exit on disabled RB, no cache information
        if rb_api and not rb_api.GetRigidBodyEnabledAttr().Get():
            return False, None

        # early exit on immediate xformstack reset
        path = usd_prim.GetPath()
        xform = UsdGeom.Xformable(usd_prim)
        if xform and xform.GetResetXformStack():
            # save True to cache for children and point to me
            self._cache_value_to_list(self._is_a_or_under_a_dynamic_body_cache, (True, usd_prim), [path])
            return False, None

        # look for either a dynamic body or an xformstack reset towards the root
        # apply cache downwards to all children on exit
        prim_list = []
        current = usd_prim.GetParent()
        while current != usd_prim.GetStage().GetPseudoRoot():
            path = current.GetPath()
            cached = self._is_a_or_under_a_dynamic_body_cache.get(path)
            if cached is not None:
                self._cache_value_to_list(self._is_a_or_under_a_dynamic_body_cache, cached, prim_list)
                return cached[0], cached[1]

            prim_list.append(path)

            # first check dynamic body
            if _is_dynamic_body(current):
                self._cache_value_to_list(self._is_a_or_under_a_dynamic_body_cache, (True, current), prim_list)
                self._is_a_or_under_a_dynamic_body_cache[usd_prim.GetPath()] = (True, usd_prim)
                return True, current

            # then check xformstack reset
            xform = UsdGeom.Xformable(current)
            if xform and xform.GetResetXformStack():
                # save False, I am not a dynamic body (checked above) and reset was encountered
                self._cache_value_to_list(self._is_a_or_under_a_dynamic_body_cache, (False, None), prim_list)
                return False, None

            current = current.GetParent()

        # nothing found until root encountered
        self._cache_value_to_list(self._is_a_or_under_a_dynamic_body_cache, (False, None), prim_list)

        return False, None
