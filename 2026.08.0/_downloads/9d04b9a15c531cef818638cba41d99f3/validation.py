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
import math
from collections import defaultdict

import simready.foundation.tier_core.requirements as cap
import usd_validation_nvidia
from pxr import Gf, Usd, UsdGeom

# Tolerance for transformation comparisons
# Used for checking if transforms are close to identity values
TRANSFORM_TOLERANCE = 1e-4  # 0.0001

# Quantization scale for mesh point comparisons
MESH_POINT_PRECISION = 6


def _quantize_matrix(matrix: Gf.Matrix4d, tolerance: float = TRANSFORM_TOLERANCE) -> tuple[float, ...]:
    """Return a tolerance-quantized matrix suitable for grouping transforms."""
    return tuple(round(float(matrix[i][j]) / tolerance) * tolerance for i in range(4) for j in range(4))


def _mesh_has_static_topology(mesh: UsdGeom.Mesh) -> bool:
    """Return True when mesh points and topology are not time-varying."""
    points_attr = mesh.GetPointsAttr()
    indices_attr = mesh.GetFaceVertexIndicesAttr()
    counts_attr = mesh.GetFaceVertexCountsAttr()
    return not any(attr.ValueMightBeTimeVarying() for attr in (points_attr, indices_attr, counts_attr))


def _mesh_geometry_signature(mesh: UsdGeom.Mesh) -> tuple | None:
    """Return a hashable signature for static local mesh geometry, or None if unsupported."""
    if not _mesh_has_static_topology(mesh):
        return None

    points = mesh.GetPointsAttr().Get(Usd.TimeCode.EarliestTime())
    indices = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.EarliestTime())
    counts = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.EarliestTime())
    if not all((points, indices, counts)):
        return None

    point_sig = tuple(tuple(round(float(component), MESH_POINT_PRECISION) for component in point) for point in points)
    return (point_sig, tuple(int(count) for count in counts), tuple(int(index) for index in indices))


def _mesh_world_transform_signature(prim: Usd.Prim) -> tuple[float, ...] | None:
    """Return a hashable composed world transform signature for a mesh prim."""
    if not prim.IsA(UsdGeom.Xformable):
        return None
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    return _quantize_matrix(matrix)


def _is_visible_mesh(prim: Usd.Prim) -> bool:
    """Return True when the mesh prim is not explicitly invisible."""
    imageable = UsdGeom.Imageable(prim)
    if not imageable:
        return True
    return imageable.ComputeVisibility(Usd.TimeCode.Default()) != UsdGeom.Tokens.invisible


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_001, override=True)
class ImageableGeometryChecker(usd_validation_nvidia.BaseRuleChecker):
    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            self._AddFailedCheck("Stage has no default prim. Unable to validate.", at=stage)
            print("Stage has no default prim. Unable to validate.")
            return
        for prim in Usd.PrimRange(default_prim):
            if UsdGeom.Imageable(prim):
                return
        self._AddFailedCheck(
            requirement=cap.GeometryRequirements.VG_001,
            message="No imageable geometry prims found under the default prim.",
            at=stage,
        )


# @usd_validation_nvidia.register_rule("Geometry")
# @usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_012, override=True)
# class UsdGeomMeshSmallChecker(usd_validation_nvidia.BaseRuleChecker):
#     mesh_extent_threshold = 0.002
#     SMALL_USDMESH_REQUIREMENT = cap.GeometryRequirements.VG_012

#     def CheckStage(self, stage: Usd.Stage) -> None:
#         default_prim = stage.GetDefaultPrim()
#         if not default_prim:
#             self._AddFailedCheck(
#                 "Stage has no default prim. Unable to validate.", at=stage)
#             return

#         mesh_prim_list = [prim for prim in Usd.PrimRange(
#             default_prim) if prim.IsA(UsdGeom.Mesh)]
#         if len(mesh_prim_list) <= 1:
#             return

#         small_prim_count = 0
#         for mesh_prim in mesh_prim_list:
#             # compute mesh extent range
#             mesh = UsdGeom.Mesh(mesh_prim)
#             extent = mesh.GetExtentAttr().Get()
#             if not extent:
#                 self._AddFailedCheck(
#                     "Mesh prim has no extent. Unable to validate.", at=mesh_prim, requirement=self.SMALL_USDMESH_REQUIREMENT)
#             extent_range = extent[1] - extent[0]
#             if all(dimensional_range < self.mesh_extent_threshold for dimensional_range in extent_range):
#                 small_prim_count += 1

