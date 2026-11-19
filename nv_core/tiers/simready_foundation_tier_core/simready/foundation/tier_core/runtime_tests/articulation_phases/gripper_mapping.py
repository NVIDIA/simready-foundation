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
"""Core-only live gripper endpoint mapping; geometry is a proxy, not contact.

Probes command existing position drives sparsely. They never teleport links,
command mimic followers, change gains, or infer OPEN from a rest target/name.
"""

import itertools

import numpy as np
from pxr import Gf, Usd, UsdGeom, UsdPhysics
from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
    note_secondary_error,
)


class GripperMappingError(RuntimeError):
    """A runtime/setup observation could not establish an endpoint mapping."""


def _optional_probe_diagnostic(operation, primary=None):
    """Never replace a present measurement/restore error with diagnostics."""
    try:
        operation()
    except BaseException as error:
        if primary is None and not isinstance(error, Exception):
            raise  # A first cancellation during normal execution stays real.
        if primary is not None:
            note_secondary_error(primary, lambda error=error: f"Optional gripper-probe diagnostics failed: {error}")


def _unit(vector):
    vector = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if vector.shape != (3,) or not np.isfinite(vector).all() or norm <= 1e-12:
        raise GripperMappingError("FET028 mapping: invalid approach direction")
    return vector / norm


def _rotate(points, quaternion):
    quaternion = np.asarray(quaternion, dtype=np.float64)
    if quaternion.shape != (4,) or not np.isfinite(quaternion).all() or np.linalg.norm(quaternion) <= 1e-12:
        raise GripperMappingError("FET028 mapping: invalid live link orientation")
    quaternion = quaternion / np.linalg.norm(quaternion)
    rotation = Gf.Rotation(Gf.Quatd(float(quaternion[3]), *[float(value) for value in quaternion[:3]]))
    return np.asarray([rotation.TransformDir(Gf.Vec3d(*point.tolist())) for point in points], dtype=np.float64)


def _inverse_quaternion(quaternion):
    result = np.asarray(quaternion, dtype=np.float64).copy()
    result[:3] *= -1
    return result


def _owned_geometry_points(stage, body_path):
    """Bound corners in the body frame, excluding nested rigid-body geometry.

    Preserve accumulated nonuniform scale; reject shear instead of averaging it.
    A local bound describes the available shape proxy, not physical contacts.
    """
    body = stage.GetPrimAtPath(body_path)
    if not body or not body.IsValid():
        return None
    cache = UsdGeom.XformCache()
    body_world = cache.GetLocalToWorldTransform(body)
    basis = np.asarray(body_world, dtype=np.float64)[:3, :3]
    scales = np.linalg.norm(basis, axis=1)
    if not np.isfinite(scales).all() or np.any(scales <= 1e-12):
        return None
    normalized = basis / scales[:, None]
    if not np.allclose(normalized @ normalized.T, np.eye(3), atol=1e-5):
        raise GripperMappingError(f"FET028 mapping: sheared rigid-body geometry cannot be mapped: {body_path}")
    if np.linalg.det(normalized) <= 0:
        raise GripperMappingError(f"FET028 mapping: reflected rigid-body frame is unsupported: {body_path}")
    inverse = body_world.GetInverse()
    result = []
    for prim in Usd.PrimRange(body):
        if not prim.IsA(UsdGeom.Boundable):
            continue
        ancestor = prim
        owned = True
        while ancestor != body:
            if ancestor.HasAPI(UsdPhysics.RigidBodyAPI):
                owned = False
                break
            ancestor = ancestor.GetParent()
        if not owned:
            continue
        if UsdGeom.Imageable(prim).ComputePurpose() == UsdGeom.Tokens.guide:
            # Annotation/site geometry is not a pad. An explicitly enabled
            # guide collider still participates physically and remains usable.
            ancestor = prim
            collision = False
            while ancestor and ancestor.IsValid():
                if ancestor.HasAPI(UsdPhysics.CollisionAPI):
                    collision = bool(UsdPhysics.CollisionAPI(ancestor).GetCollisionEnabledAttr().Get())
                    break
                if ancestor == body:
                    break
                ancestor = ancestor.GetParent()
            if not collision:
                continue
        boundable = UsdGeom.Boundable(prim)
        extent_attr = boundable.GetExtentAttr()
        extent = extent_attr.Get() if extent_attr.HasAuthoredValueOpinion() else None
        if extent is None:
            extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
        if extent is None or len(extent) != 2:
            continue
        extent = np.asarray(extent, dtype=np.float64)
        if extent.shape != (2, 3) or not np.isfinite(extent).all() or np.any(extent[1] < extent[0]):
            continue
        relative = cache.GetLocalToWorldTransform(prim) * inverse
        for coordinates in itertools.product(*zip(extent[0], extent[1], strict=True)):
            point = relative.Transform(Gf.Vec3d(*coordinates))
            result.append(np.asarray(point, dtype=np.float64) * scales)
    points = np.asarray(result, dtype=np.float64) if result else None
    if points is not None and not np.isfinite(points).all():
        raise GripperMappingError(f"FET028 mapping: non-finite owned geometry: {body_path}")
    return points


