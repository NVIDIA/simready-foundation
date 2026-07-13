# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

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
