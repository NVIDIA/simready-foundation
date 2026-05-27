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
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field

import omni.asset_validator
import omni.capabilities as cap
from pxr import Gf, Usd, UsdGeom, Vt

# Tolerance for transformation comparisons
# Used for checking if transforms are close to identity values
TRANSFORM_TOLERANCE = 1e-4  # 0.0001


# Helper classes for graph operations
@dataclass(slots=True)
class DisjointSet:
    """
    Disjoint-set (union-find) data structure for tracking connected components.
    Used for detecting non-manifold vertices in mesh topology.
    """

    _parent: dict[int, int] = field(default_factory=dict, init=False)
    _rank: dict[int, int] = field(default_factory=dict, init=False)
    _count: int = 0

    def make_set(self, x: int) -> None:
        """Create a new set containing element x."""
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
            self._count += 1

    def find(self, x: int) -> int:
        """Find the representative (root) of the set containing x."""
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]  # Path compression
            x = self._parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        """Merge the sets containing x and y."""
        x = self.find(x)
        y = self.find(y)
        if x == y:
            return
        # Union by rank
        if self._rank[x] < self._rank[y]:
            x, y = y, x
        self._parent[y] = x
        if self._rank[x] == self._rank[y]:
            self._rank[x] += 1
        self._count -= 1

    @property
    def connected(self) -> bool:
        """Check if all elements in this set are connected."""
        return self._count == 1


def _get_normals_source(mesh: UsdGeom.Mesh, time: Usd.TimeCode = None):
    """Return a tuple describing the effective normals source:

    interp: interpolation token string
    values: sequence of GfVec3f
    count_for_topology_check: integer (values count or indices count)
    value_attr_or_primvar: the UsdAttribute/UsdGeomPrimvar object (for time checks)
    is_indexed: if the primvar was indexed
    indices: the indices for the primvar
    """

    if time is None:
        time = Usd.TimeCode.EarliestTime()

    prim = mesh.GetPrim()
    pvars = UsdGeom.PrimvarsAPI(prim)
    pv = pvars.GetPrimvar("normals")
    if pv and pv.HasValue():
        interp = pv.GetInterpolation()
        values = pv.Get(time) or []
        # If indexed, the count applies to the indices array, not the values array.
        idx = []
        if pv.IsIndexed():
            idx = pv.GetIndices(time) or []
            topo_count = len(idx)
        else:
            topo_count = len(values)
        return (interp, values, topo_count, pv, pv.IsIndexed(), idx)

    # Fallback to the built-in attribute
    attr = mesh.GetNormalsAttr()
    if attr and attr.HasValue():
        values = attr.Get(time) or []
        interp = mesh.GetNormalsInterpolation()
        return (interp, values, len(values), attr, False, [])

    return None


# Helper functions for mesh validation
def vector_area(coords: list[Gf.Vec3f]):
    """Compute the vector area of a polygon defined by coordinates."""
    va = Gf.Vec3f(0, 0, 0)
    n = len(coords)
    x0: Gf.Vec3f = coords[0]
    x_prev: Gf.Vec3f = coords[1] - x0
    for i in range(2, n):
        x: Gf.Vec3f = coords[i] - x0
        va += Gf.Cross(x_prev, x)
        x_prev = x
    return va / 2


