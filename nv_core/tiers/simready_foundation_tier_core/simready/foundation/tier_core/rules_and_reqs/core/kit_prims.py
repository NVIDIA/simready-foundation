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
"""Omniverse Kit viewport prims that validators treat as editor scaffolding, not asset content."""

from pxr import Sdf

_OMNI_PRIM_PATHS = {
    Sdf.Path("/OmniverseKit_Persp"),
    Sdf.Path("/OmniverseKit_Front"),
    Sdf.Path("/OmniverseKit_Top"),
    Sdf.Path("/OmniverseKit_Right"),
    Sdf.Path("/OmniKit_Viewport_LightRig"),
}
_OMNI_PRIM_NAMES = {"OmniverseKitViewportCameraMesh"}


def is_omni_path(path: Sdf.Path) -> bool:
    return path in _OMNI_PRIM_PATHS or path.name in _OMNI_PRIM_NAMES
