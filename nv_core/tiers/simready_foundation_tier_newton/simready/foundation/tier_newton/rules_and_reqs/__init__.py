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

"""Capabilities hub for the Newton tier.

Importing this package imports every Newton validator module so their
``@register_rule`` / ``@register_requirements`` decorators register this tier's
rules and requirements. Newton validators are self-contained: they use this
tier's own duplicated helper functions and its own generated requirements enum,
with no import of ``simready-foundation-tier-core``.
"""

from .physics_bodies.base_articulation import validation  # noqa: F401
from .physics_bodies.physics_driven_joints import validation  # noqa: F401
from .physics_bodies.physics_materials import validation  # noqa: F401
from .physics_bodies.physics_rigid_bodies import validation  # noqa: F401
