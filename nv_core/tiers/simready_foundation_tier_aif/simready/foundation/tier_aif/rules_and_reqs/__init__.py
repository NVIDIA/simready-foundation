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

# AIF Capabilities
#
# The old sr_specs framework (feature/aif) discovered these validators through
# its own plugin mechanism, so this file had no imports there. The tier
# framework instead relies on importing this hub to trigger each validator
# module's @register_rule / @register_requirements decorators (see
# _plugin.py:SimReadyPlugin.on_startup) -- these imports are new in the port,
# not carried over, and are what makes registration actually happen.
from .aif.connection_points import validation
from .aif.electrical import validation
from .aif.metadata import validation
from .aif.thermal_cooling import validation