#         if small_prim_count > 1:
#             self._AddFailedCheck(
#                 "More than one small UsdGeomMesh found.", at=stage, requirement=self.SMALL_USDMESH_REQUIREMENT)


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_023, override=True)
class MeshXformPositioningChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates that meshes use xform ops instead of baked transformations"""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdGeom.Mesh):
            return

        mesh = UsdGeom.Mesh(prim)
        points_attr = mesh.GetPointsAttr()

        if not points_attr or not points_attr.HasValue():
            return

        points = points_attr.Get()
        if not points:
            return

        # Check if points appear to be offset from origin
        # This is a heuristic - checking if center of bounding box is far from origin
        min_point = [float("inf")] * 3
        max_point = [float("-inf")] * 3

        for point in points:
            for i in range(3):
                min_point[i] = min(min_point[i], point[i])
                max_point[i] = max(max_point[i], point[i])

        center = [(min_point[i] + max_point[i]) / 2 for i in range(3)]
        distance_from_origin = sum(c * c for c in center) ** 0.5

        # If center is more than 10 units from origin, likely has baked transform
        if distance_from_origin > 10.0:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_023,
                message=f"Mesh '{prim.GetPath()}' appears to have baked transformations (center is {distance_from_origin:.2f} units from origin).",
                at=prim,
            )


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_025, override=True)
class AssetOriginPositioningChecker(usd_validation_nvidia.BaseRuleChecker):
    """
    Validates that assets are positioned at origin.

    Asset transforms shall be defined such that the asset is correctly positioned and oriented
    at the origin (0,0,0) with no rotation and unit scale in its local space before any
    instance-specific transformations are applied in an aggregate scene.

    This ensures:
    - Predictable asset placement in scenes
    - Simplified instancing workflows
    - Consistent behavior across different applications
    - Easier debugging of transformation issues
    - Reduced floating-point precision errors when instancing far from origin

    The validator checks the default prim's local transformation matrix against identity,
    reporting specific issues for translation, rotation, and scale deviations.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        # Skip if prim is an instance or in a prototype
        if default_prim.IsInstance() or default_prim.IsInPrototype():
            return

        # Check if default prim has non-identity transform
        if default_prim.IsA(UsdGeom.Xformable):
            xformable = UsdGeom.Xformable(default_prim)

            # Get the composed local transformation matrix
            local_transform = xformable.GetLocalTransformation()

            # Check if the matrix is close to identity
            identity = Gf.Matrix4d(1.0)
            if not Gf.IsClose(local_transform, identity, TRANSFORM_TOLERANCE):
                # Decompose the matrix to provide specific error messages

                # Extract translation
                translation = local_transform.ExtractTranslation()
                if translation.GetLength() > TRANSFORM_TOLERANCE:
                    self._AddFailedCheck(
                        requirement=cap.GeometryRequirements.VG_025,
                        message=f"Asset root prim has non-zero translation: ({translation[0]:.4f}, {translation[1]:.4f}, {translation[2]:.4f}). "
                        f"This may cause issues with instancing, asset reuse, and floating-point precision when placed far from scene origin.",
                        at=default_prim,
                    )

                # Extract rotation
                rotation = local_transform.ExtractRotation()
                angle = rotation.GetAngle()
                if abs(angle) > TRANSFORM_TOLERANCE:  # angle is in radians
                    angle_degrees = math.degrees(angle)
                    axis = rotation.GetAxis()
                    self._AddFailedCheck(
                        requirement=cap.GeometryRequirements.VG_025,
                        message=f"Asset root prim has non-zero rotation: {angle_degrees:.2f} degrees around axis ({axis[0]:.3f}, {axis[1]:.3f}, {axis[2]:.3f}). "
                        f"Pre-rotated assets complicate instancing workflows and may not align with expected orientations in different contexts.",
                        at=default_prim,
                    )

                # Check scale - extract scale values from the matrix
                # Note: This assumes no shear in the transformation
                scale_x = local_transform.GetRow(0).GetLength()
                scale_y = local_transform.GetRow(1).GetLength()
                scale_z = local_transform.GetRow(2).GetLength()

                if any(abs(s - 1.0) > TRANSFORM_TOLERANCE for s in [scale_x, scale_y, scale_z]):
                    self._AddFailedCheck(
                        requirement=cap.GeometryRequirements.VG_025,
                        message=f"Asset root prim has non-unit scale: ({scale_x:.4f}, {scale_y:.4f}, {scale_z:.4f}). "
                        f"Pre-scaled assets can cause confusion about the asset's true size and may lead to compounding scale issues when instanced.",
                        at=default_prim,
                    )


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_026, override=True)
class AssetPivotPlacementChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validates appropriate pivot placement for assets"""

    def CheckStage(self, stage: Usd.Stage) -> None:
        default_prim = stage.GetDefaultPrim()
        if not default_prim:
            return

        # Collect all mesh bounds
        all_points = []
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                points_attr = mesh.GetPointsAttr()
                if points_attr and points_attr.HasValue():
                    # Transform points to world space
                    points = points_attr.Get()
                    xform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    for point in points:
                        world_point = xform.Transform(point)
                        all_points.append(world_point)

        if not all_points:
            return

        # Calculate bounding box
        min_point = [float("inf")] * 3
        max_point = [float("-inf")] * 3

        for point in all_points:
            for i in range(3):
                min_point[i] = min(min_point[i], point[i])
                max_point[i] = max(max_point[i], point[i])

        # Check if pivot (origin) is at the bottom center of the bounding box
        # This is a common convention for many asset types
        expected_pivot_x = (min_point[0] + max_point[0]) / 2
        expected_pivot_y = (min_point[1] + max_point[1]) / 2
        expected_pivot_z = min_point[2]  # Bottom of bounding box

        # Allow some tolerance
        tolerance = 0.1
        if abs(expected_pivot_x) > tolerance or abs(expected_pivot_y) > tolerance or abs(expected_pivot_z) > tolerance:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_026,
                message=f"Asset pivot appears to be offset from expected position (bottom-center of bounds). "
                f"Expected pivot near ({expected_pivot_x:.2f}, {expected_pivot_y:.2f}, {expected_pivot_z:.2f})",
                at=default_prim,
            )


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_008, override=True)
class CoincidentMeshChecker(usd_validation_nvidia.BaseRuleChecker):
    """
    Detect visible meshes with identical local geometry occupying the same composed
    world transform. This catches accidental duplicate meshes left in place after
    failed move/reference operations.
    """

    def CheckStage(self, stage: Usd.Stage) -> None:
        coincident_groups: dict[tuple, list[Usd.Prim]] = defaultdict(list)

        # Descend into instance proxies so duplicate meshes hidden inside
        # instanced references (common for SimReady payload layouts) are
        # still grouped against their non-instanced siblings.
        for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            if not _is_visible_mesh(prim):
                continue

            mesh = UsdGeom.Mesh(prim)
            geometry_signature = _mesh_geometry_signature(mesh)
            if geometry_signature is None:
                continue

            transform_signature = _mesh_world_transform_signature(prim)
            if transform_signature is None:
                continue

            coincident_groups[(geometry_signature, transform_signature)].append(prim)

        for prims in coincident_groups.values():
            if len(prims) < 2:
                continue

            paths = ", ".join(str(prim.GetPath()) for prim in prims)
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_008,
                message=(
                    f"Found {len(prims)} coincident meshes with identical geometry at the same transform: {paths}"
                ),
                at=prims[0],
            )


@usd_validation_nvidia.register_rule("Geometry")
@usd_validation_nvidia.register_requirements(cap.GeometryRequirements.VG_MESH_001, override=True)
class GeomShallBeMeshChecker(usd_validation_nvidia.BaseRuleChecker):
    """
    Validates that the stage contains at least one mesh.
    Warns if other geometry is also present.

    Implements VG_MESH_001
    """

    _MESH_NOT_FOUND_MESSAGE = "Stage does not contain any meshes."
    _OTHER_GEOMETRY_WARNING_MESSAGE = "Stage contains a mesh as required, but also other types of Gprims."

    def CheckStage(self, stage: Usd.Stage) -> None:

        def find_geometry_prims(stage: Usd.Stage) -> tuple[Usd.Prim | None, Usd.Prim | None]:
            """
            Traverses a USD stage to find at least one Mesh prim and one other
            type of geometry prim.

            Args:
                stage: The USD stage to traverse.

            Returns:
                A tuple containing the first found Mesh prim and the first found
                other geometry prim. Either can be None if not found.
            """
            mesh_prim = None
            other_geom_prim = None

            # Traverse all prims on the stage
            for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
                # If we haven't found a mesh yet, check if this prim is a mesh
                if not mesh_prim and prim.IsA(UsdGeom.Mesh):
                    mesh_prim = prim
                    continue  # Move to the next prim

                # If we haven't found other geometry yet, check if it's a Gprim
                # but specifically NOT a Mesh.
                if not other_geom_prim and prim.IsA(UsdGeom.Gprim) and not prim.IsA(UsdGeom.Mesh):
                    other_geom_prim = prim

                # Optimization: If we've found both, we can stop traversing
                if mesh_prim and other_geom_prim:
                    break

            return mesh_prim, other_geom_prim

        mesh_prim, other_geom_prim = find_geometry_prims(stage)

        if not mesh_prim:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_MESH_001, message=self._MESH_NOT_FOUND_MESSAGE, at=stage
            )
        elif mesh_prim and other_geom_prim:
            self._AddWarning(
                requirement=cap.GeometryRequirements.VG_MESH_001,
                message=self._OTHER_GEOMETRY_WARNING_MESSAGE,
                at=other_geom_prim,
            )
