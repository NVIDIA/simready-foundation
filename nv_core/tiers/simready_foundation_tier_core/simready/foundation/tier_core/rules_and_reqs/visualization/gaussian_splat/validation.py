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

__all__ = ["GaussianSplatCapabilityChecker"]


import simready.foundation.tier_core.requirements as cap
from usd_validation_nvidia import (
    BaseRuleChecker,
    register_requirements,
)
from pxr import Usd


# OpenUSD schema type name for a 3D Gaussian Splat prim (UsdVol, OpenUSD 26.03+).
SPLAT_TYPE_NAME = "ParticleField3DGaussianSplat"

# Per-Gaussian attributes required on every splat prim.
POSITIONS_ATTR = "positions"
SCALES_ATTR = "scales"
ORIENTATIONS_ATTR = "orientations"
OPACITIES_ATTR = "opacities"
RADIANCE_DEGREE_ATTR = "radiance:sphericalHarmonicsDegree"
RADIANCE_COEFFS_ATTR = "radiance:sphericalHarmonicsCoefficients"


@register_requirements(
    cap.GaussianSplatRequirements.SPL_001,
    cap.GaussianSplatRequirements.SPL_002,
    cap.GaussianSplatRequirements.SPL_003,
    cap.GaussianSplatRequirements.SPL_004,
    cap.GaussianSplatRequirements.SPL_005,
    cap.GaussianSplatRequirements.SPL_006,
)
class GaussianSplatCapabilityChecker(BaseRuleChecker):
    """
    Validates the following 3D Gaussian Splat requirements:

    - **SPL.001**: The asset's visual representation is a
      ``ParticleField3DGaussianSplat`` prim (at least one exists in the stage).
    - **SPL.002**: Each splat prim authors ``positions``.
    - **SPL.003**: Each splat prim authors ``scales`` (length == positions).
    - **SPL.004**: Each splat prim authors ``orientations`` (length == positions).
    - **SPL.005**: Each splat prim authors ``opacities`` (length == positions).
    - **SPL.006**: Each splat prim authors ``radiance:sphericalHarmonicsDegree``
      and ``radiance:sphericalHarmonicsCoefficients`` with a coefficient count
      equal to ``len(positions) * (degree + 1) ** 2``.

    SPL.001 is reported once per stage. SPL.002-SPL.006 are reported per splat
    prim.
    """

    def CheckStage(self, stage: Usd.Stage):
        # SPL.001 - the asset's visual representation must be a splat: at least
        # one ParticleField3DGaussianSplat prim must exist in the stage.
        has_splat = any(
            prim.GetTypeName() == SPLAT_TYPE_NAME for prim in stage.Traverse()
        )
        if not has_splat:
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_001,
                message=(
                    "No 'ParticleField3DGaussianSplat' prim found. FET_012 "
                    "requires the asset's visual representation to be a 3D "
                    "Gaussian Splat."
                ),
                at=stage,
            )

    @staticmethod
    def _not_authored(prim: Usd.Prim, what: str) -> str:
        """Message for a splat prim that does not author ``what``."""
        return f"3DGS prim <{prim.GetPath()}> does not author {what}."

    def CheckPrim(self, prim: Usd.Prim):
        if prim.GetTypeName() != SPLAT_TYPE_NAME:
            return
        num_gaussians = self._check_positions(prim)
        self._check_per_gaussian_arrays(prim, num_gaussians)
        self._check_radiance(prim, num_gaussians)

    def _check_positions(self, prim: Usd.Prim):
        """SPL.002 - ``positions`` authored and non-empty; returns the count."""
        positions_attr = prim.GetAttribute(POSITIONS_ATTR)
        if not positions_attr or not positions_attr.HasAuthoredValue():
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_002,
                message=self._not_authored(prim, f"'{POSITIONS_ATTR}'"),
                at=prim,
            )
            return None
        positions = positions_attr.Get()
        num_gaussians = len(positions) if positions is not None else 0
        if num_gaussians == 0:
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_002,
                message=(
                    f"3DGS prim <{prim.GetPath()}> authors an empty "
                    f"'{POSITIONS_ATTR}' array."
                ),
                at=prim,
            )
        return num_gaussians

    def _check_per_gaussian_arrays(self, prim: Usd.Prim, num_gaussians):
        """SPL.003 / SPL.004 / SPL.005 - per-Gaussian arrays, length == positions."""
        for attr_name, requirement in (
            (SCALES_ATTR, cap.GaussianSplatRequirements.SPL_003),
            (ORIENTATIONS_ATTR, cap.GaussianSplatRequirements.SPL_004),
            (OPACITIES_ATTR, cap.GaussianSplatRequirements.SPL_005),
        ):
            attr = prim.GetAttribute(attr_name)
            if not attr or not attr.HasAuthoredValue():
                self._AddFailedCheck(
                    requirement=requirement,
                    message=self._not_authored(prim, f"'{attr_name}'"),
                    at=prim,
                )
                continue
            if not num_gaussians:
                continue
            values = attr.Get()
            count = len(values) if values is not None else 0
            if count != num_gaussians:
                self._AddFailedCheck(
                    requirement=requirement,
                    message=(
                        f"3DGS prim <{prim.GetPath()}> '{attr_name}' has "
                        f"{count} entries but '{POSITIONS_ATTR}' has "
                        f"{num_gaussians}."
                    ),
                    at=prim,
                )

    def _check_radiance(self, prim: Usd.Prim, num_gaussians):
        """SPL.006 - radiance: degree + coefficients, count == N * (degree+1)^2."""
        degree_attr = prim.GetAttribute(RADIANCE_DEGREE_ATTR)
        coeffs_attr = prim.GetAttribute(RADIANCE_COEFFS_ATTR)
        has_degree = bool(degree_attr) and degree_attr.HasAuthoredValue()
        has_coeffs = bool(coeffs_attr) and coeffs_attr.HasAuthoredValue()

        if not has_degree or not has_coeffs:
            missing = []
            if not has_degree:
                missing.append(f"'{RADIANCE_DEGREE_ATTR}'")
            if not has_coeffs:
                missing.append(f"'{RADIANCE_COEFFS_ATTR}'")
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_006,
                message=self._not_authored(prim, " and ".join(missing)),
                at=prim,
            )
            return

        degree = degree_attr.Get()
        # The SH degree must be in the supported range 0-3.
        if degree is None or degree < 0 or degree > 3:
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_006,
                message=(
                    f"3DGS prim <{prim.GetPath()}> '{RADIANCE_DEGREE_ATTR}' is "
                    f"{degree}; the spherical-harmonics degree must be 0-3."
                ),
                at=prim,
            )
            return

        if not num_gaussians:
            return
        coeffs = coeffs_attr.Get()
        coeff_count = len(coeffs) if coeffs is not None else 0
        expected = num_gaussians * (degree + 1) ** 2
        if coeff_count != expected:
            self._AddFailedCheck(
                requirement=cap.GaussianSplatRequirements.SPL_006,
                message=(
                    f"3DGS prim <{prim.GetPath()}> "
                    f"'{RADIANCE_COEFFS_ATTR}' has {coeff_count} entries "
                    f"but expected len(positions) * (degree + 1)^2 = "
                    f"{num_gaussians} * ({degree} + 1)^2 = {expected}."
                ),
                at=prim,
            )
