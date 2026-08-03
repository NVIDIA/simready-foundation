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

"""
SimReady Foundation validation package.

This package provides validation rules, capabilities, and features for
SimReady Foundation assets. It integrates with the Omniverse Asset Validator
in two ways:

1. CLI wrapper: python -m simready.foundation.core (works with Asset Validator 1.15.0+)
2. Entrypoint plugin: Auto-discovered (works with Asset Validator 1.15.0+)
"""

from ._plugin import SimReadyPlugin

__all__ = ["SimReadyPlugin"]