def compute_winding_bias(
    mesh: UsdGeom.Mesh, interp: str, normals: list[Gf.Vec3f], normals_indexed: bool, normals_indices: list[int]
) -> float:
    """
    Compute winding bias by checking normal-face alignment.

    Returns positive value if normals mostly agree with CCW winding,
    negative if they mostly agree with CW winding.
    """
    points: Vt.Vec3fArray = mesh.GetPointsAttr().Get(Usd.TimeCode.EarliestTime())
    face_sizes: Vt.IntArray = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.EarliestTime())
    indices: Vt.IntArray = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.EarliestTime())

    cursor = 0
    winding_bias = 0.0

    for face_index, nverts in enumerate(face_sizes):
        if nverts < 3:
            cursor += nverts
            continue  # degenerate

        face_coords = [points[i] for i in indices[cursor : cursor + nverts]]
        va = vector_area(face_coords)

        if interp == UsdGeom.Tokens.uniform:  # per face
            if normals_indexed:
                winding_bias += Gf.Dot(va, normals[normals_indices[face_index]])
            else:
                winding_bias += Gf.Dot(va, normals[face_index])
        elif interp == UsdGeom.Tokens.faceVarying:  # per corner
            for i in range(nverts):
                corner_idx = cursor + i
                if normals_indexed:
                    winding_bias += Gf.Dot(va, normals[normals_indices[corner_idx]])
                else:
                    winding_bias += Gf.Dot(va, normals[corner_idx])
        elif interp in (UsdGeom.Tokens.vertex, UsdGeom.Tokens.varying):  # per vertex
            for i in range(nverts):
                vertex_idx = indices[cursor + i]
                if normals_indexed:
                    winding_bias += Gf.Dot(va, normals[normals_indices[vertex_idx]])
                else:
                    winding_bias += Gf.Dot(va, normals[vertex_idx])
        else:
            pass

        cursor += nverts

    return winding_bias


