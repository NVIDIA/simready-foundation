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
from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class Requirement:
    """
    Args:
        code: A unique identifier of the requirement
        display_name: A human-readable name of the requirement
        message: A basic description of the requirement
        path: Relative path in documentation
        compatibility: Compatibility of the requirement
        tags: Tags of the requirement
        version: Version of the requirement
        parameters: Parameters of the requirement
        examples: Examples of the requirement
    """

    code: str
    display_name: str
    message: str
    path: Optional[str] = None
    compatibility: Optional[str] = None
    tags: Tuple[str, ...] = ()
    version: Optional[str] = "0.1.0"
    parameters: Tuple[Any, ...] = ()
    examples: Tuple[Any, ...] = ()


from .core.atomic_asset import validation
from .core.naming_paths import validation
from .core.sim_ready import validation
from .core.units import validation

# Import custom validation rules here, so they will be loaded and registered.
from .example import example
from .hierarchy import validation
from .isaac_sim.composition import validation
from .isaac_sim.robot_core import validation
from .isaac_sim.robot_materials import validation
from .nonvisual_sensors.nonvisual_materials import validation
from .packaging.conformance_metadata import validation
from .packaging.packaging_core import validation
from .packaging.packaging_introspection import validation
from .physics_bodies.base_articulation import validation
from .physics_bodies.physics_colliders import validation
from .physics_bodies.physics_driven_joints import validation
from .physics_bodies.physics_graspable import validation
from .physics_bodies.physics_joints import validation
from .physics_bodies.physics_materials import validation
from .physics_bodies.physics_rigid_bodies import validation
from .semantic_labels import validation
from .visualization.geometry import validation
from .visualization.materials import validation
