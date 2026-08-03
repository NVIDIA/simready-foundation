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
IK Target Generator for Robot Tests (Framework 2.0 port).

Generates deterministic, well-distributed target points for IK testing using:
- Fibonacci sphere algorithm for even spatial distribution
- Farthest-next ordering to maximize robot movement between consecutive targets
- Interleaved out-of-reach targets for workspace boundary testing

Key Features:
- Fully deterministic: same robot reach always produces identical targets
- Configurable number of reachable and out-of-reach targets
- Multiple radius shells for comprehensive workspace coverage
- Upper hemisphere option for typical robot arm configurations

This module is the algorithmic core ported from v1.6's target_generator.py.
The viewport legend authoring (USD spheres, 3D legend, color updates) is NOT
ported here -- those concerns belong to a separate viewport-overlay module.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class IKTarget:
    """
    A single IK test target with metadata.

    Attributes:
        position: World position [x, y, z] as numpy array
        is_reachable: True if target should be reachable, False for intentional out-of-reach
        index: Original generation index for tracking and reproducibility
        orientation: Target EE quaternion (w, x, y, z) in world frame, or None.
            FK-sampled targets carry the orientation the arm demonstrably held
            at that pose, so the goal is a provably feasible 6-DOF pose. None
            means "use the home orientation" (legacy shell targets / out-of-reach).
    """

    position: np.ndarray
    is_reachable: bool
    index: int
    orientation: Optional[np.ndarray] = None


@dataclass
class LegendCounts:
    """
    Current counts for each target category in the legend.

    Used to track and display dynamic counts during test execution.
    """

    pending: int = 0
    reached: int = 0
    solve_failed: int = 0
    motion_failed: int = 0
    out_of_reach: int = 0

    def as_tuple(self) -> Tuple[int, int, int, int, int]:
        """Return counts as tuple for comparison."""
        return (
            self.pending,
            self.reached,
            self.solve_failed,
            self.motion_failed,
            self.out_of_reach,
        )


# =============================================================================
# Fibonacci Sphere Algorithm
# =============================================================================


def _fibonacci_sphere_points(n: int, hemisphere_only: bool = True) -> List[np.ndarray]:
    """
    Generate n evenly-distributed unit vectors using golden ratio spiral.

    The Fibonacci sphere algorithm produces points that are approximately
    evenly distributed on a sphere's surface. This is deterministic - the
    same n always produces the same set of points.

    Args:
        n: Number of points to generate
        hemisphere_only: If True, mirror negative-Z points to upper hemisphere

    Returns:
        List of unit vectors as numpy arrays
    """
    if n <= 0:
        return []

    golden_ratio = (1.0 + np.sqrt(5.0)) / 2.0
    points = []

    for i in range(n):
        # Deterministic: same i always gives same point
        theta = 2.0 * np.pi * i / golden_ratio
        phi = np.arccos(1.0 - 2.0 * (i + 0.5) / n)

        x = np.sin(phi) * np.cos(theta)
        y = np.sin(phi) * np.sin(theta)
        z = np.cos(phi)

        if hemisphere_only and z < 0:
            z = abs(z)  # Mirror to upper hemisphere

        points.append(np.array([x, y, z], dtype=np.float64))

    return points


# =============================================================================
# Farthest-Next Ordering
# =============================================================================


def _order_for_max_movement(points: List[np.ndarray]) -> List[np.ndarray]:
    """
    Reorder points so consecutive points are maximally distant.

    This greedy algorithm ensures the robot makes large, sweeping movements
    between consecutive targets rather than small incremental adjustments.
    The ordering is deterministic - ties are broken by original index.

    Algorithm:
    1. Start with the first point (deterministic starting point)
    2. Repeatedly select the unvisited point farthest from current position
    3. Continue until all points are ordered

    Args:
        points: List of points to reorder

    Returns:
        Reordered list of points for maximum movement
    """
    if len(points) <= 1:
        return list(points)

    ordered = [points[0]]  # Start from first point (deterministic)
    remaining = set(range(1, len(points)))

    while remaining:
        last = ordered[-1]
        # Use tuple key for deterministic tie-breaking: (distance, original_index)
        farthest = max(remaining, key=lambda i: (float(np.linalg.norm(points[i] - last)), i))
        ordered.append(points[farthest])
        remaining.remove(farthest)

    return ordered


# =============================================================================
# Target Interleaving
# =============================================================================