def check_manifold_elements(num_vertices: int, indices: Vt.IntArray, face_sizes: Vt.IntArray) -> tuple[int, int, bool]:
    """
    Construct all the edges in geometry and finds if we have:
    - Non-manifold vertices: Two or more faces share a vertex but no edge and/or no faces between them.
    - Non-manifold edges: More than 2 faces share an edge.
    - Inconsistent winding: Adjacent faces have opposite winding.

    Args:
        num_vertices: The number of total vertices.
        indices: An array of all indices.
        face_sizes: An array of all face sizes.

    Returns:
        A tuple containing:
        - The number of non-manifold vertices.
        - The number of non-manifold edges.
        - Whether the winding is consistent.
    """
    # Create a mapping for the edges
    num_edges: int = len(indices)
    edges: list[tuple[int, int, int]] = [(0, 0, 0)] * num_edges

    # Collect all edges.
    current_index: int = 0
    for face_index, face_size in enumerate(face_sizes):
        for i in range(face_size):
            p: int = indices[current_index + i]
            q: int = indices[current_index + (i + 1) % face_size]
            edges[current_index + i] = (p, q, face_index)
        current_index += face_size

    # Create a dict of edges.
    edge_to_winding: dict[tuple[int, int], list[bool]] = defaultdict(list)
    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for p, q, face_index in edges:
        key: tuple[int, int] = (min(p, q), max(p, q))
        edge_to_winding[key].append(p < q)
        edge_to_faces[key].append(face_index)

    # Non-manifold edges: Three or more faces share an edge.
    num_nonmanifold_edges: int = 0
    for faces in edge_to_faces.values():
        if len(faces) > 2:
            num_nonmanifold_edges += 1

    # Winding consistency: Adjacent faces have opposite winding.
    winding_consistent: bool = True
    for winding in edge_to_winding.values():
        if len(winding) == 2 and winding[0] == winding[1]:
            winding_consistent = False

    # Non-manifold vertices: Two or more faces share a vertex but no edge and/or no faces between them.
    vertex_to_faces = [DisjointSet() for _ in range(num_vertices)]
    current_index: int = 0
    for face_index, face_size in enumerate(face_sizes):
        for i in range(face_size):
            p: int = indices[current_index + i]
            vertex_to_faces[p].make_set(face_index)
        current_index += face_size
    for (p, q), faces in edge_to_faces.items():
        if len(faces) == 2:
            vertex_to_faces[p].union(faces[0], faces[1])
            vertex_to_faces[q].union(faces[0], faces[1])
    num_nonmanifold_vertices = sum(1 for disjoint_set in vertex_to_faces if not disjoint_set.connected)

    return num_nonmanifold_vertices, num_nonmanifold_edges, winding_consistent


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_001, override=True)
class ImageableGeometryChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_002, override=True)
class UsdGeomExtentChecker(omni.asset_validator.BaseRuleChecker):
    """Validates that boundable geometry has valid extent values"""

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdGeom.Boundable):
            return

        boundable = UsdGeom.Boundable(prim)
        extent_attr = boundable.GetExtentAttr()

        if not extent_attr or not extent_attr.HasValue():
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_002,
                message=f"Boundable prim '{prim.GetPath()}' has no extent attribute.",
                at=prim,
            )
            return

        # Check for time-varying geometry
        if extent_attr.GetNumTimeSamples() > 0:
            # For time-varying, extent should be authored at each time sample
            points_attr = prim.GetAttribute("points")
            if points_attr and points_attr.GetNumTimeSamples() > 0:
                if extent_attr.GetNumTimeSamples() != points_attr.GetNumTimeSamples():
                    self._AddFailedCheck(
                        requirement=cap.GeometryRequirements.VG_002,
                        message=f"Time-varying geometry at '{prim.GetPath()}' has mismatched extent time samples.",
                        at=prim,
                    )


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_007, override=True)
class ManifoldChecker(omni.asset_validator.BaseRuleChecker):
    """
    Counts the number of non-manifold edges and vertices. A non-manifold edge has more than two adjacent faces. A
    non-manifold vertex as more than two adjacent border edges, where a border edge is an edge with only one adjacent
    face.

    Works on non time varying geometry.
    """

    def _validate_mesh(self, mesh: UsdGeom.Mesh) -> None:
        points: Vt.Vec3fArray | None = mesh.GetPointsAttr().Get(Usd.TimeCode.EarliestTime())
        num_points: int = len(points) if points else 0
        indices: Vt.IntArray = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.EarliestTime())
        face_sizes: Vt.IntArray = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.EarliestTime())

        if all((indices, face_sizes, num_points)):
            valid, _ = UsdGeom.Mesh.ValidateTopology(indices, face_sizes, num_points)
        else:
            valid = False
        if not valid:
            # Validated in ValidationTopologyChecker
            return

        num_non_manifold_vertices, num_non_manifold_edges, winding_consistent = check_manifold_elements(
            num_points, indices, face_sizes
        )

        if num_non_manifold_vertices > 0:
            self._AddWarning(
                requirement=cap.GeometryRequirements.VG_007,
                message=f"{num_non_manifold_vertices} vertices are non-manifold.",
                at=mesh,
            )
        if num_non_manifold_edges > 0:
            self._AddWarning(
                requirement=cap.GeometryRequirements.VG_007,
                message=f"{num_non_manifold_edges} edges are non-manifold.",
                at=mesh,
            )
        if not winding_consistent:
            self._AddWarning(
                requirement=cap.GeometryRequirements.VG_007,
                message="The face winding is not consistent.",
                at=mesh,
            )

    def CheckPrim(self, prim: Usd.Prim) -> None:
        mesh: UsdGeom.Mesh = UsdGeom.Mesh(prim)
        if mesh:
            points_attr: Usd.Attribute = mesh.GetPointsAttr()
            has_static_points: bool = points_attr.IsAuthored() and not points_attr.ValueMightBeTimeVarying()
            if not has_static_points:
                return
            indices_attr: Usd.Attribute = mesh.GetFaceVertexIndicesAttr()
            has_static_indices: bool = indices_attr.IsAuthored() and not indices_attr.ValueMightBeTimeVarying()
            if not has_static_indices:
                return
            face_sizes_attr: Usd.Attribute = mesh.GetFaceVertexCountsAttr()
            has_static_faces: bool = face_sizes_attr.IsAuthored() and not face_sizes_attr.ValueMightBeTimeVarying()
            if not has_static_faces:
                return
            self._validate_mesh(mesh)


