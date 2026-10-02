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
Validation rules for the Display Color capability.
"""

import math

import simready.foundation.tier_core.requirements as cap
from pxr import Sdf, Usd, UsdGeom
from usd_validation_nvidia import BaseRuleChecker, register_requirements

DISPLAY_COLOR = "displayColor"
DISPLAY_OPACITY = "displayOpacity"

# The types UsdGeomGprim declares for the two display primvars.
DISPLAY_COLOR_TYPE = Sdf.ValueTypeNames.Color3fArray
DISPLAY_OPACITY_TYPE = Sdf.ValueTypeNames.FloatArray


@register_requirements(
    cap.DisplayColorRequirements.DISP_001,
    cap.DisplayColorRequirements.DISP_002,
    cap.DisplayColorRequirements.DISP_003,
)
class DisplayColorCapabilityChecker(BaseRuleChecker):
    """
    Validates the following display color requirements:

    - **DISP.001**: a renderable GPrim resolves a display color, authored or inherited
    - **DISP.002**: display color resolves to the array UsdGeomGprim declares, its components
      are finite and within [0, 1], and the element count agrees with the declared
      interpolation
    - **DISP.003**: display opacity, where authored, meets the same terms
    """

    def CheckPrim(self, prim) -> None:
        if not UsdGeom.Gprim(prim):
            return
        if not self._has_default_or_renderable_purpose(prim):
            return

        self._check_disp_001_display_color_resolves(prim)
        self._check_disp_002_display_color_values(prim)
        self._check_disp_003_display_opacity_values(prim)

    # ------------------------------------------------------------------
    # DISP.001
    # ------------------------------------------------------------------
    def _check_disp_001_display_color_resolves(self, prim) -> None:
        """A renderable GPrim must resolve a display color, on itself or an ancestor."""
        primvar = self._find_with_inheritance(prim, DISPLAY_COLOR)
        if primvar is None:
            self._AddFailedCheck(
                message=(
                    f"GPrim '{prim.GetPath()}' does not resolve a 'primvars:{DISPLAY_COLOR}', "
                    "authored on the prim or inherited from an ancestor"
                ),
                at=prim,
                requirement=cap.DisplayColorRequirements.DISP_001,
            )

    # ------------------------------------------------------------------
    # DISP.002
    # ------------------------------------------------------------------
    def _check_disp_002_display_color_values(self, prim) -> None:
        primvar = self._find_with_inheritance(prim, DISPLAY_COLOR)
        if primvar is None:
            return

        report = self._reporter(prim, cap.DisplayColorRequirements.DISP_002)
        authored_on = self._authoring_path(primvar)
        for time in self._resolution_times(primvar):
            values = primvar.Get(time)
            if values is None:
                # Resolving to nothing here: a blocked value, for example. Nothing to count
                # or range-check at this time code.
                continue
            if not self._check_value_type(report, time, primvar, values, DISPLAY_COLOR_TYPE):
                continue

            for index, color in enumerate(values):
                components = self._as_components(color)
                if components is None:
                    report(
                        time,
                        f"'primvars:{DISPLAY_COLOR}' element {index} on '{authored_on}' is not a "
                        "three-component colour",
                    )
                    continue
                for channel, component in zip("rgb", components):
                    if not self._is_finite(component):
                        report(
                            time,
                            f"'primvars:{DISPLAY_COLOR}' element {index} has a non-finite "
                            f"{channel} component on '{authored_on}'",
                        )
                    elif not 0.0 <= component <= 1.0:
                        report(
                            time,
                            f"'primvars:{DISPLAY_COLOR}' element {index} has {channel}={component} "
                            f"outside [0, 1] on '{authored_on}'",
                        )

            self._check_element_count(report, prim, primvar, len(values), time)

    # ------------------------------------------------------------------
    # DISP.003
    # ------------------------------------------------------------------
    def _check_disp_003_display_opacity_values(self, prim) -> None:
        """Display opacity is optional; it is only checked when authored."""
        primvar = self._find_with_inheritance(prim, DISPLAY_OPACITY)
        if primvar is None:
            return

        report = self._reporter(prim, cap.DisplayColorRequirements.DISP_003)
        authored_on = self._authoring_path(primvar)
        for time in self._resolution_times(primvar):
            values = primvar.Get(time)
            if values is None:
                # See DISP.002: authored, but resolving to nothing at this time code.
                continue
            if not self._check_value_type(report, time, primvar, values, DISPLAY_OPACITY_TYPE):
                continue

            for index, opacity in enumerate(values):
                value = self._as_scalar(opacity)
                if value is None:
                    report(
                        time,
                        f"'primvars:{DISPLAY_OPACITY}' element {index} on '{authored_on}' is not "
                        "a single float",
                    )
                elif not math.isfinite(value):
                    report(
                        time,
                        f"'primvars:{DISPLAY_OPACITY}' element {index} is non-finite "
                        f"on '{authored_on}'",
                    )
                elif not 0.0 <= value <= 1.0:
                    report(
                        time,
                        f"'primvars:{DISPLAY_OPACITY}' element {index} is {value}, outside [0, 1] "
                        f"on '{authored_on}'",
                    )

            self._check_element_count(report, prim, primvar, len(values), time)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_with_inheritance(self, prim, name):
        """Return the primvar carrying an authored value for ``prim``, or None.

        ``UsdGeomPrimvarsAPI`` inherits constant-interpolation primvars down namespace, so a
        value authored on an ancestor satisfies the requirement for the geometry beneath it.
        ``displayColor`` and ``displayOpacity`` are declared by the ``UsdGeomGprim`` schema, so
        a primvar object exists whether or not a value was authored; the authored check is what
        distinguishes the two.
        """
        primvar = UsdGeom.PrimvarsAPI(prim).FindPrimvarWithInheritance(name)
        if not primvar:
            return None
        if not primvar.GetAttr().HasAuthoredValue():
            return None
        return primvar

    def _reporter(self, prim, requirement):
        """Return a ``report(time, message)`` that fires once per distinct message.

        The value rules run over every time code the primvar resolves at, and a primvar that
        is out of range is usually out of range at all of them. Reporting each repeat would
        bury everything else the validator has to say, so the first occurrence is reported,
        named with the time it was found at, and the repeats are dropped.

        The default time code is left unnamed, which keeps the message a static asset
        produces the same as it was before animation was checked at all.
        """
        seen = set()

        def report(time, message) -> None:
            if message in seen:
                return
            seen.add(message)
            if not time.IsDefault():
                message = f"{message}, at time {time.GetValue():g}"
            self._AddFailedCheck(message=message, at=prim, requirement=requirement)

        return report

    def _check_value_type(self, report, time, primvar, values, declared) -> bool:
        """Report a display primvar that does not resolve to the declared array, return False.

        ``UsdGeomGprim`` declares ``displayColor`` as ``color3f[]`` and ``displayOpacity`` as
        ``float[]``. What is compared is the resolved value against the array that declared
        type produces, so the answer does not depend on where the primvar was authored. It
        used to: the previous form compared the value against the array class of the
        *attribute's* type name, which a GPrim takes from the schema and an ancestor takes
        from the author, so the same mis-authored value failed on a GPrim and passed on the
        ``Xform`` above it.

        Two ways to miss the declared type, and USD reports neither. A scalar: nothing
        constrains the type on a prim that is not a GPrim, so a scalar authored on an
        enclosing ``Xform`` loads and ``FindPrimvarWithInheritance`` hands it to every GPrim
        beneath; a scalar authored on the GPrim itself is not coerced either, and the
        attribute keeps the schema's type name while resolving to a single value. A precision
        variant: ``color3d[]`` and ``half3[]``, or ``double[]`` and ``half[]`` for opacity,
        load as authored on an ancestor, and on a GPrim the schema pins the type name to the
        declared one while the value keeps the precision it was authored with. Either way
        ``Get`` hands a consumer an array it did not ask for.

        ``float3[]`` on an ancestor does pass, because it resolves to the same
        ``VtVec3fArray`` as ``color3f[]``; only the Sdf role differs, and a consumer reading
        the declared type gets its value. The role is worth authoring for colour management,
        but its absence costs the consumer nothing this requirement can measure.
        """
        expected = declared.arrayType.type.pythonClass
        if isinstance(values, expected):
            return True
        report(
            time,
            f"'{primvar.GetName()}' on '{self._authoring_path(primvar)}' resolves to "
            f"'{type(values).__name__}'; UsdGeomGprim declares it as '{declared}'",
        )
        return False

    def _check_element_count(self, report, prim, primvar, count, time) -> None:
        """Compare the authored count against the declared interpolation.

        Only the cases that can be determined without ambiguity are checked. ``constant``
        applies to every GPrim, and ``vertex`` is one element per point on any
        ``UsdGeomPointBased``. ``uniform``, ``varying`` and ``faceVarying`` are checked on
        meshes only: on ``BasisCurves`` they count curves and segment endpoints, which follow
        from the curve type, basis and wrap, so reading them as a mesh would report conforming
        curves as failures.

        An indexed primvar carries one index per element, so the index array is what topology
        is compared against. Its value array may legitimately be any length, and is only
        required to cover every index.

        ``time`` is the time code the values were resolved at, and everything read here is
        read at the same one. The index array and the prim's topology each carry their own
        samples, and reading them at the default time code while the values came from a
        sample compares arrays that never coexist.
        """
        interpolation = primvar.GetInterpolation()
        authored_on = self._authoring_path(primvar)
        unit = "elements"

        # The indices attribute rather than ``GetIndices()``, which flattens "no indices
        # resolve here" and "an empty index array is authored here" into the same empty
        # array. A primvar whose indices are sampled resolves as unindexed at a time code
        # they do not cover, and there is no index count to compare against there.
        indices = primvar.GetIndicesAttr().Get(time)
        if indices is not None:
            if any(index < 0 or index >= count for index in indices):
                report(
                    time,
                    f"'{primvar.GetName()}' on '{authored_on}' indexes outside its "
                    f"{count}-element value array",
                )
            count = len(indices)
            unit = "indices"

        if interpolation == UsdGeom.Tokens.constant:
            if count != 1:
                report(
                    time,
                    f"'{primvar.GetName()}' on '{authored_on}' declares constant "
                    f"interpolation but authors {count} {unit}, expected 1",
                )
            return

        expected = self._expected_count(prim, interpolation, time)
        if expected is not None and count != expected:
            report(
                time,
                f"'{primvar.GetName()}' on '{authored_on}' declares {interpolation} "
                f"interpolation and authors {count} {unit}, expected {expected}",
            )

    @staticmethod
    def _expected_count(prim, interpolation, time):
        """The count the prim's topology implies, or None where it cannot be determined.

        Topology is read at ``time``, the time code the primvar's values resolved at, so a
        deforming mesh is compared against the points it carries alongside those values.
        """
        if interpolation == UsdGeom.Tokens.vertex:
            point_based = UsdGeom.PointBased(prim)
            if not point_based:
                return None
            points = point_based.GetPointsAttr().Get(time)
            return len(points) if points else None

        mesh = UsdGeom.Mesh(prim)
        if not mesh:
            return None
        if interpolation == UsdGeom.Tokens.uniform:
            face_counts = mesh.GetFaceVertexCountsAttr().Get(time)
            return len(face_counts) if face_counts else None
        if interpolation == UsdGeom.Tokens.varying:
            points = mesh.GetPointsAttr().Get(time)
            return len(points) if points else None
        if interpolation == UsdGeom.Tokens.faceVarying:
            face_indices = mesh.GetFaceVertexIndicesAttr().Get(time)
            return len(face_indices) if face_indices else None
        return None

    @staticmethod
    def _resolution_times(primvar):
        """Every time code the primvar resolves a value at, earliest first.

        A static primvar resolves once, at the default time code, and that is what a consumer
        of a static asset reads. A primvar carrying time samples resolves at each of them,
        and DISP.002 and DISP.003 hold for every value it takes, so each sample is checked.
        Checking one and stopping would leave range, finiteness and element count unexamined
        from the second sample on, which an override layer can reach by adding samples to a
        primvar that conforms at the first.

        A primvar can also carry only time samples and no default, in which case nothing
        resolves at the default time code. DISP.001 counts such a primvar as authored on the
        strength of ``HasAuthoredValue``, so the samples are the only chance the value rules
        get to see it.

        The index array carries its own samples, and a static value array can be read through
        an animated index array, so the two sets are merged. ``GetIndicesAttr`` is invalid on
        an unindexed primvar and reports no samples, which is the answer wanted there.
        """
        attr = primvar.GetAttr()
        times = set(attr.GetTimeSamples())
        times.update(primvar.GetIndicesAttr().GetTimeSamples())
        resolution_times = [Usd.TimeCode(time) for time in sorted(times)]
        if attr.Get(Usd.TimeCode.Default()) is not None:
            resolution_times.insert(0, Usd.TimeCode.Default())
        return resolution_times

    @staticmethod
    def _authoring_path(primvar):
        """The prim the value is authored on, which is not always the prim being checked."""
        return primvar.GetAttr().GetPrim().GetPath()

    @staticmethod
    def _as_components(color):
        """Return the three components of a colour element, or None if it is not one."""
        try:
            components = tuple(color)
        except TypeError:
            return None
        return components if len(components) == 3 else None

    @staticmethod
    def _as_scalar(value):
        """Return a float for a scalar element, or None if it is not one."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _has_default_or_renderable_purpose(self, prim) -> bool:
        """Returns True if the prim is Imageable with default or renderable purpose."""
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            return False
        purpose = imageable.ComputePurpose()
        return purpose in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)

    @staticmethod
    def _is_finite(value) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False
