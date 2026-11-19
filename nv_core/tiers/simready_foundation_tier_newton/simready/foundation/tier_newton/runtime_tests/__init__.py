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
"""SimReady Newton Evaluate suite for Kit/Isaac Sim.

This package contains the Newton-engine FET test implementations owned by the
``simready-foundation-tier-newton`` tier. Tests are discovered from the tier's
``runtime_tests_path`` descriptor field, additively alongside the Core suite.

The bundled canonical ``benchmark-provider.json`` declares the public namespace
``simready.foundation.tier_newton.runtime_tests`` as both the provider identity
and import package. It retains ``simready_benchmark_newton_suite`` as a provider
selector alias.

The Newton tier owns its test decorators, defaults, verdict procedures, scene
setup, articulation backend, and optional motion observer. It does not import
Core run_* procedures or Core decorator metadata. Placement and diagnostic
helpers are owned locally; the evaluate extra supplies engine dependencies,
not Core runtime-test modules.
No Newton close/lift gripper contract is added by this ownership split.
"""
