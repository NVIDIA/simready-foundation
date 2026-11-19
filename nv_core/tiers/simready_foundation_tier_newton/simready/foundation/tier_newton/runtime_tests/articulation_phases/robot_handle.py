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
"""RobotHandle: thin wrapper over isaacsim.core.prims.SingleArticulation.

Exposes only the subset of methods phase functions use. Construction is cheap
(stores refs). initialize() MUST be called after ctx.scene.add_physics(...).play()
+ await ctx.settle(count=1).

Framework 2.0 deliberately does NOT construct isaacsim.core.api.World or
isaacsim.core.api.simulation_context.SimulationContext. SingleArticulation.initialize()
lazily creates the tensor view via omni.physics.tensors.create_simulation_view
once Newton is attached and stepping.
"""

import math
from numbers import Real

import numpy as np
from simready.foundation.tier_newton.runtime_tests.articulation_phases.motion_utils import (
    get_dof_property,
)
from simready.foundation.tier_newton.runtime_tests.articulation_phases.required_readback import (
    as_real_array,
)


def _to_host_array(raw):
    # type: (Any) -> Optional[np.ndarray]
    """Copy real numeric backend values without coercing malformed evidence."""
    if raw is None:
        return None
    try:
        value = raw.detach() if hasattr(raw, "detach") else raw
        value = value.cpu() if hasattr(value, "cpu") else value
        value = value.numpy() if hasattr(value, "numpy") else value
        array = as_real_array(value)
        if array.dtype.kind not in "iuf":
            return None
        return np.asarray(array, dtype=np.float64)
    except Exception:
        return None


def _to_dof_array(raw, dof_count):
    # type: (Any, int) -> np.ndarray
    """Coerce a (possibly broken) tensor read into a 1-D float array.

    Accepts a 1-D vector or one batched articulation row ``(1, dof_count)``.
    Returns a NaN-filled array of shape ``(dof_count,)`` for missing values,
    scalars, wrong lengths or other tensor shapes. This protects callers
    from invalidated views without erasing multiple-articulation identity.
    """
    if raw is None:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    arr = _to_host_array(raw)
    if arr is None:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if arr.ndim == 0 or arr.size == 0:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if arr.ndim == 2 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 1:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if dof_count and arr.shape[0] != int(dof_count):
        # Length mismatch — physics view returned a partial / stale frame;
        # treat as invalidated and return NaNs at the expected size.
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    return arr


def _discover_mjc_tendon_controls(stage, robot_prim_path):
    # type: (Any, str) -> List[dict]
    """Describe fixed-tendon actuators below an articulation root.

    The returned dictionaries contain only resolved USD data. Runtime handles
    use them to translate a requested joint angle into the native MuJoCo
    actuator control value without treating the tendon as an ordinary joint
    drive.
    """
    if stage is None or not robot_prim_path:
        return []
    try:
        from pxr import Usd

        root = stage.GetPrimAtPath(robot_prim_path)
        if not root or not root.IsValid():
            return []
        tendons = {}
        actuators = []
        for prim in Usd.PrimRange(root):
            if prim.GetTypeName() != "MjcTendon":
                continue
            path_rel = prim.GetRelationship("mjc:path")
            joint_paths = [str(path) for path in path_rel.GetTargets()] if path_rel else []
            coef_attr = prim.GetAttribute("mjc:path:coef")
            coefficients = list(coef_attr.Get() or []) if coef_attr else []
            if joint_paths:
                if len(joint_paths) != len(coefficients):
                    raise RuntimeError("Newton fixed-tendon joint paths and coefficients must have matching lengths")
                _finite_tendon_vector(coefficients, "coefficients")
                tendons[str(prim.GetPath())] = (joint_paths, [float(value) for value in coefficients])
        for prim in Usd.PrimRange(root):
            if prim.GetTypeName() != "MjcActuator":
                continue
            target_rel = prim.GetRelationship("mjc:target")
            targets = [str(path) for path in target_rel.GetTargets()] if target_rel else []
            if len(targets) != 1 or targets[0] not in tendons:
                continue
            gain_attr = prim.GetAttribute("mjc:gainPrm")
            bias_attr = prim.GetAttribute("mjc:biasPrm")
            gains = list(gain_attr.Get() or []) if gain_attr else []
            biases = list(bias_attr.Get() or []) if bias_attr else []
            if not gains or len(biases) < 2:
                continue
            _finite_tendon_vector(gains, "gains")
            _finite_tendon_vector(biases, "biases")
            if float(gains[0]) == 0.0 or float(biases[1]) >= 0.0:
                continue  # Not the affine position-control form supported here.
            minimum_attr = prim.GetAttribute("mjc:ctrlRange:min")
            maximum_attr = prim.GetAttribute("mjc:ctrlRange:max")
            joint_paths, coefficients = tendons[targets[0]]
            control_joint_names = []
            control_joint_paths = []
            for joint_path in joint_paths:
                joint_prim = stage.GetPrimAtPath(joint_path)
                schemas = list(joint_prim.GetAppliedSchemas()) if joint_prim and joint_prim.IsValid() else []
                mimic_rel = (
                    joint_prim.GetRelationship("newton:mimicJoint") if joint_prim and joint_prim.IsValid() else None
                )
                if "NewtonMimicAPI" not in schemas and not (mimic_rel and mimic_rel.GetTargets()):
                    control_joint_names.append(joint_path.rsplit("/", 1)[-1])
                    control_joint_paths.append(joint_path)
            if not control_joint_names:
                control_joint_names = [path.rsplit("/", 1)[-1] for path in joint_paths]
                control_joint_paths = list(joint_paths)
            control_path = control_joint_paths[0]
            joint_target_offsets = []
            joint_target_scales = []
            valid_coupling = True
            for joint_path in joint_paths:
                if joint_path == control_path:
                    joint_target_offsets.append(0.0)
                    joint_target_scales.append(1.0)
                    continue
                joint_prim = stage.GetPrimAtPath(joint_path)
                mimic_rel = (
                    joint_prim.GetRelationship("newton:mimicJoint") if joint_prim and joint_prim.IsValid() else None
                )
                mimic_targets = [str(path) for path in mimic_rel.GetTargets()] if mimic_rel else []
                if mimic_targets != [control_path]:
                    valid_coupling = False
                    break
                coef0_attr = joint_prim.GetAttribute("newton:mimicCoef0")
                coef1_attr = joint_prim.GetAttribute("newton:mimicCoef1")
                coef0 = coef0_attr.Get() if coef0_attr else None
                coef1 = coef1_attr.Get() if coef1_attr else None
                _finite_tendon_vector([coef0 if coef0 is not None else 0.0], "mimic offset")
                _finite_tendon_vector([coef1 if coef1 is not None else 1.0], "mimic scale")
                joint_target_offsets.append(float(coef0) if coef0 is not None else 0.0)
                joint_target_scales.append(float(coef1) if coef1 is not None else 1.0)
            if not valid_coupling:
                continue
            control = {
                "actuator_path": str(prim.GetPath()),
                "target_path": targets[0],
                "joint_paths": joint_paths,
                "joint_names": [path.rsplit("/", 1)[-1] for path in joint_paths],
                "control_joint_names": control_joint_names,
                "coefficients": coefficients,
                "joint_target_offsets": joint_target_offsets,
                "joint_target_scales": joint_target_scales,
                "gain": float(gains[0]),
                "position_bias": float(biases[1]),
                "ctrl_min": (minimum_attr.Get() if minimum_attr and minimum_attr.Get() is not None else -np.inf),
                "ctrl_max": (maximum_attr.Get() if maximum_attr and maximum_attr.Get() is not None else np.inf),
            }
            _validated_tendon_parameters(control)
            actuators.append(control)
        return actuators
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError("Required Newton fixed-tendon authoring could not be inspected") from error