# @omni.asset_validator.register_rule("Geometry")
# @omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_012, override=True)
# class UsdGeomMeshSmallChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_023, override=True)
class MeshXformPositioningChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_025, override=True)
class AssetOriginPositioningChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_026, override=True)
class AssetPivotPlacementChecker(omni.asset_validator.BaseRuleChecker):
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_028, override=True)
class NormalsShouldBeCorrectChecker(omni.asset_validator.BaseRuleChecker):
    """
    Check that all normals have unit length, and that there are no non-finite values.
    Also checks that the supplied number of normal values agrees with the interpolation.
    Supports both normals attribute and primvar:normals.
    """

    UNIT_LENGTH_TOLERANCE = 1e-3

    @staticmethod
    def _is_finite_vec3(v: Gf.Vec3f):
        return all(math.isfinite(c) for c in v)

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdGeom.Mesh):
            return

        mesh = UsdGeom.Mesh(prim)

        # Subdivision rule: normals should not be authored on subdiv meshes.
        scheme = mesh.GetSubdivisionSchemeAttr().Get() or UsdGeom.Tokens.catmullClark
        src = _get_normals_source(mesh, Usd.TimeCode.EarliestTime())

        if scheme != UsdGeom.Tokens.none and src is not None:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_028,
                message=f"Mesh '{prim.GetPath()}' is subdiv ('{scheme}') but has authored normals; USD recommends not authoring normals on subdiv meshes.",
                at=prim,
            )
            # Continue checking anyway; downstream tools may still consume them.

        # If no normals at all, nothing to validate (often OK → faceted polys).
        if src is None:
            return

        interp, normals, topo_count, _, _, _ = src

        # Accept the standard interpolation tokens. (normals commonly use 'varying' or 'vertex')
        valid_interps = {
            UsdGeom.Tokens.vertex,
            UsdGeom.Tokens.varying,
            UsdGeom.Tokens.uniform,
            UsdGeom.Tokens.faceVarying,
            UsdGeom.Tokens.constant,
        }
        if interp not in valid_interps:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_028,
                message=f"Mesh '{prim.GetPath()}' has invalid normals interpolation: '{interp}'.",
                at=prim,
            )
            return

        # Expected element count by interpolation
        face_counts = mesh.GetFaceVertexCountsAttr().Get() or []
        indices = mesh.GetFaceVertexIndicesAttr().Get() or []
        points = mesh.GetPointsAttr().Get() or []

        face_count = len(face_counts)
        point_count = len(points)
        face_vert_count = len(indices)

        if interp in (UsdGeom.Tokens.vertex, UsdGeom.Tokens.varying):
            expected = point_count
        elif interp == UsdGeom.Tokens.uniform:
            expected = face_count
        elif interp == UsdGeom.Tokens.faceVarying:
            expected = face_vert_count
        else:  # "constant"
            expected = 1

        if topo_count != expected:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_028,
                message=(
                    f"Mesh '{prim.GetPath()}' normals have {topo_count} elements but expected {expected} "
                    f"for '{interp}' interpolation."
                ),
                at=prim,
            )

        # Check the actual normal vectors for validity & normalization.
        # For indexed primvars we still validate the value array contents themselves.
        for n in normals:
            if not self._is_finite_vec3(n):
                self._AddFailedCheck(
                    requirement=cap.GeometryRequirements.VG_028,
                    message=f"Mesh '{prim.GetPath()}' has non-finite normal components.",
                    at=prim,
                )
                break
            length = n.GetLength()
            if abs(length - 1.0) > self.UNIT_LENGTH_TOLERANCE:
                self._AddWarning(
                    requirement=cap.GeometryRequirements.VG_028,
                    message=f"Mesh '{prim.GetPath()}' has non-unit normal (length={length:.6f}).",
                    at=prim,
                )
                break


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_029, override=True)
class NormalsWindingsChecker(omni.asset_validator.BaseRuleChecker):
    """
    Check that the mesh has normals that are consistent with the face windings,
    taking into account the 'orientation' attribute.

    We define the meaning of agreement between a normal attribute value and the
    reference normal of a face (quite loosely) as the two having a positive inner product.
    We then sum these inner products, and if the sum is positive, it would be a relatively
    large number (close to the area of the surface) and this would indicate that the winding
    is right-handed. Otherwise, the sum would be a relatively large negative number to
    indicate a left-handed rule having been used for generation of normals.

    Works on non time varying geometry.
    """

    def CheckPrim(self, prim: Usd.Prim) -> None:
        if not prim.IsA(UsdGeom.Mesh):
            return

        mesh = UsdGeom.Mesh(prim)

        points_attr: Usd.Attribute = mesh.GetPointsAttr()
        has_static_points: bool = points_attr.IsAuthored() and not points_attr.ValueMightBeTimeVarying()
        if not has_static_points:
            return
        indices_attr: Usd.Attribute = mesh.GetFaceVertexIndicesAttr()
        has_static_indices: bool = indices_attr.IsAuthored() and not indices_attr.ValueMightBeTimeVarying()
        if not has_static_indices:
            return
        face_sizes_attr: Usd.Attribute = mesh.GetFaceVertexCountsAttr()
        has_static_faces: bool = face_sizes_attr.IsAuthored() and not face_sizes_attr.ValueMightBeTimeVarying()
        if not has_static_faces:
            return

        orientation_attr: Usd.Attribute = mesh.GetOrientationAttr()
        has_static_orientation: bool = not orientation_attr.ValueMightBeTimeVarying()
        if not has_static_orientation:
            return

        src = _get_normals_source(mesh, Usd.TimeCode.EarliestTime())
        if src is None:
            return

        interp, normals, normals_indexed, normals_indices = src[0], src[1], src[4], src[5]

        winding_bias = compute_winding_bias(mesh, interp, normals, normals_indexed, normals_indices)

        # Pull topology
        orientation = orientation_attr.Get(Usd.TimeCode.EarliestTime()) or UsdGeom.Tokens.rightHanded

        if (winding_bias >= 0) != (orientation == UsdGeom.Tokens.rightHanded):
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_029,
                message=f"Mesh '{prim.GetPath()}' has normals inconsistent with the face windings.",
                at=prim,
            )


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_014, override=True)
class ValidateTopologyChecker(omni.asset_validator.BaseRuleChecker):
    """
    Validate the topology of a mesh on all time samples.
    """

    @classmethod
    def _get_time_samples(cls, attribute: Usd.Attribute) -> Iterator[Usd.TimeCode]:
        if attribute.Get(Usd.TimeCode.Default()):
            yield Usd.TimeCode.Default()
        for time in attribute.GetTimeSamples():
            yield Usd.TimeCode(time)

    def _get_validate_topology_args(self, mesh: UsdGeom.Mesh) -> tuple[Vt.IntArray, Vt.IntArray, int]:
        # Get attributes
        points_attr: Usd.Attribute = mesh.GetPointsAttr()
        indices_attr: Usd.Attribute = mesh.GetFaceVertexIndicesAttr()
        counts_attr: Usd.Attribute = mesh.GetFaceVertexCountsAttr()
        # Determine time varying
        static_points: bool = not points_attr.ValueMightBeTimeVarying()
        static_indices: bool = not indices_attr.ValueMightBeTimeVarying()
        static_counts: bool = not counts_attr.ValueMightBeTimeVarying()
        static_topology: bool = static_indices and static_counts
        # Decide scenario
        if static_points and static_topology:
            indices: Vt.IntArray = indices_attr.Get(Usd.TimeCode.EarliestTime())
            counts: Vt.IntArray = counts_attr.Get(Usd.TimeCode.EarliestTime())
            points_attr_value: Vt.Vec3fArray | None = points_attr.Get(Usd.TimeCode.EarliestTime())
            point_size: int = len(points_attr_value) if points_attr_value else 0
            yield indices, counts, point_size
        elif static_topology:
            indices: Vt.IntArray = indices_attr.Get(Usd.TimeCode.EarliestTime())
            counts: Vt.IntArray = counts_attr.Get(Usd.TimeCode.EarliestTime())
            point_sizes: set[int] = set()
            for time in self._get_time_samples(points_attr):
                point_attr_value: Vt.Vec3fArray | None = points_attr.Get(time)
                point_size = len(point_attr_value) if point_attr_value else 0
                point_sizes.add(point_size)

            for point_size in point_sizes:
                yield indices, counts, point_size
        elif static_points:
            points_attr_value: Vt.Vec3fArray | None = points_attr.Get(Usd.TimeCode.EarliestTime())
            point_size: int = len(points_attr_value) if points_attr_value else 0
            if static_indices:
                indices: Vt.IntArray = indices_attr.Get(Usd.TimeCode.EarliestTime())
                for time in self._get_time_samples(counts_attr):
                    counts: Vt.IntArray = counts_attr.Get(time)
                    yield indices, counts, point_size
            elif static_counts:
                counts: Vt.IntArray = counts_attr.Get(Usd.TimeCode.EarliestTime())
                for time in self._get_time_samples(indices_attr):
                    indices: Vt.IntArray = indices_attr.Get(time)
                    yield indices, counts, point_size
            else:
                times: set[Usd.TimeCode] = set(self._get_time_samples(indices_attr)) & set(
                    self._get_time_samples(counts_attr)
                )
                for time in times:
                    indices: Vt.IntArray = indices_attr.Get(time)
                    counts: Vt.IntArray = counts_attr.Get(time)
                    yield indices, counts, point_size
        else:
            times: set[Usd.TimeCode] = (
                set(self._get_time_samples(points_attr))
                & set(self._get_time_samples(indices_attr))
                & set(self._get_time_samples(counts_attr))
            )
            for time in times:
                indices: Vt.IntArray = indices_attr.Get(time)
                counts: Vt.IntArray = counts_attr.Get(time)
                points: Vt.Vec3fArray | None = points_attr.Get(time)
                point_size: int = len(points) if points else 0
                yield indices, counts, point_size

    def validate(self, mesh: UsdGeom.Mesh) -> None:
        for indices, counts, point_size in self._get_validate_topology_args(mesh):
            if all((indices, counts, point_size)):
                valid_topology, _ = UsdGeom.Mesh.ValidateTopology(indices, counts, point_size)
            else:
                # No Points, no FaceVertexCounts, or no indices - not valid topology
                valid_topology = False

            if not valid_topology:
                self._AddFailedCheck(
                    requirement=cap.GeometryRequirements.VG_014,
                    message="Invalid topology found",
                    at=mesh,
                )
                break

    def CheckPrim(self, prim: Usd.Prim) -> None:
        mesh: UsdGeom.Mesh = UsdGeom.Mesh(prim)
        if mesh:
            self.validate(mesh)


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_MESH_001, override=True)
class GeomShallBeMeshChecker(omni.asset_validator.BaseRuleChecker):
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
            for prim in stage.Traverse():
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