def _live_geometry_tips(robot, geometry, approach, reference_path=None, diagnostics=None):
    """Read one complete live snapshot of owned distal face centroids."""
    requested = list(geometry)
    if reference_path is not None and reference_path not in requested:
        requested.append(reference_path)
    poses = robot.get_link_world_transforms(requested)
    if set(poses) != set(requested):
        raise GripperMappingError("FET028 mapping: partial/stale live fingertip transforms")
    reference = poses.get(reference_path)
    if reference is not None:
        position = np.asarray(reference[0], dtype=np.float64)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise GripperMappingError("FET028 mapping: invalid gripper-base reference")
        approach = _rotate(np.asarray([approach]), reference[1])[0]
    if diagnostics is not None:
        diagnostics.update(
            {
                "coordinate_basis": "world and gripper-base-relative stage lengths; geometry proxies, not contacts",
                "reference_path": reference_path,
                "reference_position_world": np.asarray(reference[0]).tolist() if reference is not None else None,
                "reference_quaternion_xyzw": np.asarray(reference[1]).tolist() if reference is not None else None,
                "candidate_count": len(geometry),
                "candidates": [],
                "candidates_omitted": max(0, len(geometry) - 64),
            }
        )
    tips = {}
    for path, points in geometry.items():
        position, quaternion = poses[path]
        position = np.asarray(position, dtype=np.float64)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise GripperMappingError("FET028 mapping: non-finite live fingertip position")
        world = _rotate(points, quaternion) + position
        projections = world @ approach
        tolerance = max(1e-9, float(np.ptp(projections)) * 1e-6)
        tips[path] = np.mean(world[projections >= max(projections) - tolerance], axis=0)
        world_tip = tips[path].copy()
        if reference is not None:
            tips[path] = _rotate(
                np.asarray([tips[path] - np.asarray(reference[0])]), _inverse_quaternion(reference[1])
            )[0]
        if diagnostics is not None and len(diagnostics["candidates"]) < 64:
            diagnostics["candidates"].append(
                {
                    "body_path": path,
                    "body_position_world": position.tolist(),
                    "body_quaternion_xyzw": np.asarray(quaternion).tolist(),
                    "tip_position_world": world_tip.tolist(),
                    "tip_position_reference": tips[path].tolist(),
                    "geometry_min_world": np.min(world, axis=0).tolist(),
                    "geometry_max_world": np.max(world, axis=0).tolist(),
                }
            )
    return tips


def live_pad_tips(robot, stage, paths, approach_world):
    """Resolved-pad geometry for descent, with the same ownership/scale rules."""
    geometry = {path: _owned_geometry_points(stage, path) for path in dict.fromkeys(paths)}
    if not geometry or any(points is None for points in geometry.values()):
        raise GripperMappingError("FET028 mapping: resolved pad geometry is unavailable")
    return _live_geometry_tips(robot, geometry, _unit(approach_world))