def _finite_tendon_vector(values, label, *, allow_single_row=False):
    """Require finite authored affine parameters without string/bool coercion."""
    try:
        array = as_real_array(values)
        if allow_single_row and array.ndim == 2 and array.shape[0] == 1:
            array = array[0]
        if array.ndim != 1 or not array.size or not np.all(np.isfinite(array)):
            raise ValueError("requires a nonempty finite vector")
        return np.asarray(array, dtype=np.float64)
    except Exception as error:
        raise RuntimeError("Invalid Newton fixed-tendon " + label) from error


def _validated_tendon_parameters(actuator):
    """Validate the complete conversion before any native control is changed."""
    try:
        coefficients = _finite_tendon_vector(actuator["coefficients"], "coefficients")
        offsets = _finite_tendon_vector(actuator.get("joint_target_offsets", [0.0] * len(coefficients)), "offsets")
        scales = _finite_tendon_vector(actuator.get("joint_target_scales", [1.0] * len(coefficients)), "scales")
        if len(offsets) != len(coefficients) or len(scales) != len(coefficients):
            raise ValueError("affine vector lengths must match")
        gain, bias = actuator["gain"], actuator["position_bias"]
        if any(
            isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) for value in (gain, bias)
        ):
            raise ValueError("gain and position bias must be finite real values")
        if gain == 0 or bias >= 0:
            raise ValueError("position control requires nonzero gain and negative position bias")
        lower, upper = actuator["ctrl_min"], actuator["ctrl_max"]
        if any(isinstance(value, bool) or not isinstance(value, Real) or math.isnan(value) for value in (lower, upper)):
            raise ValueError("control limits must be real and not NaN")
        if lower == math.inf or upper == -math.inf or lower > upper:
            raise ValueError("control range must be ordered; only outward unbounded sentinels are allowed")
        return coefficients, offsets, scales, float(gain), float(bias), float(lower), float(upper)
    except Exception as error:
        raise RuntimeError("Invalid Newton fixed-tendon position-control parameters") from error


def _tendon_position_to_ctrl(actuator, joint_position):
    # type: (dict, float) -> float
    """Convert a common coupled-joint target to an affine tendon control."""
    coefficients, offsets, scales, gain, bias, lower, upper = _validated_tendon_parameters(actuator)
    try:
        if (
            isinstance(joint_position, bool)
            or not isinstance(joint_position, Real)
            or not math.isfinite(joint_position)
        ):
            raise ValueError("joint target must be finite and real")
        desired_length = sum(
            float(coefficient) * (float(offset) + float(scale) * float(joint_position))
            for coefficient, offset, scale in zip(coefficients, offsets, scales, strict=True)
        )
        value = -bias * desired_length / gain
        if not math.isfinite(desired_length) or not math.isfinite(value):
            raise ValueError("derived tendon target is nonfinite")
        return min(max(value, lower), upper)
    except (TypeError, ValueError, OverflowError) as error:
        raise RuntimeError("Invalid Newton fixed-tendon requested control") from error


def _has_native_newton_actuators(stage, robot_prim_path):
    # type: (Any, str) -> bool
    """Return whether the articulation uses a native Newton control contract."""
    if stage is None or not robot_prim_path:
        return False
    try:
        from pxr import Usd

        root = stage.GetPrimAtPath(robot_prim_path)
        if not root or not root.IsValid():
            return False
        if any(prim.GetTypeName() == "NewtonActuator" for prim in Usd.PrimRange(root)):
            return True
        return bool(_discover_mjc_tendon_controls(stage, robot_prim_path))
    except Exception:
        return False


def _newton_actuator_prims(stage, root_paths):
    """Return unique NewtonActuator prims below one or more search roots."""
    if stage is None:
        return []
    try:
        from pxr import Usd

        paths = [root_paths] if isinstance(root_paths, str) else list(root_paths or ())
        result = []
        seen = set()
        for root_path in paths:
            root = stage.GetPrimAtPath(str(root_path))
            if not root or not root.IsValid():
                continue
            for prim in Usd.PrimRange(root):
                if prim.GetTypeName() != "NewtonActuator":
                    continue
                prim_path = str(prim.GetPath())
                if prim_path not in seen:
                    seen.add(prim_path)
                    result.append(prim)
        return result
    except Exception:
        return []


def _native_newton_actuator_target_names(stage, robot_prim_path):
    """Return DOF names explicitly targeted by NewtonActuator prims."""
    names = set()
    for prim in _newton_actuator_prims(stage, robot_prim_path):
        rel = prim.GetRelationship("newton:targets")
        for target in rel.GetTargets() if rel else ():
            names.add(str(target).rsplit("/", 1)[-1])
    return names


