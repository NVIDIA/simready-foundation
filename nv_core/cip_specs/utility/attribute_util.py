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
from pxr import Usd


def replace_attr_name_prefix(prim: Usd.Prim, attr_prefix_replacement: list):
    """
    Replace attribute name prefixes for all attributes in a prim hierarchy.

    Args:
        prim: The root prim to start the search from
        attr_prefix_replacement: List of [old_prefix, new_prefix] pairs
    """
    # Loop through all prims starting from the given prim
    for current_prim in Usd.PrimRange(prim):
        for attr in current_prim.GetAttributes():
            for prefix, replacement in attr_prefix_replacement:
                if attr.GetName().startswith(prefix):
                    # Get the old attribute name and create the new one
                    old_name = attr.GetName()
                    new_name = old_name.replace(prefix, replacement)

                    # Get the attribute value and type info
                    attr_value = attr.Get()
                    attr_type = attr.GetTypeName()

                    # Create the new attribute with the same type
                    new_attr = current_prim.CreateAttribute(new_name, attr_type)

                    # Copy the value to the new attribute
                    new_attr.Set(attr_value)

                    # Copy any metadata if present
                    if attr.HasMetadata("doc"):
                        new_attr.SetMetadata("doc", attr.GetMetadata("doc"))

                    # Remove the old attribute
                    current_prim.RemoveProperty(old_name)
