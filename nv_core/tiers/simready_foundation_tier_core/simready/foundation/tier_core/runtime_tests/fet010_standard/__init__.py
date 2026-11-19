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
"""FET010 display colour response tests.

Display colour is a primvar rather than a material, so there is no surface on
the asset to isolate. What these tests do instead is bind the material DISP.001's
Guidance nominates -- an OpenPBR surface driven by MaterialX primvar readers --
over the asset through strong all-purpose/full/preview bindings on a test-owned
enclosing ancestor. Nested instances are expanded in the disposable session
layer and both read materials are primed before measured swaps. Source layers,
primvars and bindings are preserved. The response qualifies the expanded scene,
not the original instanced rendering path or complete per-Gprim coverage.
"""