@omni.asset_validator.register_rule("Geometry")
@omni.asset_validator.register_requirements(cap.GeometryRequirements.VG_027, override=True)
class NormalsExistChecker(omni.asset_validator.BaseRuleChecker):
    """
    Check that meshes have normals. All meshes should have normals
    unless they have the subdivision scheme set. Meshes cannot have
    both normals and subdivision set.
    """

    @classmethod
    def set_to_none(cls, _: Usd.Stage, mesh: UsdGeom.Mesh) -> None:
        """Sets subdivision scheme to None"""
        mesh.GetSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)

    def _validate_mesh(self, mesh: UsdGeom.Mesh) -> None:
        # Normals may be defined via attribute or via primvar.
        normals_attr: Usd.Attribute = mesh.GetNormalsAttr()
        primvar_api: UsdGeom.PrimvarsAPI = UsdGeom.PrimvarsAPI(mesh)
        primvar: UsdGeom.Primvar = primvar_api.GetPrimvar(UsdGeom.Tokens.normals)
        has_normals: bool = normals_attr.HasAuthoredValue() or primvar.HasAuthoredValue()

        # Get the subdivision attribute
        subdivision_attr: Usd.Attribute = mesh.GetSubdivisionSchemeAttr()
        subdivision_scheme: str = mesh.GetSubdivisionSchemeAttr().Get()

        # Normals are set but subdivision scheme is not "none". Fail and suggest fix.
        if subdivision_scheme != UsdGeom.Tokens.none and has_normals:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_027,
                message="Normals are defined but subdivision mesh also has normals, either remove normals or set"
                "subdivision scheme to None.",
                at=mesh,
                suggestion=Suggestion(
                    message="Set subdivision scheme to none for a polygonal mesh which uses normals",
                    callable=self.set_to_none,
                    at=AuthoringLayers(subdivision_attr),
                ),
            )

        # No normals and subdivision is set to None. Invalid. Warn and ask user to set one
        elif subdivision_scheme == UsdGeom.Tokens.none and not has_normals:
            self._AddFailedCheck(
                requirement=cap.GeometryRequirements.VG_027,
                message="Either normals should be authored or subdivision should be set to Catmull-Clark or Loop ",
                at=mesh,
            )
            pass

    def CheckPrim(self, prim: Usd.Prim) -> None:
        mesh: UsdGeom.Mesh = UsdGeom.Mesh(prim)
        if mesh:
            self._validate_mesh(mesh)