def _interleave_targets(reachable: List[IKTarget], out_of_reach: List[IKTarget]) -> List[IKTarget]:
    """
    Distribute out-of-reach targets evenly among reachable ones.

    This ensures out-of-reach tests are spread throughout the test sequence
    rather than clustered at the end, providing better visual feedback in
    the captured video.

    Args:
        reachable: List of reachable IKTarget objects
        out_of_reach: List of out-of-reach IKTarget objects

    Returns:
        Combined list with out-of-reach targets interleaved
    """
    if not out_of_reach:
        return list(reachable)

    if not reachable:
        return list(out_of_reach)

    result: List[IKTarget] = []
    interval = max(1, len(reachable) // (len(out_of_reach) + 1))
    oor_iter = iter(out_of_reach)

    for i, target in enumerate(reachable):
        result.append(target)
        if (i + 1) % interval == 0:
            try:
                result.append(next(oor_iter))
            except StopIteration:
                pass

    # Append any remaining out-of-reach targets
    result.extend(oor_iter)

    return result


# =============================================================================
# Main Target Generation Function
# =============================================================================


def generate_ik_targets(
    robot_reach: float,
    base_position: np.ndarray,
    num_reachable: int = 22,
    num_out_of_reach: int = 3,
    radius_factors: Tuple[float, ...] = (0.5, 0.7, 0.9),
    out_of_reach_factor: float = 1.3,
    hemisphere_only: bool = True,
) -> List[IKTarget]:
    """
    Generate deterministic IK test targets distributed around workspace.

    Uses Fibonacci sphere for even distribution across multiple radius shells.
    Points at radius_factors are intended to be reachable; points at
    out_of_reach_factor are intentionally beyond reach.

    IMPORTANT: The sphere should be centered on the ROBOT BASE position, not
    the end-effector position. The robot's workspace is a sphere centered on
    its base link, so targets must be generated relative to the base.

    NOTE: Some "reachable" points may fail due to joint limits - this is
    valid test data revealing actual workspace boundaries vs geometric reach.

    Args:
        robot_reach: Estimated robot reach from bounding box (meters)
        base_position: Robot base link world position [x, y, z] - the center
                       of the robot's workspace sphere (NOT the end-effector!)
        num_reachable: Number of reachable targets to generate
        num_out_of_reach: Number of intentionally unreachable targets
        radius_factors: Distance factors for reachable shells (0.5 = 50% of reach)
        out_of_reach_factor: Distance factor for unreachable targets (1.3 = 130%)
        hemisphere_only: If True, mirror points to upper hemisphere

    Returns:
        List of IKTarget objects, interleaved with out-of-reach targets
    """
    base_pos = np.array(base_position, dtype=np.float64).flatten()

    if num_reachable <= 0 and num_out_of_reach <= 0:
        return []

    # Distribute reachable targets across radius shells
    reachable_targets: List[IKTarget] = []

    if num_reachable > 0 and radius_factors:
        # Calculate how many points per shell
        num_shells = len(radius_factors)
        points_per_shell = num_reachable // num_shells
        remainder = num_reachable % num_shells

        target_idx = 0
        for shell_idx, radius_factor in enumerate(radius_factors):
            # Distribute remainder to outer shells first
            shell_points = points_per_shell
            if shell_idx >= num_shells - remainder:
                shell_points += 1

            if shell_points <= 0:
                continue

            # Generate Fibonacci sphere points for this shell
            unit_vectors = _fibonacci_sphere_points(shell_points, hemisphere_only)

            # Scale by radius and add base position
            radius = robot_reach * radius_factor
            for uv in unit_vectors:
                world_pos = base_pos + uv * radius
                reachable_targets.append(
                    IKTarget(
                        position=world_pos,
                        is_reachable=True,
                        index=target_idx,
                    )
                )
                target_idx += 1

    # Apply farthest-next ordering to reachable targets
    if len(reachable_targets) > 1:
        positions = [t.position for t in reachable_targets]
        ordered_positions = _order_for_max_movement(positions)

        # Rebuild targets with ordered positions, preserving indices
        ordered_reachable: List[IKTarget] = []
        for new_idx, pos in enumerate(ordered_positions):
            # Find original target with this position
            for orig_target in reachable_targets:
                if np.allclose(orig_target.position, pos):
                    ordered_reachable.append(
                        IKTarget(
                            position=pos,
                            is_reachable=True,
                            index=new_idx,
                        )
                    )
                    break
        reachable_targets = ordered_reachable

    # Generate out-of-reach targets
    out_of_reach_targets: List[IKTarget] = []

    if num_out_of_reach > 0:
        # Generate Fibonacci sphere points for out-of-reach shell
        unit_vectors = _fibonacci_sphere_points(num_out_of_reach, hemisphere_only)

        radius = robot_reach * out_of_reach_factor
        for i, uv in enumerate(unit_vectors):
            world_pos = base_pos + uv * radius
            out_of_reach_targets.append(
                IKTarget(
                    position=world_pos,
                    is_reachable=False,
                    index=len(reachable_targets) + i,
                )
            )

    # Interleave out-of-reach targets with reachable targets
    final_targets = _interleave_targets(reachable_targets, out_of_reach_targets)

    # Re-index for final ordering
    for i, target in enumerate(final_targets):
        target.index = i

    return final_targets


# =============================================================================
# SCARA Cylindrical Target Generator
# =============================================================================


def generate_scara_ik_targets(
    robot_reach: float,
    base_position: np.ndarray,
    ee_position: np.ndarray,
    z_limits: Tuple[float, float],
    num_reachable: int = 5,
    num_out_of_reach: int = 2,
    radius_factors: Tuple[float, ...] = (0.5, 0.7, 0.9),
    out_of_reach_factor: float = 1.3,
) -> List["IKTarget"]:
    """
    Generate IK test targets for a SCARA robot in a cylindrical annulus.

    Unlike the Fibonacci-sphere generator used for 6-DOF arms, SCARA robots
    operate in a horizontal annular cylinder (XY plane with limited Z stroke).
    This function distributes targets accordingly:

    - Radii: ``radius_factors * robot_reach`` (same shells as sphere generator)
    - Angles: evenly spaced in [0, 2*pi] - no hemisphere restriction
    - Heights: 3 levels across ``z_limits`` (lo, mid, hi)

    Args:
        robot_reach: Estimated robot reach in meters (used for radius scaling).
        base_position: Robot base world position [x, y, z].
        ee_position: Current end-effector world position (provides Z reference).
        z_limits: (lower, upper) prismatic DOF limits in meters; applied as
                  offsets from ``ee_position[2]`` to get world Z levels.
        num_reachable: Number of reachable targets to generate.
        num_out_of_reach: Number of intentionally out-of-reach targets.
        radius_factors: Shell radii as fraction of ``robot_reach``.
        out_of_reach_factor: Radius factor for out-of-reach targets.

    Returns:
        List of IKTarget objects interleaved with out-of-reach targets.
    """
    base_pos = np.array(base_position, dtype=np.float64).flatten()
    ee_pos = np.array(ee_position, dtype=np.float64).flatten()

    if num_reachable <= 0 and num_out_of_reach <= 0:
        return []

    # Z levels: distribute across prismatic stroke centred on current EE Z.
    # Apply a 20 % inward margin so targets are never placed at the exact J3
    # joint-limit boundary where the DLS solver stalls due to joint clamping.
    z_lo_raw = float(ee_pos[2]) + float(z_limits[0])
    z_hi_raw = float(ee_pos[2]) + float(z_limits[1])
    z_range = z_hi_raw - z_lo_raw
    margin = 0.2 * z_range if z_range > 0.01 else 0.0
    z_lo = z_lo_raw + margin
    z_hi = z_hi_raw - margin
    z_mid = (z_lo + z_hi) / 2.0
    z_levels = [z_lo, z_mid, z_hi]

    # Minimum clearance from base axis (avoids singularity at r=0)
    min_radius_factor = 0.35

    # Determine the single effective target radius using the EE home XY distance.
    #
    # WHY a single radius ring (not multi-shell):
    #   SCARA robots have an annular workspace in XY.  Placing targets at inner radii
    #   (e.g. 0.5 * reach) requires large J2 displacement from home to reduce arm
    #   extension. When J2 is near 0 (arm fully extended), the DLS Jacobian column
    #   for J2 is near-zero in the radius-reduction direction - DLS barely moves J2
    #   each iteration and the stall detector fires within ~30 iterations. Targets
    #   at inner radii all fail even though the robot geometrically CAN reach them
    #   (FRS proves it can).
    #
    #   Using r_home_xy as the sole radius means J2 stays near home and DLS only
    #   needs to converge J1 (azimuth - large Jacobian column) and J3 (height).
    #   All num_reachable targets are spread evenly around a 360 deg ring at this
    #   radius, cycling through the three Z-levels.  This tests meaningful J1 + J3
    #   variation without the J2 singularity trap.  J2 range is independently
    #   tested by the FRS phase.
    r_home_xy = float(np.linalg.norm(ee_pos[:2] - base_pos[:2]))
    r_effective = max(robot_reach * min_radius_factor, r_home_xy)

    # Compute the home arm direction (world angle from base to EE in XY plane).
    # Used to centre target angles around home so J1 rotation stays small and
    # within the robot's joint range.
    home_arm_angle = float(
        np.arctan2(
            float(ee_pos[1]) - float(base_pos[1]),
            float(ee_pos[0]) - float(base_pos[0]),
        )
    )

    reachable_targets: List[IKTarget] = []
    target_idx = 0
    angles: List[float] = []

    if num_reachable > 0:
        num_z = len(z_levels)
        # Distribute all reachable targets evenly around the full 360 deg circle,
        # CENTRED on the home arm direction.
        #
        # WHY anchor to home arm direction:
        #   SCARA J1 limits are typically +/- 145-155 deg from home.  A fixed
        #   offset (e.g. pi/4) ignores the robot's actual home orientation and
        #   may place one or more targets beyond J1's range.  For example,
        #   sr12ia with arm at +X (0 deg) home and targets at
        #   [45, 117, 189, 261, 333] deg: the 189 deg target requires
        #   J1 ~= +/-171 deg which exceeds +/-145 deg.
        #
        #   Centering around home places the targets symmetrically at
        #   home +/- k*step for k = 0, 1, ..., (n-1)/2.  For n=5 and step=72 deg
        #   the outermost targets are +/-144 deg from home - safely within
        #   +/-145 deg.
        angle_step = 2.0 * np.pi / num_reachable
        # Start at home - (n-1)/2 * step so the set is symmetric about home.
        start_angle = home_arm_angle - (num_reachable - 1) / 2.0 * angle_step
        angles = list(np.linspace(start_angle, start_angle + 2.0 * np.pi, num_reachable, endpoint=False))
        for k, angle in enumerate(angles):
            z_val = z_levels[k % num_z]
            x = float(base_pos[0]) + r_effective * np.cos(angle)
            y = float(base_pos[1]) + r_effective * np.sin(angle)
            world_pos = np.array([x, y, z_val], dtype=np.float64)
            reachable_targets.append(
                IKTarget(
                    position=world_pos,
                    is_reachable=True,
                    index=target_idx,
                )
            )
            target_idx += 1

    # Apply farthest-next ordering for maximum robot motion between targets
    if len(reachable_targets) > 1:
        positions = [t.position for t in reachable_targets]
        ordered_positions = _order_for_max_movement(positions)
        ordered_reachable: List[IKTarget] = []
        for new_idx, pos in enumerate(ordered_positions):
            for orig in reachable_targets:
                if np.allclose(orig.position, pos):
                    ordered_reachable.append(IKTarget(position=pos, is_reachable=True, index=new_idx))
                    break
        reachable_targets = ordered_reachable

    # Out-of-reach targets: placed beyond max reach in the horizontal plane
    out_of_reach_targets: List[IKTarget] = []
    if num_out_of_reach > 0:
        oor_radius = robot_reach * out_of_reach_factor
        angles_oor = np.linspace(0, 2 * np.pi, num_out_of_reach, endpoint=False)
        for i, angle in enumerate(angles_oor):
            x = float(base_pos[0]) + oor_radius * np.cos(angle)
            y = float(base_pos[1]) + oor_radius * np.sin(angle)
            z_val = z_levels[i % len(z_levels)]
            world_pos = np.array([x, y, z_val], dtype=np.float64)
            out_of_reach_targets.append(
                IKTarget(
                    position=world_pos,
                    is_reachable=False,
                    index=len(reachable_targets) + i,
                )
            )

    final_targets = _interleave_targets(reachable_targets, out_of_reach_targets)
    for i, target in enumerate(final_targets):
        target.index = i

    # Silenced informational logging (radius factors / unused variables) is
    # intentionally not preserved here. The local computations above remain
    # so behavior matches v1 exactly; only the Log.info side-effects are
    # dropped per the framework 2.0 translation rules.
    _ = (radius_factors, z_lo_raw, z_hi_raw, r_home_xy, home_arm_angle, angles)

    return final_targets


# =============================================================================
# Target sphere visualization (ported from v1.6 target_generator.py)
#
# Renders each IK target as a coloured UsdGeom.Sphere so the captured video
# shows where the robot is reaching. Per-target color is updated live during
# motion playback (gray = pending, green = reached, red = solver failed,
# orange = motion failed, magenta = out-of-reach correctly failed). Phase
# code calls cleanup_target_spheres after the test so the asset stage stays
# clean between tests.
# =============================================================================

# Color palette (RGB 0-1). Each color maps to ONE outcome so the captured
# video and the metric breakdown line up 1:1 (see `_record_phase_metrics`
# in jacobian_ik.py for the corresponding metric names).
COLOR_TARGET_PENDING = (0.5, 0.5, 0.5)  # gray:    not yet visited
COLOR_TARGET_REACHED = (0.2, 1.0, 0.2)  # green:   in-reach + reached within tolerance
COLOR_TARGET_SOLVE_FAILED = (1.0, 0.2, 0.2)  # red:     in-reach but solver could not find a joint solution
COLOR_TARGET_MOTION_FAILED = (1.0, 0.6, 0.2)  # orange:  in-reach + solver ok but motion did not track
COLOR_TARGET_OUT_OF_REACH_OK = (0.7, 0.2, 1.0)  # magenta: out-of-reach and solver correctly flagged unreachable
COLOR_TARGET_OOR_FALSE_POSITIVE = (1.0, 0.95, 0.2)  # yellow: out-of-reach but solver claimed reachable (FALSE POSITIVE)


def create_target_spheres_from_targets(stage, parent_path, targets, radius):
    # type: (Any, str, List[IKTarget], float) -> List[Any]
    """Create one colored sphere per IK target. All start as PENDING (gray).

    Returns the list of sphere prims in target order so phase code can
    update color per-target during motion playback. Silent on individual
    failures (one bad target should not block others).
    """
    if stage is None or not targets:
        return []
    try:
        from pxr import Gf, Sdf, UsdGeom
    except Exception:
        return []
    parent = stage.GetPrimAtPath(parent_path)
    if not parent or not parent.IsValid():
        try:
            stage.DefinePrim(parent_path, "Scope")
        except Exception:
            return []
    sphere_prims = []  # type: List[Any]
    for target in targets:
        sphere_path = "%s/target_%d" % (parent_path, target.index)
        try:
            sphere = UsdGeom.Sphere.Define(stage, Sdf.Path(sphere_path))
            sphere.GetRadiusAttr().Set(float(radius))
            xformable = UsdGeom.Xformable(sphere.GetPrim())
            pos = target.position
            xformable.AddTranslateOp().Set(Gf.Vec3d(float(pos[0]), float(pos[1]), float(pos[2])))
            _bind_color_material(
                stage,
                sphere.GetPrim(),
                "%s/mat_%d" % (parent_path, target.index),
                COLOR_TARGET_PENDING,
            )
            sphere_prims.append(sphere.GetPrim())
        except Exception:
            sphere_prims.append(None)
    return sphere_prims


def set_target_sphere_color(prim, color):
    # type: (Any, Tuple[float, float, float]) -> None
    """Update the diffuse color on a target sphere's bound material."""
    if prim is None or not prim.IsValid():
        return
    try:
        from pxr import Gf, UsdShade
    except Exception:
        return
    try:
        binding_api = UsdShade.MaterialBindingAPI(prim)
        material = binding_api.GetDirectBinding().GetMaterial()
        if not material:
            return
        for child in material.GetPrim().GetChildren():
            shader = UsdShade.Shader(child)
            if shader:
                diffuse_input = shader.GetInput("diffuseColor")
                if diffuse_input:
                    diffuse_input.Set(Gf.Vec3f(float(color[0]), float(color[1]), float(color[2])))
                    return
    except Exception:
        pass


def cleanup_target_spheres(stage, scope_path):
    # type: (Any, str) -> None
    """Remove the target-spheres scope and all children."""
    if stage is None or not scope_path:
        return
    try:
        from pxr import Sdf

        prim = stage.GetPrimAtPath(scope_path)
        if prim and prim.IsValid():
            stage.RemovePrim(Sdf.Path(scope_path))
    except Exception:
        pass


def _bind_color_material(stage, prim, mat_path, color):
    # type: (Any, Any, str, Tuple[float, float, float]) -> None
    """Author a UsdPreviewSurface material with the given diffuse color and bind to prim."""
    try:
        from pxr import Gf, Sdf, UsdShade

        material = UsdShade.Material.Define(stage, Sdf.Path(mat_path))
        shader = UsdShade.Shader.Define(stage, Sdf.Path(mat_path + "/shader"))
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(float(color[0]), float(color[1]), float(color[2]))
        )
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)
    except Exception:
        pass
