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
"""FET006 display colour tests.

Display colour is a primvar rather than a material, so there is no surface on
the asset to isolate. What these tests do instead is bind the material DISP.001's
Guidance nominates -- an OpenPBR surface driven by MaterialX primvar readers --
over the whole asset through one ``strongerThanDescendants`` binding on the
asset's root prim, and swap the reader in and out behind it. The frames differ
only by which material is bound, so nothing on the asset is edited.
"""