class GripperProbe:
    """Bounded sparse live probes with command restoration, not state rollback."""

    def __init__(self, ctx, robot, stage, paths, indices, config, approach, reference_path=None):
        self.ctx, self.robot = ctx, robot
        self.stage = stage
        self.indices = tuple(dict.fromkeys(int(index) for index in indices))
        self.approach = _unit(approach)
        self.reference_path = reference_path
        self.reference_initial = None
        if reference_path is not None:
            initial = robot.get_link_world_transforms([reference_path]).get(reference_path)
            if (
                initial is None
                or np.asarray(initial[0]).shape != (3,)
                or not np.isfinite(np.asarray(initial[0], dtype=np.float64)).all()
            ):
                raise GripperMappingError("FET028 mapping: live gripper-base reference is unavailable")
            self.reference_initial = initial
            self.approach = _rotate(np.asarray([self.approach]), _inverse_quaternion(initial[1]))[0]
        self.steps = int(config.get("open_close_detect_steps", 120))
        self.inset = float(config.get("detect_limit_inset_frac", 0.05))
        if not 1 <= self.steps <= 10000 or not np.isfinite(self.inset) or not 0 <= self.inset < 0.5:
            raise GripperMappingError("FET028 mapping: invalid bounded probe steps/inset configuration")
        self.lowers, self.uppers = [
            np.asarray(values, dtype=np.float64) for values in robot.get_joint_position_limits()
        ]
        self.original = self._positions()
        if self.lowers.shape != self.original.shape or self.uppers.shape != self.original.shape:
            raise GripperMappingError("FET028 mapping: complete joint limits are unavailable")
        targets = np.asarray(robot.get_joint_position_targets(), dtype=np.float64)
        if targets.shape != self.original.shape:
            raise GripperMappingError("FET028 mapping: prior leader target readback is unavailable")
        self.targets = {}
        for index in self.indices:
            if not 0 <= index < len(self.original) or not np.isfinite(targets[index]):
                raise GripperMappingError(
                    f"FET028 mapping: prior leader target readback is unavailable for DOF {index}"
                )
            if (
                not np.isfinite([self.lowers[index], self.uppers[index]]).all()
                or self.uppers[index] <= self.lowers[index]
            ):
                raise GripperMappingError(f"FET028 mapping: finite ordered limits are required for DOF {index}")
            self.targets[index] = float(targets[index])
        self.geometry = {}
        self.candidate_paths = list(dict.fromkeys(paths))
        for path in self.candidate_paths:
            points = _owned_geometry_points(stage, path)
            if points is not None:
                self.geometry[path] = points
        if not self.geometry:
            raise GripperMappingError("FET028 mapping: no owned fingertip geometry is available")
        self.meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
        if not np.isfinite(self.meters_per_unit) or self.meters_per_unit <= 0:
            raise GripperMappingError("FET028 mapping: invalid stage length scale")
        self.moved = False
        self.pending_restore = set()
        self.diagnostics = {}
        self.observers = {}
        self.last_geometry_diagnostics = None
        trial_index = config.get("_probe_trial_index", 0)
        self.trial_index = (
            trial_index
            if isinstance(trial_index, int) and not isinstance(trial_index, bool) and trial_index >= 0
            else 0
        )
        self.trial_shape = str(config.get("_probe_trial_shape", ""))[:64]
        self.diagnostic_suffix = "" if self.trial_index == 0 else f"_trial_{self.trial_index + 1:03d}"

    def _evidence(self, index):
        if index not in self.diagnostics:
            self.diagnostics[index] = {
                "schema_version": 1,
                "trial_index": self.trial_index,
                "trial_shape": self.trial_shape,
                "dof_index": int(index),
                "joint_name": str(self.robot.dof_names[index]),
                "joint_units": "native articulation position units; see motion metadata when identity resolves",
                "lower_limit": float(self.lowers[index]),
                "upper_limit": float(self.uppers[index]),
                "inset_fraction": self.inset,
                "original_position": float(self.original[index]),
                "prior_target": self.targets[index],
                "meters_per_unit": self.meters_per_unit,
                "reference_path": self.reference_path,
                "candidate_body_paths": self.candidate_paths[:64],
                "candidate_body_paths_omitted": max(0, len(self.candidate_paths) - 64),
                "missing_geometry_paths": [path for path in self.candidate_paths if path not in self.geometry][:64],
                "geometry_basis": "owned bound corners transformed by live tensor poses; not measured contacts",
                "ramps": [],
                "endpoints": {},
            }
        return self.diagnostics[index]

    def _publish(self, index, primary=None):
        # Diagnostics are optional: recording failures cannot replace the
        # mapping error, alter its criteria, or interfere with restoration.
        _optional_probe_diagnostic(
            lambda: self.ctx.add_metric(
                f"detect_probe_evidence_{index}{self.diagnostic_suffix}", self._evidence(index)
            ),
            primary,
        )

    def _motion_sample(self, index, commanded, achieved, phase):
        if not callable(getattr(self.ctx, "begin_motion_history", None)):
            return
        try:
            if index not in self.observers:
                from simready.foundation.tier_core.runtime_tests.motion_observer import (
                    MotionObserver,
                    joint_metadata,
                )

                root = self.robot.prim_path if hasattr(self.robot, "prim_path") else "/"
                identity = joint_metadata(
                    self.stage,
                    self.stage.GetPrimAtPath(root),
                    self.robot.dof_names[index],
                    root_path=getattr(self.robot, "prim_path", None),
                )
                unit = identity["unit"]
                identity.update(
                    {
                        "dof_index": int(index),
                        "trial_index": self.trial_index,
                        "trial_shape": self.trial_shape,
                        "trial_number": self.trial_index + 1,
                        "shape": self.trial_shape,
                        "clock_basis": "Kit timeline clock, not a solver execution clock",
                        "observation_basis": "existing post-step joint readback; no additional physics ticks",
                    }
                )
                self.observers[index] = MotionObserver(
                    self.ctx,
                    f"gripper_probe_joint_{index:03d}{self.diagnostic_suffix}",
                    {
                        "target": {"unit": unit, "source": "actual sparse endpoint-probe command"},
                        "position": {"unit": unit, "source": "existing post-step articulation position readback"},
                        "error": {"unit": unit, "source": "probe target minus achieved position"},
                    },
                    metadata=identity,
                    sample_stride=4,
                )
            self.observers[index].sample(
                {"target": commanded, "position": achieved, "error": commanded - achieved}, phase=phase
            )
        except Exception:
            pass

    def _positions(self):
        values = np.asarray(self.robot.get_joint_positions(), dtype=np.float64)
        if values.shape != (self.robot.dof_count,) or not np.isfinite(values).all():
            raise GripperMappingError("FET028 mapping: joint readback is unavailable/non-finite")
        return values.copy()

    async def __aenter__(self):
        return self

    def _hold_peers(self):
        if self.moved:
            return
        # Hold every selected leader at its measured start while probing peers.
        # Restore original commands only when the entire mapping is complete.
        self.moved = True
        for index in self.indices:
            self.robot.set_joint_position_target(index, float(self.original[index]))

    async def _ramp(self, index, target):
        start = float(self._positions()[index])
        evidence = self._evidence(index)
        phase = getattr(self, "probe_phase", "restore")
        ramp = {
            "phase": phase,
            "start_position": start,
            "commanded_target": float(target),
            "steps_requested": self.steps,
            "steps_attempted": 0,
            "steps_observed": 0,
            "samples": [],
            "samples_omitted": 0,
        }
        evidence["ramps"].append(ramp)
        stride = max(1, (self.steps + 31) // 32)
        primary = None
        try:
            for step in range(self.steps):
                fraction = float(step + 1) / self.steps
                eased = fraction * fraction * (3.0 - 2.0 * fraction)
                commanded = start + (float(target) - start) * eased
                self.robot.set_joint_position_target(index, commanded)
                self.moved = True
                self.pending_restore.add(index)
                ramp["steps_attempted"] = step + 1
                ramp["last_commanded_position"] = commanded
                await self.ctx.step_one()
                positions = self._positions()  # Keep the existing required-view guard.
                achieved = float(positions[index])
                ramp["steps_observed"] = step + 1
                ramp["last_achieved_position"] = achieved
                if step == 0 or (step + 1) % stride == 0 or step + 1 == self.steps:
                    ramp["samples"].append({"step": step + 1, "commanded": commanded, "achieved": achieved})
                else:
                    ramp["samples_omitted"] += 1
                self._motion_sample(index, commanded, achieved, phase)
        except BaseException as error:
            primary = error
            raise
        finally:
            self._publish(index, primary)

    def read(self):
        """One transform snapshot supplies all geometry points for this sample."""
        diagnostics = {}
        tips = _live_geometry_tips(self.robot, self.geometry, self.approach, self.reference_path, diagnostics)
        self.last_geometry_diagnostics = diagnostics
        return self._positions(), tips

    async def endpoints(self, index):
        self._hold_peers()
        lower, upper = float(self.lowers[index]), float(self.uppers[index])
        inset = (upper - lower) * self.inset
        self.probe_phase = "lower_endpoint"
        await self._ramp(index, lower + inset)
        first = self.read()
        evidence = self._evidence(index)
        evidence["endpoints"]["lower"] = {
            "commanded": lower + inset,
            "achieved": float(first[0][index]),
            "geometry": self.last_geometry_diagnostics,
        }
        self._publish(index)
        self.probe_phase = "upper_endpoint"
        await self._ramp(index, upper - inset)
        second = self.read()
        evidence["endpoints"]["upper"] = {
            "commanded": upper - inset,
            "achieved": float(second[0][index]),
            "geometry": self.last_geometry_diagnostics,
        }
        evidence["achieved_endpoint_delta"] = float(second[0][index] - first[0][index])
        evidence["required_endpoint_delta"] = max(1e-9, (upper - lower) * 1e-4)
        self._publish(index)
        try:
            self.ctx.log(
                "FET028 probe DOF %d: commanded endpoints=(%.9g, %.9g), achieved=(%.9g, %.9g); "
                "world/reference geometry retained in %s (bounds proxy, not contacts)."
                % (
                    index,
                    lower + inset,
                    upper - inset,
                    first[0][index],
                    second[0][index],
                    f"detect_probe_evidence_{index}{self.diagnostic_suffix}",
                )
            )
        except Exception:
            pass
        if second[0][index] - first[0][index] <= max(1e-9, (upper - lower) * 1e-4):
            raise GripperMappingError(f"FET028 mapping: stale/insignificant achieved endpoint motion for DOF {index}")
        return first, second

    async def restore_pose(self, index):
        self.probe_phase = "restore"
        await self._ramp(index, float(self.original[index]))
        error = abs(float(self._positions()[index]) - float(self.original[index]))
        if error > max(1e-8, (self.uppers[index] - self.lowers[index]) * 0.05):
            raise GripperMappingError(f"FET028 mapping: leader pose restoration did not settle for DOF {index}")
        self.pending_restore.discard(index)

    async def __aexit__(self, exc_type, exc, traceback):
        if self.moved:
            restoration_error = None
            try:
                for index in self.indices:
                    if index in self.pending_restore:
                        await self.restore_pose(index)
            except BaseException as error:
                restoration_error = error
            finally:
                # Commands are saved before any movement. Restore every
                # selected buffer entry even if physical return was interrupted;
                # one failing setter must not prevent restoring other leaders.
                for index in self.indices:
                    try:
                        self.robot.set_joint_position_target(index, self.targets[index])
                    except BaseException as error:
                        if restoration_error is None:
                            restoration_error = error
                for observer in self.observers.values():
                    try:
                        complete = exc is None and restoration_error is None
                        if not complete and observer.history is not None:
                            observer.history.mark_partial("endpoint mapping did not complete")
                        observer.finish("mapping_completed" if complete else "mapping_interrupted")
                    except BaseException as diagnostic_error:
                        primary = exc if exc is not None else restoration_error
                        if primary is None and not isinstance(diagnostic_error, Exception):
                            raise
                        if primary is not None:
                            note_secondary_error(
                                primary,
                                lambda diagnostic_error=diagnostic_error: (
                                    f"Optional gripper-probe finalization failed: {diagnostic_error}"
                                ),
                            )
            if restoration_error is not None:
                primary = exc if exc is not None else restoration_error
                _optional_probe_diagnostic(
                    lambda: self.ctx.log(f"FET028 mapping restoration incomplete: {restoration_error}"), primary
                )
                _optional_probe_diagnostic(lambda: self.ctx.add_metric("detect_restoration_incomplete", True), primary)
                if exc is None:
                    if not isinstance(restoration_error, Exception):
                        raise restoration_error  # Preserve cancellation/process interruption.
                    raise GripperMappingError(
                        "FET028 mapping: command/pose restoration was incomplete"
                    ) from restoration_error
                # Do not replace cancellation/the original failure. The caller
                # must stop the trial; its normal scene cleanup tears down the rig.
        return False


def _planar(vector, approach):
    return vector - approach * float(np.dot(vector, approach))


def _aperture_mapping(first, second, approach, meters_per_unit, max_opening, branches=None, diagnostics=None):
    """Select distal moving geometry on distinct branches; wider means OPEN.

    GR.003 endpoints and their segment length are deliberately not consumed.
    No static pad guess is authoritative. Apertures are planar geometry proxies.
    """
    first, second = first[1], second[1]
    paths = list(first)
    if len(paths) < 2 or set(first) != set(second):
        raise GripperMappingError("FET028 mapping: fewer than two complete pad geometry observations")
    scale = float(meters_per_unit)
    tolerance = max(1e-6, float(max_opening) * 1e-3)
    depths = {path: max(float(first[path] @ approach), float(second[path] @ approach)) for path in paths}
    deepest = max(depths.values())
    branch = branches or {path: index for index, path in enumerate(paths)}
    if diagnostics is not None:
        diagnostics.update(
            {
                "aperture_change_tolerance_m": tolerance,
                "max_opening_m": float(max_opening),
                "candidate_branches": {path: branch.get(path) for path in paths[:64]},
                "candidate_branches_omitted": max(0, len(paths) - 64),
                "pair_observations": [],
                "pair_observations_omitted": 0,
                "same_branch_pairs_ignored": 0,
            }
        )
    records = []
    for a, b in itertools.combinations(paths, 2):
        if branch.get(a) == branch.get(b):
            if diagnostics is not None:
                diagnostics["same_branch_pairs_ignored"] += 1
            continue
        delta_first, delta_second = first[a] - first[b], second[a] - second[b]
        lower = float(np.linalg.norm(_planar(delta_first, approach))) * scale
        upper = float(np.linalg.norm(_planar(delta_second, approach))) * scale
        if diagnostics is not None:
            if len(diagnostics["pair_observations"]) < 64:
                diagnostics["pair_observations"].append(
                    {"body_paths": [a, b], "lower_m": lower, "upper_m": upper, "change_m": upper - lower}
                )
            else:
                diagnostics["pair_observations_omitted"] += 1
        if abs(upper - lower) <= tolerance:
            continue
        height_mismatch = max(abs(float(delta_first @ approach)), abs(float(delta_second @ approach))) * scale
        proximal_penalty = (2 * deepest - depths[a] - depths[b]) * scale
        score = abs(max(lower, upper) - float(max_opening)) + height_mismatch + 4 * proximal_penalty
        records.append((score, a, b, lower, upper))
    if not records:
        raise GripperMappingError("FET028 mapping: unchanged/ambiguous distal pad aperture; OPEN cannot be inferred")
    records.sort(key=lambda item: item[0])
    best = records[0]
    # Several fingers may form a centric aperture. Use their collective planar
    # spread rather than interpreting GR.003 as a required pair of opposing jaws.
    distal = [path for path in paths if (deepest - depths[path]) * scale <= max(tolerance, max_opening * 0.15)]
    distinct = {}
    for path in distal:
        distinct.setdefault(branch.get(path, path), path)
    if len(distinct) >= 3:
        selected = list(distinct.values())

        def spread(points):
            planar = np.asarray([_planar(points[path], approach) for path in selected])
            return float(np.mean(np.linalg.norm(planar - planar.mean(axis=0), axis=1))) * scale

        lower, upper = spread(first), spread(second)
        if abs(upper - lower) <= tolerance:
            raise GripperMappingError("FET028 mapping: ambiguous centric fingertip spread")
        open_points = second if upper > lower else first
        pair = max(
            itertools.combinations(selected, 2),
            key=lambda pair: float(np.linalg.norm(_planar(open_points[pair[0]] - open_points[pair[1]], approach))),
        )
        return list(pair), lower, upper, "centric planar radius proxy"
    if len(records) > 1 and abs(records[1][0] - best[0]) <= tolerance:
        other = records[1]
        if {best[1], best[2]} != {other[1], other[2]}:
            raise GripperMappingError("FET028 mapping: multiple equally plausible distal pad pairs")
    return [best[1], best[2]], best[3], best[4], "planar pad-separation proxy"


async def map_parallel_endpoints(ctx, robot, fingertips, stage, config, max_opening, reference_path=None):
    """Infer a separate lower/upper convention for every selected leader."""
    indices = list(fingertips.mimic_master_dofs or [int(fingertips.mimic_master_dof)])
    paths = list(fingertips.candidate_tip_paths or fingertips.tip_link_paths)
    mappings, selected_pads = {}, None
    async with GripperProbe(ctx, robot, stage, paths, indices, config, (0.0, 0.0, -1.0), reference_path) as probe:
        for index in indices:
            first, second = await probe.endpoints(index)
            evidence = probe._evidence(index)
            primary = None
            try:
                pads, lower_aperture, upper_aperture, measure = _aperture_mapping(
                    first,
                    second,
                    probe.approach,
                    probe.meters_per_unit,
                    max_opening,
                    getattr(fingertips, "candidate_branches", None),
                    evidence,
                )
            except BaseException as error:
                primary = error
                raise
            finally:
                # Persist comparisons even when the aperture guard rejects
                # the mapping, rather than recording only successful probes.
                probe._publish(index, primary)
            if selected_pads is not None and set(pads) != set(selected_pads):
                raise GripperMappingError("FET028 mapping: independent leaders identify inconsistent pad bodies")
            selected_pads = pads
            lower, upper = float(probe.lowers[index]), float(probe.uppers[index])
            mappings[int(index)] = (upper, lower) if upper_aperture > lower_aperture else (lower, upper)
            ctx.add_metric(f"detect_aperture_lower_m_dof_{index}", lower_aperture)
            ctx.add_metric(f"detect_aperture_upper_m_dof_{index}", upper_aperture)
            ctx.add_metric(f"detect_achieved_lower_dof_{index}", float(first[0][index]))
            ctx.add_metric(f"detect_achieved_upper_dof_{index}", float(second[0][index]))
            opened, closed = mappings[int(index)]
            ctx.log(
                f"FET028 live endpoint mapping DOF {index}: {measure} lower={lower_aperture:.6g} m "
                f"upper={upper_aperture:.6g} m; OPEN={opened:.6g} CLOSED={closed:.6g}. "
                "Measured geometry is not collision contact evidence."
            )
            await probe.restore_pose(index)
    ctx.add_metric("detect_used_authored_grip_line", False)
    return mappings, selected_pads


async def map_hand_endpoints(ctx, robot, fingertips, stage, config, center, classify, reference_path=None):
    """Probe each independent finger DOF live, without a lower-limit teleport."""
    indices = sorted({int(index) for chain in fingertips.finger_chains or [] for index in chain})
    paths = list(fingertips.tip_link_paths)
    chains = list(fingertips.finger_chains or [])
    if len(chains) != len(paths) or len(set(paths)) != len(paths):
        raise GripperMappingError("FET028 mapping: incomplete independent branch-tip ownership")
    tip_by_index = {}
    for chain, path in zip(chains, paths, strict=True):
        for index in chain:
            if int(index) in tip_by_index:
                raise GripperMappingError("FET028 mapping: ambiguous independent leader ownership")
            tip_by_index[int(index)] = path
    center = np.asarray(center, dtype=np.float64)
    specs, diagnostics = [], []
    # The hand test frame uses +X for approach and -Z for the palm direction.
    async with GripperProbe(ctx, robot, stage, paths, indices, config, (1.0, 0.0, 0.0), reference_path) as probe:
        if probe.reference_initial is not None:
            reference_position, reference_orientation = probe.reference_initial
            center = _rotate(
                np.asarray([center - np.asarray(reference_position)]), _inverse_quaternion(reference_orientation)
            )[0]
        for index in indices:
            first, second = await probe.endpoints(index)
            movements = []
            for path in [tip_by_index[index]]:
                if path not in first[1] or path not in second[1]:
                    raise GripperMappingError("FET028 mapping: missing independent-finger tip geometry")
                before, after = first[1][path], second[1][path]
                displacement = (after - before) * probe.meters_per_unit
                if np.linalg.norm(displacement) <= 1e-6:
                    continue
                radial_change = float(np.linalg.norm(after - center) - np.linalg.norm(before - center))
                movements.append((path, displacement, radial_change * probe.meters_per_unit))
            if not movements:
                diagnostics.append((index, "unresolved", None, 0.0, []))
            else:
                _, displacement, radial_change = max(movements, key=lambda item: float(np.linalg.norm(item[1])))
                role, endpoint = classify(displacement, radial_change)
                if endpoint is None:
                    diagnostics.append((index, "unresolved", None, radial_change, displacement.tolist()))
                else:
                    lower, upper = float(probe.lowers[index]), float(probe.uppers[index])
                    closed = upper if endpoint == "upper" else lower
                    opened = lower if endpoint == "upper" else upper
                    if role != "closure":
                        # Positioning joints stay at their original command;
                        # endpoint observations do not authorize a pose retune.
                        opened = closed = probe.targets[index]
                    specs.append({"idx": index, "open": opened, "closed": closed, "name": robot.dof_names[index]})
                    diagnostics.append((index, role, endpoint, radial_change, displacement.tolist()))
            await probe.restore_pose(index)
    return specs, diagnostics