class RobotHandle:
    """Wrapper over SingleArticulation exposing phase-facing joint API."""

    def __init__(
        self,
        stage,
        robot_prim_path,
        asset_prim,
        robot_type,
        *,
        setup_world_pin=None,
    ):
        # type: (Any, str, Any, RobotType) -> None
        self._stage = stage
        self._robot_prim_path = str(robot_prim_path)
        self._asset_prim = asset_prim
        self._root_prim = None
        self._robot_type = robot_type
        self._articulation = None  # type: Optional[Any]
        self._newton_actuators = None  # type: Optional[Any]
        self._newton_actuator_target_names = set()
        self._mjc_tendon_controls = []  # type: List[dict]
        self._initialized = False
        self._name = "robot_%d" % id(self)  # unique within this Kit session
        self._physics_dt = 1.0 / 240.0
        self._is_newton = True
        self._newton_actuator_search_roots = (self._robot_prim_path,)
        self._setup_world_pin = setup_world_pin

    # -- Properties ----------------------------------------------------

    @property
    def prim_path(self):
        # type: () -> str
        return self._robot_prim_path

    @property
    def robot_type(self):
        # type: () -> RobotType
        return self._robot_type

    @property
    def asset_prim(self):
        # type: () -> Any
        return self._asset_prim

    @property
    def root_prim(self):
        # type: () -> Any
        return self._root_prim

    @property
    def articulation(self):
        # type: () -> Any
        """Escape hatch to the underlying SingleArticulation."""
        return self._articulation

    @property
    def dof_count(self):
        # type: () -> int
        names = getattr(self._articulation, "dof_names", None)
        if names is None:
            return 0
        return len(names)

    @property
    def dof_names(self):
        # type: () -> List[str]
        names = getattr(self._articulation, "dof_names", None)
        if names is None:
            return []
        return [str(n) for n in names]

    # -- Initialization (Task 7 decision A) ----------------------------

    async def initialize_newton(self, ctx):
        # type: (Any) -> None
        """Initialize a Newton articulation after its USD drives are compiled.

        Newton owns a GPU-backed tensor view and does not use the PhysX
        ``World.reset_async`` initialization path. In particular, rewriting
        controller gains after play can mix CPU index buffers with CUDA gain
        buffers. The caller compiles the asset's authored drives before this
        method creates the read/write articulation view; no gains are modified.
        """
        # Newton creates a GPU physics pipeline.  Select Torch before either
        # wrapper below captures SimulationManager's backend utilities.
        # Otherwise SingleArticulation is constructed with NumPy helpers and
        # Newton later auto-switches the physics view to Torch, causing the
        # first state write to pass a NumPy array into a CUDA API.
        from isaacsim.core.simulation_manager import SimulationManager  # type: ignore

        SimulationManager.set_backend("torch")
        try:
            from isaacsim.core.prims import SingleArticulation  # type: ignore
        except Exception:
            from isaacsim.core.prims.single_articulation import (  # type: ignore
                SingleArticulation,
            )

        self._is_newton = True
        previous_manager = self._newton_actuators
        if previous_manager is not None:
            try:
                previous_manager.close()
            except Exception:
                pass
            self._newton_actuators = None

        actuator_prims = _newton_actuator_prims(
            self._stage,
            self._newton_actuator_search_roots,
        )
        has_native_control = bool(actuator_prims) or any(
            _discover_mjc_tendon_controls(self._stage, path) for path in self._newton_actuator_search_roots
        )
        if has_native_control:
            ctx.step("RobotHandle.initialize_newton: enabling native Newton actuator bridge")
            try:
                from isaacsim.core.experimental.actuators import (  # type: ignore
                    ArticulationActuators,
                )

                self._newton_actuators = ArticulationActuators(self._robot_prim_path, auto_step_pre_physics=True)
                self._newton_actuator_target_names = _native_newton_actuator_target_names(
                    self._stage, self._newton_actuator_search_roots
                )
                self._mjc_tendon_controls = _discover_mjc_tendon_controls(
                    self._stage,
                    self._robot_prim_path,
                )
                if not self._mjc_tendon_controls and self._asset_prim is not None:
                    asset_path = str(self._asset_prim.GetPath())
                    if asset_path != self._robot_prim_path:
                        self._mjc_tendon_controls = _discover_mjc_tendon_controls(
                            self._stage,
                            asset_path,
                        )
                ctx.step(
                    "RobotHandle.initialize_newton: native actuator bridge owns %d DOF(s); "
                    "discovered %d fixed-tendon control(s)"
                    % (
                        len(getattr(self._newton_actuators, "_actuators", ())),
                        len(self._mjc_tendon_controls),
                    )
                )
            except Exception as exc:
                raise RuntimeError(
                    "Asset authors NewtonActuator control, but Isaac Sim could not "
                    f"initialize ArticulationActuators for {self._robot_prim_path}: {exc}"
                ) from exc

        ctx.step("RobotHandle.initialize_newton: constructing SingleArticulation(name=%s)" % self._name)
        articulation = SingleArticulation(
            prim_path=self._robot_prim_path,
            name=self._name,
        )
        articulation.initialize()
        self._articulation = articulation
        if self._stage is not None:
            self._root_prim = self._stage.GetPrimAtPath(self._robot_prim_path)
        self._initialized = True
        ctx.step("RobotHandle.initialize_newton: ready; dof_names=%r" % (getattr(articulation, "dof_names", None),))

    def teardown(self):
        """Release the Newton actuator bridge and tensor-view references.

        Idempotent. No PhysX World singleton is constructed or reset.
        """
        manager = getattr(self, "_newton_actuators", None)
        if manager is not None:
            try:
                manager.close()
            except Exception:
                pass
        self._newton_actuators = None
        self._mjc_tendon_controls = []
        self._articulation = None
        self._root_prim = None
        self._initialized = False

    # -- State reads ---------------------------------------------------

    def get_joint_positions(self):
        # type: () -> np.ndarray
        """Return joint positions as a 1-D array of shape (dof_count,).

        When the underlying physics view is invalidated (e.g. asset deletion
        mid-test, world reset without re-init), Isaac Sim's
        ``Articulation.get_joint_positions`` returns ``None``, which
        ``np.array`` converts to a 0-D array. Indexing such an array with
        ``arr[i]`` raises ``IndexError: too many indices for array``. To
        keep callers from blowing up on a single bad frame, we coerce
        None / 0-D / wrong-length results into a NaN-filled 1-D array of
        the expected DOF count. Callers that need to detect invalidation
        can ``np.isnan(arr).any()``.
        """
        if self._newton_actuators is not None:
            values = self._newton_actuators.articulation.get_dof_positions()
            return self._native_values_in_legacy_order(values)
        return _to_dof_array(self._articulation.get_joint_positions(), self.dof_count)

    def get_joint_velocities(self):
        # type: () -> np.ndarray
        """Return joint velocities as a 1-D array of shape (dof_count,).
        See ``get_joint_positions`` for the invalidation-handling rationale.
        """
        if self._newton_actuators is not None:
            values = self._newton_actuators.articulation.get_dof_velocities()
            return self._native_values_in_legacy_order(values)
        return _to_dof_array(self._articulation.get_joint_velocities(), self.dof_count)

    def get_joint_position_targets(self):
        # type: () -> np.ndarray
        """Return the controller target buffer used by the active runtime."""
        if self._newton_actuators is not None:
            values = self._newton_actuators.articulation.get_dof_position_targets()
            return self._native_values_in_legacy_order(values)
        getter = getattr(self._articulation, "get_joint_position_targets", None)
        if callable(getter):
            try:
                return _to_dof_array(getter(), self.dof_count)
            except Exception:
                return np.full(self.dof_count, np.nan, dtype=np.float64)
        unavailable = np.full(self.dof_count, np.nan, dtype=np.float64)
        try:
            applied_getter = getattr(self._articulation, "get_applied_action", None)
            action = applied_getter() if callable(applied_getter) else None
            positions = _to_host_array(getattr(action, "joint_positions", None))
            if positions is None or positions.shape != (self.dof_count,):
                return unavailable
            raw_indices = getattr(action, "joint_indices", None)
            indices = _to_host_array(raw_indices)
            if raw_indices is not None and indices is None:
                return unavailable
            if indices is not None:
                if (
                    indices.shape != (self.dof_count,)
                    or not np.isfinite(indices).all()
                    or not np.equal(indices, indices.astype(np.int64)).all()
                    or set(indices.astype(np.int64).tolist()) != set(range(self.dof_count))
                ):
                    return unavailable
                ordered = unavailable.copy()
                ordered[indices.astype(np.int64)] = positions
                positions = ordered
            return np.asarray(positions, dtype=np.float64).copy()
        except Exception:
            return unavailable

    def get_world_pose(self):
        # type: () -> Tuple[np.ndarray, np.ndarray]
        """Return root position and orientation as host NumPy arrays.

        Newton GPU pipelines return Torch CUDA tensors from the underlying
        ``SingleArticulation``.  Phase code must not call ``np.asarray`` on
        those values directly.
        """
        position, orientation = self._articulation.get_world_pose()
        host_position = _to_host_array(position)
        host_orientation = _to_host_array(orientation)
        if host_position is None:
            host_position = np.full(3, np.nan, dtype=np.float64)
        if host_orientation is None:
            host_orientation = np.full(4, np.nan, dtype=np.float64)
        return host_position.reshape(3), host_orientation.reshape(4)

    def get_applied_joint_efforts(self):
        # type: () -> Optional[np.ndarray]
        """Return native effort evidence, never a synthetic zero readback.

        An absent native getter returns None. Missing/malformed getter results
        use the same NaN-marked numeric/shape adapter as other DOF readbacks;
        actual numeric zeros remain valid evidence. Native getter errors and
        cancellation propagate so required consumers must handle them honestly.
        """
        if self._newton_actuators is not None:
            efforts = self._newton_actuators.articulation.get_dof_efforts()
            return self._native_values_in_legacy_order(efforts)
        fn = getattr(self._articulation, "get_applied_joint_efforts", None)
        if fn is None:
            return None
        return _to_dof_array(fn(), self.dof_count)

    # -- Commands ------------------------------------------------------

    def _apply_action(self, **kwargs):
        # type: (**Any) -> None
        """Dispatch an ArticulationAction via SingleArticulation.apply_action.

        Isaac Sim 5.x SingleArticulation does not expose
        ``set_joint_position_targets`` / ``set_joint_velocity_targets``
        directly -- the PD drive is set through
        ``articulation.apply_action(ArticulationAction(joint_positions=...,
        joint_velocities=...))``. This matches the v1 framework pattern in
        ``test_definitions/isaac_sim/shared_phases/shared_utils.py::apply_joint_positions``.
        """
        if self._newton_actuators is not None:
            self._apply_native_newton_action(**kwargs)
            return

        # Isaac Sim 6.0's Newton SingleArticulation accepts full target arrays
        # but silently ignores sparse position actions carrying joint_indices.
        # FET022 already uses the working full-array form; normalize all other
        # phases at this backend boundary so callers remain engine-neutral.
        indices = kwargs.get("joint_indices")
        sparse_positions = kwargs.get("joint_positions")
        if indices is not None and sparse_positions is not None:
            host_indices = np.asarray(indices, dtype=np.int32).reshape(-1)
            host_positions = np.asarray(sparse_positions, dtype=np.float64).reshape(-1)
            if host_indices.size != host_positions.size:
                raise ValueError("joint_indices and joint_positions must have matching lengths")
            full_positions = self.get_joint_position_targets()
            if full_positions is None or len(full_positions) != self.dof_count:
                full_positions = np.full(self.dof_count, np.nan, dtype=np.float64)
            full_positions = np.asarray(full_positions, dtype=np.float64).reshape(self.dof_count).copy()
            # A newly initialized Newton tensor view commonly exposes a
            # correctly-sized target buffer containing NaNs.  Preserve valid
            # controller targets, but seed every invalid entry from measured
            # state before submitting the full array.  One NaN is enough for
            # Newton to ignore the otherwise valid sparse update.
            invalid = ~np.isfinite(full_positions)
            if bool(np.any(invalid)):
                current_positions = np.asarray(self.get_joint_positions(), dtype=np.float64).reshape(self.dof_count)
                full_positions[invalid] = current_positions[invalid]
            if not bool(np.all(np.isfinite(full_positions))):
                raise RuntimeError("Newton joint targets and positions contain non-finite values")
            full_positions[host_indices] = host_positions
            # Validate after inserting the sparse request and before backend
            # float32 conversion; a valid retained buffer does not qualify a
            # newly inserted NaN or an overflowing finite request.
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                native_targets = full_positions.astype(np.float32)
            if not np.isfinite(native_targets).all():
                raise ValueError("Newton joint targets are outside the finite native float32 range")
            kwargs["joint_positions"] = full_positions
            kwargs["joint_indices"] = None

        from isaacsim.core.utils.types import ArticulationAction  # type: ignore

        backend_utils = getattr(self._articulation, "_backend_utils", None)
        device = getattr(self._articulation, "_device", None)
        if backend_utils is not None:
            converted = {}
            for key, value in kwargs.items():
                if value is None:
                    converted[key] = None
                    continue
                dtype = "int32" if key == "joint_indices" else "float32"
                converted[key] = backend_utils.convert(value, device=device, dtype=dtype)
            kwargs = converted
        self._articulation.apply_action(ArticulationAction(**kwargs))

    def _apply_native_newton_action(self, **kwargs):
        # type: (**Any) -> None
        """Write control targets through Isaac's native Newton interface.

        ``ArticulationActuators`` reads targets from its experimental
        ``Articulation`` wrapper. Sending an ``ArticulationAction`` only to the
        legacy ``SingleArticulation`` wrapper may update a different controller
        buffer, leaving the native actuator at its prior target.
        """
        articulation = self._newton_actuators.articulation
        indices = kwargs.get("joint_indices")
        legacy_indices = (
            np.arange(self.dof_count, dtype=np.int32)
            if indices is None
            else np.asarray(indices, dtype=np.int32).reshape(-1)
        )
        pairs = self._legacy_native_index_pairs(legacy_indices)
        native_target_names = set(getattr(self, "_newton_actuator_target_names", set()) or ())
        # Older mocked/native implementations do not expose target metadata;
        # preserve their all-native behavior.  In a real mixed articulation,
        # route only explicitly actuator-owned DOFs through the experimental
        # bridge and leave standard PhysicsDriveAPI joints on the legacy view.
        native_pairs = (
            [pair for pair in pairs if pair[2] < len(legacy_indices) and self.dof_names[pair[0]] in native_target_names]
            if native_target_names
            else list(pairs)
        )
        standard_pairs = [pair for pair in pairs if pair not in native_pairs]

        position_values = kwargs.get("joint_positions")
        prepared_tendon = None
        if position_values is not None and getattr(self, "_mjc_tendon_controls", None):
            # Resolve mappings, actual buffer representability and detached
            # updates before staging ANY independent joint or tendon target.
            prepared_tendon = self._prepare_mjc_tendon_position_targets(position_values, legacy_indices)
        if position_values is not None and standard_pairs:
            requested = np.asarray(position_values, dtype=np.float32).reshape(-1)
            # Preserve targets already staged for the other controller family.
            # In a mixed Newton articulation the test-owned carrier rail uses a
            # native NewtonActuator while the asset fingers use standard USD
            # drives.  Seeding this vector entirely from measured positions
            # resets the rail target every time a finger command is submitted.
            full = np.asarray(self.get_joint_position_targets(), dtype=np.float32).reshape(self.dof_count).copy()
            invalid = ~np.isfinite(full)
            if bool(np.any(invalid)):
                measured = np.asarray(self.get_joint_positions(), dtype=np.float32).reshape(self.dof_count)
                full[invalid] = measured[invalid]
            for legacy_index, _native_index, selection_offset in standard_pairs:
                full[legacy_index] = requested[legacy_index if indices is None else selection_offset]
            from isaacsim.core.utils.types import ArticulationAction  # type: ignore

            backend_utils = getattr(self._articulation, "_backend_utils", None)
            device = getattr(self._articulation, "_device", None)
            converted = full
            if backend_utils is not None:
                converted = backend_utils.convert(full, device=device, dtype="float32")
            # Isaac Newton ignores sparse legacy actions.  Submit a complete
            # finite vector; the native actuator callback overwrites its owned
            # DOFs before the next physics step.
            self._articulation.apply_action(ArticulationAction(joint_positions=converted))
        calls = (
            ("joint_positions", "set_dof_position_targets"),
            ("joint_velocities", "set_dof_velocity_targets"),
            ("joint_efforts", "set_dof_efforts"),
        )
        for value_key, method_name in calls:
            values = kwargs.get(value_key)
            if values is None:
                continue
            method = getattr(articulation, method_name)
            selected_pairs = native_pairs if value_key == "joint_positions" else pairs
            if not selected_pairs:
                continue
            value_array = np.asarray(values, dtype=np.float32).reshape(-1)
            if indices is None:
                reordered = np.zeros(len(self._native_dof_names()), dtype=np.float32)
                for legacy_index, native_index, _selection_offset in selected_pairs:
                    reordered[native_index] = value_array[legacy_index]
                value_array = reordered
                call_kwargs = {}
            else:
                value_array = np.asarray(
                    [value_array[selection_offset] for _legacy, _native, selection_offset in selected_pairs],
                    dtype=np.float32,
                )
                call_kwargs = {
                    "dof_indices": np.asarray(
                        [native for _legacy, native, _selection_offset in selected_pairs],
                        dtype=np.int32,
                    )
                }
            method(value_array, **call_kwargs)
        position_values = kwargs.get("joint_positions")
        # Stage every target before the next simulation step.  The actuator
        # manager's pre-physics callback advances all actuator controllers
        # exactly once per physics timestep.  Calling ``step_actuators`` here
        # would advance every controller once per *command*. A phase submits
        # independent carrier and finger commands in the same frame, so manual
        # stepping here would update both PID states twice and can destabilize
        # an otherwise valid Newton gripper.
        if prepared_tendon is not None:
            self._commit_mjc_tendon_position_targets(prepared_tendon)

    def _requested_mjc_tendon_controls(self, position_values, legacy_indices):
        """Return validated requested controls without accessing native buffers."""
        values = _finite_tendon_vector(position_values, "requested joint targets", allow_single_row=True)
        with np.errstate(over="ignore", invalid="ignore"):
            native_values = values.astype(np.float32)
        if not np.all(np.isfinite(native_values)):
            raise RuntimeError("Newton fixed-tendon joint targets cannot be represented by native float32 controls")
        if len(values) != len(legacy_indices):
            raise RuntimeError("Newton fixed-tendon target indices and values must have matching lengths")
        selected = {
            self.dof_names[int(index)]: float(value) for index, value in zip(legacy_indices, values, strict=True)
        }
        controls = []
        for actuator in self._mjc_tendon_controls:
            _validated_tendon_parameters(actuator)
            requested = [selected[name] for name in actuator["control_joint_names"] if name in selected]
            if requested:
                controls.append((actuator, _tendon_position_to_ctrl(actuator, requested[0])))
        return controls

    def _apply_mjc_tendon_position_targets(self, position_values, legacy_indices):
        # type: (Any, np.ndarray) -> None
        """Translate per-joint targets into fixed-tendon actuator controls."""
        prepared = self._prepare_mjc_tendon_position_targets(position_values, legacy_indices)
        if prepared is not None:
            self._commit_mjc_tendon_position_targets(prepared)

    def _prepare_mjc_tendon_position_targets(self, position_values, legacy_indices):
        """Read/validate and allocate detached updates without staging controls."""
        requested_controls = self._requested_mjc_tendon_controls(position_values, legacy_indices)
        if not requested_controls:
            return
        experimental_view = getattr(self._newton_actuators.articulation, "_physics_articulation_view", None)
        legacy_articulation_view = getattr(self._articulation, "_articulation_view", None)
        legacy_physics_view = getattr(legacy_articulation_view, "_physics_view", None)
        backend = None
        for start in (experimental_view, legacy_physics_view):
            candidate = start
            visited = set()
            while candidate is not None and id(candidate) not in visited:
                visited.add(id(candidate))
                if hasattr(candidate, "model") and hasattr(candidate, "newton_stage"):
                    backend = candidate
                    break
                candidate = getattr(candidate, "_backend", None)
            if backend is not None:
                break
        try:
            from isaacsim.physics.newton import acquire_stage  # type: ignore

            newton_stage = acquire_stage()
        except Exception:
            newton_stage = None
        if newton_stage is None:
            newton_stage = getattr(backend, "newton_stage", None)
        model = getattr(newton_stage, "model", None)
        mujoco_model = getattr(model, "mujoco", None)
        control = getattr(getattr(newton_stage, "control", None), "mujoco", None)
        ctrl = getattr(control, "ctrl", None)
        labels = getattr(mujoco_model, "actuator_target_label", None)
        if ctrl is None or not isinstance(labels, list):

            def _diagnostic_attrs(value):
                return [
                    name
                    for name in dir(value)
                    if any(token in name.lower() for token in ("backend", "physics", "view", "stage", "model"))
                ]

            raise RuntimeError(
                "Newton fixed-tendon actuator controls are unavailable from the physics tensor view "
                f"(experimental_view={type(experimental_view).__name__} attrs={_diagnostic_attrs(experimental_view)}, legacy_physics_view={type(legacy_physics_view).__name__} attrs={_diagnostic_attrs(legacy_physics_view)}, backend={type(backend).__name__}, "
                f"labels_type={type(labels).__name__}, ctrl={type(ctrl).__name__})"
            )
        values = np.asarray(ctrl.numpy()).copy()
        if values.dtype.kind != "f" or not values.size or not np.all(np.isfinite(values)):
            raise RuntimeError("Required Newton tendon control buffer is invalid")
        actuator_updates = {}
        for actuator, actuator_ctrl in requested_controls:
            # A coupled gripper command names one or both tendon joints. The
            # desired tendon length uses the same target for every coupled DOF.
            try:
                if labels.count(actuator["target_path"]) != 1:
                    raise ValueError("tendon target must resolve exactly once")
                actuator_index = labels.index(actuator["target_path"])
            except ValueError as exc:
                raise RuntimeError(
                    "Newton did not compile tendon target {} for actuator {}".format(
                        actuator["target_path"], actuator["actuator_path"]
                    )
                ) from exc
            if actuator_index >= values.size:
                raise RuntimeError("Newton tendon target exceeds the native control buffer")
            actuator_updates[actuator_index] = actuator_ctrl
        if actuator_updates:
            import warp as wp  # type: ignore

            # Root-pose updates can leave the public
            # stage-control buffer and the already-compiled MuJoCo solver data
            # out of sync. Keep the solver's live ctrl array coherent with the
            # same actuator-indexed values. On ordinary articulation runs this
            # is idempotent with Newton's normal stage->solver synchronization.
            solver = getattr(newton_stage, "solver", None)
            solver_ctrl = getattr(getattr(solver, "mjw_data", None), "ctrl", None)
            solver_values = None
            if solver_ctrl is not None:
                solver_values = np.asarray(solver_ctrl.numpy()).copy()
                if (
                    solver_values.dtype.kind != "f"
                    or solver_values.ndim < 1
                    or not solver_values.size
                    or not np.all(np.isfinite(solver_values))
                ):
                    raise RuntimeError("Required Newton solver tendon control buffer is invalid")
                solver_flat = solver_values.reshape(-1, solver_values.shape[-1])
                if max(actuator_updates) >= solver_flat.shape[-1]:
                    raise RuntimeError("Newton tendon target exceeds the solver control buffer")
                with np.errstate(over="ignore", invalid="ignore"):
                    for actuator_index, control_value in actuator_updates.items():
                        solver_flat[:, actuator_index] = control_value
                if not np.all(np.isfinite(solver_values)):
                    raise RuntimeError("Newton tendon control cannot be represented by the solver buffer")
            with np.errstate(over="ignore", invalid="ignore"):
                for actuator_index, control_value in actuator_updates.items():
                    values.reshape(-1)[actuator_index] = control_value
            if not np.all(np.isfinite(values)):
                raise RuntimeError("Newton tendon control cannot be represented by the native buffer")
            native_update = wp.array(values, dtype=ctrl.dtype, device=ctrl.device)
            solver_update = (
                wp.array(solver_values, dtype=solver_ctrl.dtype, device=solver_ctrl.device)
                if solver_values is not None
                else None
            )
            return ctrl, native_update, solver_ctrl, solver_update
        return None

    def _commit_mjc_tendon_position_targets(self, prepared):
        """Stage the already qualified copies in the existing command order."""
        import warp as wp  # type: ignore

        ctrl, native_update, solver_ctrl, solver_update = prepared
        wp.copy(ctrl, native_update)
        if solver_update is not None:
            wp.copy(solver_ctrl, solver_update)

    def _native_dof_names(self):
        paths = list(getattr(self._newton_actuators.articulation, "dof_paths", ()) or ())
        if paths and isinstance(paths[0], (list, tuple)):
            paths = list(paths[0])
        return [str(path).rsplit("/", 1)[-1] for path in paths]

    def _legacy_native_index_pairs(self, legacy_indices):
        """Map legacy DOFs onto the native Newton articulation.

        Excluded loop-closure joints are intentionally absent from Newton's
        articulation DOF list even though ``SingleArticulation`` can still
        enumerate their authored joint-state schemas.  They are constraints,
        not controllable DOFs, so omit them instead of rejecting the asset.
        """
        legacy_names = list(self.dof_names)
        native_names = self._native_dof_names()
        mapped = []
        for selection_offset, index in enumerate(legacy_indices):
            name = legacy_names[int(index)]
            if name in native_names:
                mapped.append((int(index), native_names.index(name), selection_offset))
        return mapped

    def _legacy_indices_to_native(self, legacy_indices):
        pairs = self._legacy_native_index_pairs(legacy_indices)
        return np.asarray([native for _legacy, native, _offset in pairs], dtype=np.int32)

    def _native_values_in_legacy_order(self, values):
        native = _to_dof_array(values, len(self._native_dof_names()))
        legacy = np.full(self.dof_count, np.nan, dtype=np.float64)
        for legacy_index, native_index, _selection_offset in self._legacy_native_index_pairs(
            np.arange(self.dof_count, dtype=np.int32)
        ):
            legacy[legacy_index] = native[native_index]
        return legacy

    def set_physics_timestep(self, timestep: float):
        # type: (float) -> None
        """Configure the timestep used for explicit native actuator steps."""
        value = float(timestep)
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError("physics timestep must be a positive finite value")
        self._physics_dt = value

    def apply_action(self, action):
        # type: (Any) -> None
        """Apply an Isaac articulation action through backend conversion.

        Test phases construct actions from host NumPy arrays.  Newton uses a
        Torch/CUDA articulation view, so forwarding those objects directly to
        ``SingleArticulation`` fails while resolving NumPy joint indices.  Keep
        that backend boundary centralized in ``RobotHandle``.
        """
        self._apply_action(
            joint_positions=getattr(action, "joint_positions", None),
            joint_velocities=getattr(action, "joint_velocities", None),
            joint_efforts=getattr(action, "joint_efforts", None),
            joint_indices=getattr(action, "joint_indices", None),
        )

    def _excluded_dofs_are_unactuated(self, excluded_indices):
        stage = getattr(self, "_stage", None)
        root_path = getattr(self, "_robot_prim_path", None)
        names = list(self.dof_names)
        if stage is None or not root_path or not names:
            return False
        from .joint_identity import joint_for_native_name, selected_joint_prims
        from .passive_joints import _actuator_target_paths, _joint_is_passive

        asset_prim = getattr(self, "_asset_prim", None)
        joints = selected_joint_prims(stage, root_path, names, asset_prim)
        if not joints:
            return False
        scan_path = str(asset_prim.GetPath()) if asset_prim is not None else root_path
        actuator_targets = _actuator_target_paths(stage, scan_path)
        root_prim = stage.GetPrimAtPath(root_path)
        mobility_attr = root_prim.GetAttribute("newton:jointsAddMobility") if root_prim else None
        newton_adds_mobility = bool(mobility_attr.Get()) if mobility_attr else False
        for idx in excluded_indices:
            if not 0 <= int(idx) < len(names):
                return False
            joint = joint_for_native_name(joints, names[int(idx)])
            if joint is None or not _joint_is_passive(joint, actuator_targets, newton_adds_mobility):
                return False
        return True

    def require_indexed_joint_control(self, *, indices=None, excluded=None):
        """Verify that sparse control does not command active drives on excluded DOFs."""
        if not (getattr(self, "_is_newton", False) or getattr(self, "_newton_actuators", None) is not None):
            return
        dof_count = self.dof_count
        if excluded is not None:
            excluded_set = {int(i) for i in excluded}
        elif indices is not None:
            selected_set = {int(i) for i in indices}
            excluded_set = {i for i in range(dof_count) if i not in selected_set}
        else:
            excluded_set = set()
        if dof_count > 0 and not excluded_set:
            return

        if getattr(self, "_newton_actuators", None) is not None:
            native_target_names = set(getattr(self, "_newton_actuator_target_names", set()) or ())
            names = list(self.dof_names)
            if native_target_names and names and excluded_set:
                selected_indices = [i for i in range(len(names)) if i not in excluded_set]
                if (
                    selected_indices
                    and all(names[i] in native_target_names for i in selected_indices)
                    and all(names[i] not in native_target_names for i in excluded_set if 0 <= i < len(names))
                    and self._excluded_dofs_are_unactuated(excluded_set)
                ):
                    return
            raise RuntimeError(
                "Articulation runtime error: indexed control excluding coupled DOFs is not qualified "
                "for this Newton adapter; no unsafe full-vector fallback was issued"
            )

        articulation = getattr(self, "_articulation", None)
        has_target_readback = callable(getattr(articulation, "get_joint_position_targets", None)) or callable(
            getattr(articulation, "get_applied_action", None)
        )
        if has_target_readback and excluded_set and self._excluded_dofs_are_unactuated(excluded_set):
            return
        raise RuntimeError(
            "Articulation runtime error: indexed control excluding coupled DOFs is not qualified "
            "for this Newton adapter; no unsafe full-vector fallback was issued"
        )

    def set_joint_position_targets_indexed(self, values, indices):
        from ._independent_dofs import selected_dof_values

        values, indices = selected_dof_values(values, indices, self.dof_count)
        self.require_indexed_joint_control(indices=indices)
        self._apply_action(joint_positions=values, joint_indices=indices)

    def set_joint_positions_indexed(self, values, indices):
        from ._independent_dofs import selected_dof_values

        values, indices = selected_dof_values(values, indices, self.dof_count)
        self.require_indexed_joint_control(indices=indices)
        backend = getattr(self._articulation, "_backend_utils", None)
        if backend is not None:
            values = backend.convert(values, getattr(self._articulation, "_device", None))
            indices = backend.convert(indices, getattr(self._articulation, "_device", None), dtype="int32")
        self._articulation.set_joint_positions(values, joint_indices=indices)

    def set_joint_velocities_indexed(self, values, indices):
        from ._independent_dofs import selected_dof_values

        values, indices = selected_dof_values(values, indices, self.dof_count)
        self.require_indexed_joint_control(indices=indices)
        backend = getattr(self._articulation, "_backend_utils", None)
        if backend is not None:
            values = backend.convert(values, getattr(self._articulation, "_device", None))
            indices = backend.convert(indices, getattr(self._articulation, "_device", None), dtype="int32")
        self._articulation.set_joint_velocities(values, joint_indices=indices)

    def set_joint_position_targets(self, targets):
        # type: (np.ndarray) -> None
        self._apply_action(
            joint_positions=np.array(targets, dtype=np.float64),
        )

    def set_joint_position_target(self, joint_index, target):
        # type: (int, float) -> None
        """Select one DOF at the interface, with backend-specific dispatch.

        PhysX accepts a sparse ``ArticulationAction`` and therefore leaves
        mimic followers entirely under the mimic constraint.  The Newton
        backend boundary in :meth:`_apply_action` expands this request to a
        retained finite full target vector; that legacy path is not qualified
        to leave coupled-follower target buffers uncommanded. The stricter
        indexed-control API rejects it instead of making that guarantee.
        """
        self._apply_action(
            joint_positions=np.array([target], dtype=np.float64),
            joint_indices=np.array([joint_index], dtype=np.int32),
        )

    def set_joint_velocity_targets(self, targets):
        # type: (np.ndarray) -> None
        self._apply_action(
            joint_velocities=np.array(targets, dtype=np.float64),
        )

    def set_joint_positions(self, positions):
        # type: (np.ndarray) -> None
        values = np.array(positions, dtype=np.float64)
        backend_utils = getattr(self._articulation, "_backend_utils", None)
        if backend_utils is not None:
            values = backend_utils.convert(values, getattr(self._articulation, "_device", None))
        self._articulation.set_joint_positions(values)

    def set_joint_velocities(self, velocities):
        # type: (np.ndarray) -> None
        values = np.array(velocities, dtype=np.float64)
        backend_utils = getattr(self._articulation, "_backend_utils", None)
        if backend_utils is not None:
            values = backend_utils.convert(values, getattr(self._articulation, "_device", None))
        self._articulation.set_joint_velocities(values)

    # -- Limits --------------------------------------------------------

    def get_joint_position_limits(self):
        # type: () -> Tuple[np.ndarray, np.ndarray]
        lowers = None
        uppers = None
        try:
            props = getattr(self._articulation, "dof_properties", None)
            lowers = get_dof_property(props, "lower")
            uppers = get_dof_property(props, "upper")
        except Exception:
            # Isaac Sim's deprecated SingleArticulation.dof_properties builds
            # a NumPy record array. Newton's view is CUDA-backed, so that
            # compatibility property fails before callers can copy it to CPU.
            pass

        if lowers is None or uppers is None:
            view = getattr(self._articulation, "_articulation_view", None)
            get_limits = getattr(view, "get_dof_limits", None)
            limits = _to_host_array(get_limits() if callable(get_limits) else None)
            if limits is not None:
                while limits.ndim > 2 and limits.shape[0] == 1:
                    limits = limits[0]
                if limits.shape == (self.dof_count, 2):
                    lowers = limits[:, 0]
                    uppers = limits[:, 1]
        if lowers is None:
            lowers = np.full(self.dof_count, np.nan)
        if uppers is None:
            uppers = np.full(self.dof_count, np.nan)
        return (
            _to_dof_array(lowers, self.dof_count),
            _to_dof_array(uppers, self.dof_count),
        )

    def get_joint_velocity_limits(self):
        # type: () -> np.ndarray
        out = None
        try:
            props = getattr(self._articulation, "dof_properties", None)
            out = get_dof_property(props, "max_velocity")
        except Exception:
            pass
        if out is None:
            view = getattr(self._articulation, "_articulation_view", None)
            getter = getattr(view, "get_joint_max_velocities", None)
            out = getter() if callable(getter) else None
        if out is None:
            return np.full(self.dof_count, np.nan, dtype=np.float64)
        return _to_dof_array(out, self.dof_count)

    def get_joint_effort_limits(self):
        # type: () -> np.ndarray
        out = None
        try:
            props = getattr(self._articulation, "dof_properties", None)
            out = get_dof_property(props, "max_effort")
        except Exception:
            pass
        if out is None:
            view = getattr(self._articulation, "_articulation_view", None)
            getter = getattr(view, "get_max_efforts", None)
            out = getter() if callable(getter) else None
        if out is None:
            return np.full(self.dof_count, np.nan, dtype=np.float64)
        return _to_dof_array(out, self.dof_count)

    # -- Joint -> downstream rigid body lookup -------------------------

    def get_child_body_path(self, dof_index):
        """Return the qualified downstream body; unresolved required identity raises."""
        from simready.foundation.tier_newton.runtime_tests.articulation_phases.joint_identity import (
            selected_downstream_body,
        )

        view = getattr(self._articulation, "_articulation_view", None)
        return selected_downstream_body(self._stage, self, dof_index, getattr(view, "_physics_view", None))

    # -- USD velocity limits -> tensor view ----------------------------

    def apply_velocity_limits_to_tensor_view(self, limits):
        """Apply positive caps while preserving omitted native DOF limits.

        Public Articulation setters use (1, dof_count); the legacy tensor
        accessor takes that row plus articulation indices. A setter without
        any getter can only acknowledge application, not verify enforcement.
        NaN is a request-only omission marker, never a native buffer value.
        Full-row writes require a complete live getter to preserve omissions.
        """
        self._velocity_apply_detail = ""
        values = as_real_array(limits)
        if values.shape == (1, self.dof_count):
            values = values[0]
        if values.shape != (self.dof_count,):
            raise ValueError("Velocity-cap request must be one complete DOF vector")
        values = np.asarray(values, dtype=np.float64)
        requested = ~np.isnan(values)
        if np.isinf(values).any() or np.any(values[requested] <= 0.0):
            raise ValueError("Requested velocity caps must be finite and positive")
        if not requested.any():
            self._velocity_apply_detail = "no requested velocity caps; native limits unchanged"
            return False
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            native = values.astype(np.float32)
        if not np.isfinite(native[requested]).all() or np.any(native[requested] <= 0.0):
            raise ValueError("Requested velocity caps are outside the native float32 range")
        first_error = None
        art = self._articulation
        view = getattr(art, "_articulation_view", None)
        backend_utils = getattr(art, "_backend_utils", None)
        device = getattr(art, "_device", None)
        public_getters = [
            getter
            for obj in (art, view)
            if obj is not None
            for getter in (
                getattr(obj, "get_joint_max_velocities", None) or getattr(obj, "get_max_joint_velocities", None),
            )
            if callable(getter)
        ]

        pv = getattr(view if view is not None else art, "_physics_view", None)
        if not requested.all():
            raw_getters = [
                getter for getter in (getattr(pv, "get_dof_max_velocities", None),) if callable(getter)
            ] + list(reversed(public_getters))
            if not raw_getters:
                raise RuntimeError("Cannot preserve omitted velocity caps without complete live native readback")
            current = _to_host_array(raw_getters[0]())
            if current is not None and current.shape == (1, self.dof_count):
                current = current[0]
            if current is None or current.shape != values.shape:
                raise RuntimeError("Cannot preserve omitted velocity caps: incomplete native readback")
            omitted = current[~requested]
            with np.errstate(over="ignore", under="ignore", invalid="ignore"):
                preserved = omitted.astype(np.float32)
            # Zero can be an existing locked native cap; it is not a rating.
            # SDK unlimited sentinels are preserved as state, never invented.
            if (
                not np.isfinite(omitted).all()
                or np.any(omitted < 0.0)
                or not np.isfinite(preserved).all()
                or np.any((omitted > 0.0) & (preserved == 0.0))
            ):
                raise RuntimeError("Cannot preserve omitted velocity caps: unusable native values")
            native[~requested] = preserved
        limits_2d = native.reshape(1, self.dof_count)
        want = native.astype(np.float64)
        backend_limits = limits_2d
        if backend_utils is not None:
            # Torch setters move tensors between devices; they do not convert
            # host NumPy inputs. Convert only the validated complete row.
            backend_limits = backend_utils.convert(limits_2d, device=device, dtype="float32")

        def verify(getter):
            if getter is None:
                self._velocity_apply_detail = "setter acknowledged; no readback accessor available"
                return True
            raw = getter()
            rb = _to_host_array(raw)
            if rb is not None and rb.shape == (1, self.dof_count):
                rb = rb[0]
            if (
                rb is not None
                and rb.shape == want.shape
                and np.isfinite(rb).all()
                # Both arrays describe the submitted float32 native row.
                # Physical-response tolerances do not qualify buffer writes.
                and np.array_equal(rb, want)
            ):
                return True
            self._velocity_apply_detail = "complete finite native velocity-cap readback did not match"
            return False

        for obj in (art, view):
            setter = getattr(obj, "set_max_joint_velocities", None)
            if not callable(setter):
                continue
            getter = getattr(obj, "get_joint_max_velocities", None) or getattr(obj, "get_max_joint_velocities", None)
            if not callable(getter):
                getter = public_getters[0] if public_getters else None
            try:
                setter(backend_limits)
                if verify(getter):
                    return True
            except Exception as error:
                if first_error is None:
                    first_error = error
                self._velocity_apply_detail = "public velocity-cap application/readback failed"

        pv = getattr(view if view is not None else art, "_physics_view", None)
        setter = getattr(pv, "set_dof_max_velocities", None)
        if callable(setter):
            getter = getattr(pv, "get_dof_max_velocities", None)
            if not callable(getter):
                getter = public_getters[0] if public_getters else None
            indices = np.array([0], dtype=np.int32)
            try:
                if backend_utils is not None:
                    indices = backend_utils.convert(indices, device=device, dtype="int32")
                setter(backend_limits, indices)
                if verify(getter):
                    return True
            except Exception as error:
                if first_error is None:
                    first_error = error
                self._velocity_apply_detail = "legacy velocity-cap application/readback failed"
        if first_error is not None:
            raise first_error
        if not self._velocity_apply_detail:
            self._velocity_apply_detail = "no supported velocity-cap setter available"
        return False

    def get_link_world_positions(self, link_prim_paths):
        """Live world positions ``{prim_path: np.ndarray(3,)}`` of the named
        articulation links, read from the physics tensor view.

        Articulation link poses are NOT written back to USD -- a gripper's
        finger links carry no independent USD xform, so ``UsdGeom.XformCache``
        returns the static base rest pose for every one of them (all identical).
        The physics view's link transforms are the only source of the actual
        simulated link poses. Reuses the already-cooked articulation view (no new
        RigidPrim view) to avoid perturbing the tensor-view lifecycle, mirroring
        the private-``_physics_view`` access used elsewhere in this class.

        Returns an empty dict when the physics view or body-name list is not
        available (e.g. before initialize / after the timeline stopped).
        """
        rows = self._get_link_transform_rows(link_prim_paths)
        return {path: row[:3].copy() for path, row in rows.items()}

    def apply_external_force(self, link_prim_path, direction, magnitude_newtons):
        """Apply a world-space force to one articulation link through its tensor view.

        Newton applies the force through its existing articulation tensor view.
        """
        art = self._articulation
        view = getattr(art, "_articulation_view", None) or art
        body_names = list(getattr(view, "body_names", None) or [])
        physics_view = getattr(view, "_physics_view", None)
        if physics_view is None or not body_names:
            return False
        paths = getattr(physics_view, "link_paths", None)
        if (
            not isinstance(paths, (list, tuple))
            or len(paths) != 1
            or not isinstance(paths[0], (list, tuple))
            or len(paths[0]) != len(body_names)
        ):
            return False
        matches = [index for index, path in enumerate(paths[0]) if str(path) == str(link_prim_path)]
        if len(matches) != 1:
            return False
        forces = np.zeros((1, len(body_names), 3), dtype=np.float32)
        forces[0, matches[0], :] = np.asarray(direction, dtype=np.float32) * float(magnitude_newtons)
        indices = np.asarray([0], dtype=np.int32)
        backend_utils = getattr(self._articulation, "_backend_utils", None)
        device = getattr(self._articulation, "_device", None)
        if backend_utils is not None:
            forces = backend_utils.convert(forces, device=device, dtype="float32")
            indices = backend_utils.convert(indices, device=device, dtype="int32")
        submitted = physics_view.apply_forces_and_torques_at_position(forces, None, None, indices, is_global=True)
        return submitted is not False

    def get_link_world_transforms(self, link_prim_paths):
        """Live world poses ``{prim_path: (pos(3,), quat_xyzw(4,))}`` of the named
        links, read from the physics tensor view.

        Same source and caveats as ``get_link_world_positions``, but also returns
        each link's orientation (scalar-last quaternion) so callers can transform
        a link-local point (e.g. a pad's geometry centroid) into world space. The
        link ORIGIN alone is the proximal body frame, which on a 4-bar gripper
        moves opposite to the pad tip -- the orientation is needed to locate the
        actual contact surface.
        """
        rows = self._get_link_transform_rows(link_prim_paths)
        return {path: (row[:3].copy(), row[3:7].copy()) for path, row in rows.items()}

    def _get_link_transform_rows(self, link_prim_paths):
        """Resolve live transform rows without ambiguous or stale name lookup."""
        self._link_transform_resolve_detail = ""
        art = self._articulation
        view = getattr(art, "_articulation_view", None) or art
        body_names = list(getattr(view, "body_names", None) or [])
        pv = getattr(view, "_physics_view", None)
        if pv is None or not body_names:
            self._link_transform_resolve_detail = "physics link view is unavailable"
            return {}
        transforms = _to_host_array(pv.get_link_transforms())
        if transforms is None:
            self._link_transform_resolve_detail = "physics link transforms could not be copied to host"
            return {}
        if transforms.ndim == 3:
            if transforms.shape[0] != 1:
                self._link_transform_resolve_detail = "physics link view returned multiple articulation rows"
                return {}
            transforms = transforms[0]
        if transforms.ndim != 2 or transforms.shape[0] != len(body_names) or transforms.shape[1] < 7:
            self._link_transform_resolve_detail = (
                "stale physics link view: transform shape %r does not match %d body names"
                % (transforms.shape, len(body_names))
            )
            return {}

        name_to_indices = {}
        for index, name in enumerate(body_names):
            name_to_indices.setdefault(str(name), []).append(index)

        out = {}
        for path in link_prim_paths:
            prim = self._stage.GetPrimAtPath(path) if self._stage is not None else None
            if not prim or not prim.IsValid():
                self._link_transform_resolve_detail = "requested physics link prim is stale or missing: %s" % path
                return {}
            leaf_name = path.rsplit("/", 1)[-1]
            indices = name_to_indices.get(leaf_name, [])
            if not indices:
                self._link_transform_resolve_detail = "physics link name %r did not resolve; body_names=%s" % (
                    leaf_name,
                    body_names,
                )
                return {}
            if len(indices) > 1:
                matching_rows = [np.round(transforms[index, :7], 6).tolist() for index in indices]
                reference_row = transforms[indices[0], :7]
                if not all(
                    np.allclose(transforms[index, :7], reference_row, rtol=1e-5, atol=1e-6) for index in indices[1:]
                ):
                    self._link_transform_resolve_detail = (
                        "ambiguous physics link name %r resolves to %d divergent rows %s; body_names=%s"
                        % (leaf_name, len(indices), matching_rows, body_names)
                    )
                    return {}
            row = transforms[indices[0]]
            if not np.isfinite(row[:7]).all():
                self._link_transform_resolve_detail = "non-finite physics transform for link %s" % path
                return {}
            out[path] = row[:7].copy()
        return out
