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
once PhysX is attached + stepping.
"""

import numpy as np
from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
    get_dof_property,
)


def _to_host_array(raw):
    # type: (Any) -> Optional[np.ndarray]
    """Copy a NumPy, Torch, or Warp value to a host NumPy array."""
    if raw is None:
        return None
    try:
        value = raw.detach() if hasattr(raw, "detach") else raw
        value = value.cpu() if hasattr(value, "cpu") else value
        value = value.numpy() if hasattr(value, "numpy") else value
        return np.asarray(value, dtype=np.float64)
    except Exception:
        return None


def _to_dof_array(raw, dof_count):
    # type: (Any, int) -> np.ndarray
    """Coerce a (possibly broken) tensor read into a 1-D float array.

    Returns a NaN-filled array of shape ``(dof_count,)`` when ``raw`` is
    ``None``, a 0-D array, or a wrong-length array. This protects callers
    from ``IndexError`` when the underlying physics view is invalidated.
    """
    if raw is None:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    arr = _to_host_array(raw)
    if arr is None:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if arr.ndim == 0 or arr.size == 0:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if arr.ndim > 1:
        arr = arr.reshape(-1)
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
            if joint_paths and len(joint_paths) == len(coefficients):
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
            if not gains or len(biases) < 2 or float(gains[0]) == 0.0 or float(biases[1]) >= 0.0:
                continue
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
                joint_target_offsets.append(float(coef0) if coef0 is not None else 0.0)
                joint_target_scales.append(float(coef1) if coef1 is not None else 1.0)
            if not valid_coupling:
                continue
            actuators.append(
                {
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
                    "ctrl_min": (
                        float(minimum_attr.Get()) if minimum_attr and minimum_attr.Get() is not None else -np.inf
                    ),
                    "ctrl_max": (
                        float(maximum_attr.Get()) if maximum_attr and maximum_attr.Get() is not None else np.inf
                    ),
                }
            )
        return actuators
    except Exception:
        return []


def _tendon_position_to_ctrl(actuator, joint_position):
    # type: (dict, float) -> float
    """Convert a common coupled-joint target to an affine tendon control."""
    offsets = actuator.get("joint_target_offsets", [0.0] * len(actuator["coefficients"]))
    scales = actuator.get("joint_target_scales", [1.0] * len(actuator["coefficients"]))
    desired_length = sum(
        coefficient * (offset + scale * float(joint_position))
        for coefficient, offset, scale in zip(actuator["coefficients"], offsets, scales)
    )
    value = -actuator["position_bias"] * desired_length / actuator["gain"]
    return float(np.clip(value, actuator["ctrl_min"], actuator["ctrl_max"]))


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


def _build_newton_actuator_manager(articulation_root_path, actuator_prims):
    """Build one public actuator manager from actuators in disjoint subtrees.

    ``ArticulationActuators(paths)`` discovers only below ``paths``.  FET028's
    test carrier becomes the merged articulation root while the asset remains a
    sibling USD subtree, so normal discovery sees the carrier actuator but not
    the asset's native finger actuator.  Isaac Sim 6 exposes
    ``ArticulationActuators.from_actuators`` for exactly this case: parse the
    existing USD contracts, then bind their unchanged controller components to
    the merged articulation.
    """
    import newton.actuators as newton_actuators  # type: ignore
    from isaacsim.core.experimental.actuators import (  # type: ignore
        ActuatorConfig,
        ArticulationActuators,
    )
    from isaacsim.core.experimental.actuators.impl.clamping_builders import (  # type: ignore
        build_clamping,
    )
    from isaacsim.core.experimental.actuators.impl.controller_builders import (  # type: ignore
        build_controller,
    )
    from isaacsim.core.experimental.actuators.impl.delay_builder import (  # type: ignore
        build_delay,
    )
    from isaacsim.core.experimental.prims import Articulation  # type: ignore
    from newton.actuators import Delay  # type: ignore

    articulation = Articulation(str(articulation_root_path))
    n_robots = len(articulation)
    device = getattr(articulation, "_device", None)
    configs = []
    target_names = set()
    for prim in actuator_prims:
        parsed = newton_actuators.parse_actuator_prim(prim)
        if parsed is None:
            continue
        target_name = str(parsed.target_path).rsplit("/", 1)[-1]
        if target_name in target_names:
            raise ValueError("Multiple NewtonActuator prims target DOF %r" % target_name)
        target_names.add(target_name)
        controller = build_controller(parsed.controller_class, parsed.controller_kwargs, n_robots, device)
        delay = None
        clamping = []
        for component_class, component_kwargs in parsed.component_specs:
            if issubclass(component_class, Delay):
                delay = build_delay(component_kwargs, n_robots, device)
            else:
                clamping.append(build_clamping(component_class, component_kwargs, n_robots, device))
        configs.append(
            (
                ActuatorConfig(controller=controller, clamping=clamping, delay=delay),
                target_name,
            )
        )
    return ArticulationActuators.from_actuators(
        str(articulation_root_path),
        configs,
        auto_step_pre_physics=True,
    )


class RobotHandle:
    """Wrapper over SingleArticulation exposing phase-facing joint API."""

    def __init__(
        self,
        stage,
        robot_prim_path,
        asset_prim,
        robot_type,
        newton_actuator_search_roots=None,
    ):
        # type: (Any, str, Any, RobotType, Any) -> None
        self._stage = stage
        self._robot_prim_path = str(robot_prim_path)
        self._asset_prim = asset_prim
        self._root_prim = None
        self._robot_type = robot_type
        self._articulation = None  # type: Optional[Any]
        self._newton_actuators = None  # type: Optional[Any]
        self._newton_actuator_target_names = set()
        self._mjc_tendon_controls = []  # type: List[dict]
        self._world = None  # type: Optional[Any]
        self._initialized = False
        self._name = "robot_%d" % id(self)  # unique within this Kit session
        self._physics_dt = 1.0 / 240.0
        self._is_newton = False
        roots = list(newton_actuator_search_roots or [self._robot_prim_path])
        self._newton_actuator_search_roots = tuple(dict.fromkeys(str(path) for path in roots if path))

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

    async def initialize(self, ctx):
        # type: (Any) -> None
        """Initialize SingleArticulation using the v1.6 World-based pattern.

        This is the pattern used by
        ``test_definitions/isaac_sim/test_infra/scene_builder.py::build_test_scene``
        (lines 742-801) which runs the same fanuc robots without hanging.
        An earlier attempt to skip ``World`` ("Option A") works for simple
        articulations but hangs on complex ones like the fanuc arms --
        ``World.reset_async()`` is what cooks the articulation and primes
        the PhysX tensor backend. The earlier rejection of "Option B"
        (use World) was based on reading
        Isaac Sim samples, not on testing complex articulations, and is
        empirically wrong for this use case.

        Heartbeats via ctx.step() bracket each blocking call so future
        hangs surface in events.jsonl with a clear last-step marker.
        """
        ctx.step("RobotHandle.initialize: importing World + SingleArticulation for %s" % self._robot_prim_path)
        from isaacsim.core.api import World  # type: ignore

        try:
            from isaacsim.core.prims import SingleArticulation  # type: ignore
        except Exception:
            from isaacsim.core.prims.single_articulation import (  # type: ignore
                SingleArticulation,
            )

        # World is a singleton; clear any leftover from a prior test so
        # this test starts with a fresh simulation context.
        ctx.step("RobotHandle.initialize: World.clear_instance()")
        try:
            World.clear_instance()
        except Exception:
            pass

        ctx.step(
            "RobotHandle.initialize: World(stage_units_in_meters=1.0) "
            "[gravity-enabled; using PhysicsContext defaults]"
        )
        world = World(stage_units_in_meters=1.0)

        ctx.step("RobotHandle.initialize: awaiting " "initialize_simulation_context_async()")
        await world.initialize_simulation_context_async()

        ctx.step("RobotHandle.initialize: constructing SingleArticulation(name=%s)" % self._name)
        articulation = SingleArticulation(
            prim_path=self._robot_prim_path,
            name=self._name,
        )

        ctx.step("RobotHandle.initialize: world.scene.add(articulation)")
        try:
            world.scene.add(articulation)
        except Exception as exc:
            # v1.6 swallows this too -- scene.add can complain when the
            # articulation is already registered under the same name.
            ctx.step("RobotHandle.initialize: world.scene.add ignored (%s)" % exc)

        ctx.step(
            "RobotHandle.initialize: awaiting world.reset_async() "
            "(cooks articulation; may take time for complex robots)"
        )
        await world.reset_async()

        ctx.step(
            "RobotHandle.initialize: world.reset_async() returned; "
            "dof_names=%r" % getattr(articulation, "dof_names", None)
        )

        # Publish the articulation reference NOW -- right after reset_async has
        # cooked it and primed the tensor/physics view -- not at the end of
        # initialize. The velocity-limit apply below calls
        # ``self.apply_velocity_limits_to_tensor_view``, which reads
        # ``self._articulation``; assigning it only at the end of this method
        # meant that call ran against ``None`` and silently failed ("no public
        # set_max_joint_velocities and no _physics_view available"), so every
        # joint ran UNCAPPED. The articulation view is valid here, so the limit
        # apply now resolves correctly.
        self._articulation = articulation

        # Enforce the asset's AUTHORED joint velocity limits via the tensor API.
        #
        # PhysX's tensor backend leaves the per-DOF max velocity effectively
        # unlimited (~1e10) unless the authored value is pushed in, so without
        # this the motion phases (IK, multi-joint coordination, full-range
        # sweep) would whip joints at unrealistic speed, overshoot, and fail
        # for no real reason. We push in ONLY what the asset authored -- both
        # authoring forms are honored: physxJoint:maxJointVelocity and
        # physxDrivePerformanceEnvelope:{angular,linear}:maxActuatorVelocity
        # (the latter converted deg/s -> rad/s) -- and apply NO artificial cap
        # and NO fabricated fallback. DOFs the asset left unlimited keep PhysX's
        # native value. This faithfully enforces the asset's own limits and is
        # applied uniformly to every robot type; the former hard 6 rad/s cap and
        # the per-robot-type gating have been removed.
        try:
            from simready_benchmark_kit_suite.articulation_phases.motion_utils import (
                resolve_usd_max_velocities,
            )

            dof_names = list(getattr(articulation, "dof_names", []) or [])
            if dof_names and self._stage is not None:
                usd_vels = resolve_usd_max_velocities(
                    stage=self._stage,
                    robot_prim_path=self._robot_prim_path,
                    dof_names=dof_names,
                    asset_prim=self._asset_prim,
                    robot_root_prim=self._stage.GetPrimAtPath(self._robot_prim_path),
                    use_min_when_both=True,
                    actuator_deg_to_rad=True,
                )
                if usd_vels is not None:
                    usd_vels = np.asarray(usd_vels, dtype=np.float64)
                    authored = np.isfinite(usd_vels) & (usd_vels > 0)
                    if bool(np.any(authored)):
                        # Build the full per-DOF max-velocity array (rad/s):
                        #   authored DOF        -> the authored limit
                        #   unauthored, finite  -> keep the current native value
                        #   otherwise           -> a large finite "unlimited"
                        #                          sentinel (never NaN/inf)
                        # The sentinel matters: get_joint_velocity_limits() can
                        # read back NaN, and writing NaN makes the whole
                        # set_dof_max_velocities call fail -- which would
                        # silently drop the AUTHORED caps too, leaving every
                        # joint uncapped (the "moves too fast" symptom).
                        UNLIMITED = np.float32(1.0e6)
                        current = np.asarray(self.get_joint_velocity_limits(), dtype=np.float32)
                        vel_limits = np.full(self.dof_count, UNLIMITED, dtype=np.float32)
                        for i in range(self.dof_count):
                            if i < len(usd_vels) and authored[i]:
                                vel_limits[i] = np.float32(usd_vels[i])
                            elif i < len(current) and np.isfinite(current[i]) and current[i] > 0:
                                vel_limits[i] = np.float32(current[i])
                        applied = self.apply_velocity_limits_to_tensor_view(vel_limits)
                        vel_summary = ", ".join(
                            "%s=%.2f" % (n, usd_vels[i])
                            for i, n in enumerate(dof_names)
                            if i < len(usd_vels) and authored[i]
                        )
                        if applied:
                            ctx.step(
                                "RobotHandle.initialize: enforced authored joint "
                                "velocity limits via tensor API (rad/s: %s); "
                                "unauthored DOFs left effectively unlimited" % vel_summary
                            )
                        else:
                            # The limits did NOT take effect. Surface it loudly:
                            # uncapped joints will whip and IK/MJC/FRS will
                            # overshoot, which is a TEST-RIG failure, not an
                            # asset defect.
                            ctx.warn(
                                "RobotHandle.initialize: FAILED to apply authored "
                                "joint velocity limits (%s). Joints will run "
                                "UNCAPPED and motion tests (IK / multi-joint "
                                "coordination / full-range sweep) may overshoot "
                                "for this reason rather than an asset defect. "
                                "Authored limits (rad/s) were: %s"
                                % (getattr(self, "_velocity_apply_detail", "") or "unknown reason", vel_summary)
                            )
                    else:
                        ctx.step(
                            "RobotHandle.initialize: no joint authored a "
                            "velocity limit; PhysX native per-DOF limits "
                            "left unchanged"
                        )
        except Exception as exc:
            ctx.warn(
                "RobotHandle.initialize: applying authored velocity limits "
                "raised (%s); joints use PhysX native limits." % exc
            )

        # Signal the engine proxy that Isaac's World/SimulationContext
        # now owns the timeline. ctx.physics_step() must NOT externally
        # call ``timeline.pause()`` -- doing so corrupts the PhysX tensor
        # simulation view and crashes Kit on the next render/capture.
        engine_session = getattr(ctx, "_engine_session", None)
        if engine_session is not None:
            try:
                engine_session._world_managed_timeline = True
                ctx.step("RobotHandle.initialize: flagged engine session " "_world_managed_timeline=True")
            except Exception:
                pass

        self._world = world
        # self._articulation already assigned right after reset_async (above),
        # so the velocity-limit apply during init could see a valid view.
        if self._stage is not None:
            self._root_prim = self._stage.GetPrimAtPath(self._robot_prim_path)
        self._initialized = True

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

                self._newton_actuators = (
                    _build_newton_actuator_manager(self._robot_prim_path, actuator_prims)
                    if len(self._newton_actuator_search_roots) > 1
                    else ArticulationActuators(
                        self._robot_prim_path,
                        auto_step_pre_physics=True,
                    )
                )
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
                    "initialize ArticulationActuators for {}: {}".format(
                        self._robot_prim_path,
                        exc,
                    )
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

    async def reinitialize_articulation(self, ctx):
        # type: (Any) -> None
        """Rebuild the SingleArticulation view after the articulation's DOF
        count/topology changed at runtime (FET028 prismatic rail merges a
        prismatic Z joint into the gripper articulation, 19 -> 20 DOFs).

        The view was first cooked at the OLD DOF count by
        ``setup_robot_test_scene``; a plain ``world.reset_async()`` after the
        merge then re-applies a stale OLD-sized default actuation array and PhysX
        rejects it ("Incompatible size of DOF force tensor: expected 20,
        received 19"). Removing the stale view from ``world.scene``, creating a
        fresh ``SingleArticulation``, re-adding it, and resetting rebuilds every
        cached array at the NEW DOF count. Reuses the existing World (no
        ``clear_instance``) so the rest of the scene/timeline is untouched.
        """
        try:
            from isaacsim.core.prims import SingleArticulation  # type: ignore
        except Exception:
            from isaacsim.core.prims.single_articulation import (  # type: ignore
                SingleArticulation,
            )
        world = self._world
        if world is None:
            raise RuntimeError("reinitialize_articulation called before initialize(); no World.")
        ctx.step("RobotHandle.reinitialize_articulation: removing stale view")
        # registry_only=True drops ONLY the Python registration -- it must NOT
        # delete the USD prims (the default remove_object deletes them, which
        # invalidates the live tensor view: "prim ... was deleted while being
        # used by a shape in a tensor view class"). Fall back defensively if
        # this Isaac build lacks the flag.
        try:
            world.scene.remove_object(self._name, registry_only=True)
        except TypeError:
            try:
                world.scene.remove_object(self._name)
            except Exception as exc:
                ctx.step("RobotHandle.reinitialize_articulation: remove ignored " "(%s)" % exc)
        except Exception as exc:
            ctx.step("RobotHandle.reinitialize_articulation: remove ignored (%s)" % exc)
        articulation = SingleArticulation(prim_path=self._robot_prim_path, name=self._name)
        try:
            world.scene.add(articulation)
        except Exception as exc:
            ctx.step("RobotHandle.reinitialize_articulation: add ignored (%s)" % exc)
        ctx.step("RobotHandle.reinitialize_articulation: awaiting reset_async()")
        await world.reset_async()
        self._articulation = articulation
        ctx.step(
            "RobotHandle.reinitialize_articulation: rebuilt; dof_names=%r" % (getattr(articulation, "dof_names", None),)
        )

    def teardown(self):
        # type: () -> None
        """Release the World singleton and drop tensor-view references.

        Idempotent. Safe to call multiple times. Call at the end of each
        test that used RobotHandle so the next test starts from a clean
        state; World.clear_instance() at the next initialize() also
        handles this defensively, so teardown here is belt-and-braces.
        """
        try:
            from isaacsim.core.api import World  # type: ignore

            World.clear_instance()
        except Exception:
            pass
        manager = getattr(self, "_newton_actuators", None)
        if manager is not None:
            try:
                manager.close()
            except Exception:
                pass
        self._newton_actuators = None
        self._mjc_tendon_controls = []
        self._world = None
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
            return _to_dof_array(getter(), self.dof_count)
        return np.full(self.dof_count, np.nan, dtype=np.float64)

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
        # type: () -> np.ndarray
        if self._newton_actuators is not None:
            efforts = self._newton_actuators.articulation.get_dof_efforts()
            return self._native_values_in_legacy_order(efforts)
        fn = getattr(self._articulation, "get_applied_joint_efforts", None)
        if fn is None:
            return np.zeros(self.dof_count, dtype=np.float64)
        return np.array(fn(), dtype=np.float64)

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
        if getattr(self, "_is_newton", False) and indices is not None and sparse_positions is not None:
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
        # would advance every controller once per *command*.  FET028 submits
        # independent carrier and finger commands in the same frame, so manual
        # stepping here would update both PID states twice and can destabilize
        # an otherwise valid Newton gripper.
        if position_values is not None and getattr(self, "_mjc_tendon_controls", None):
            self._apply_mjc_tendon_position_targets(position_values, legacy_indices)

    def _apply_mjc_tendon_position_targets(self, position_values, legacy_indices):
        # type: (Any, np.ndarray) -> None
        """Translate per-joint targets into fixed-tendon actuator controls."""
        selected = {
            self.dof_names[int(legacy_index)]: float(value)
            for legacy_index, value in zip(legacy_indices, np.asarray(position_values).reshape(-1))
        }
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
                "(experimental_view={} attrs={}, legacy_physics_view={} attrs={}, backend={}, "
                "labels_type={}, ctrl={})".format(
                    type(experimental_view).__name__,
                    _diagnostic_attrs(experimental_view),
                    type(legacy_physics_view).__name__,
                    _diagnostic_attrs(legacy_physics_view),
                    type(backend).__name__,
                    type(labels).__name__,
                    type(ctrl).__name__,
                )
            )
        values = ctrl.numpy()
        changed = False
        actuator_updates = {}
        for actuator in self._mjc_tendon_controls:
            requested = [selected[name] for name in actuator["control_joint_names"] if name in selected]
            if not requested:
                continue
            # A coupled gripper command names one or both tendon joints. The
            # desired tendon length uses the same target for every coupled DOF.
            actuator_ctrl = _tendon_position_to_ctrl(actuator, requested[0])
            try:
                actuator_index = labels.index(actuator["target_path"])
            except ValueError as exc:
                raise RuntimeError(
                    "Newton did not compile tendon target {} for actuator {}".format(
                        actuator["target_path"], actuator["actuator_path"]
                    )
                ) from exc
            values.reshape(-1)[actuator_index] = actuator_ctrl
            actuator_updates[actuator_index] = actuator_ctrl
            changed = True
        if changed:
            import warp as wp  # type: ignore

            wp.copy(ctrl, wp.array(values, dtype=ctrl.dtype, device=ctrl.device))
            # Root-pose updates used by Newton FET028 can leave the public
            # stage-control buffer and the already-compiled MuJoCo solver data
            # out of sync. Keep the solver's live ctrl array coherent with the
            # same actuator-indexed values. On ordinary articulation runs this
            # is idempotent with Newton's normal stage->solver synchronization.
            solver = getattr(newton_stage, "solver", None)
            solver_ctrl = getattr(getattr(solver, "mjw_data", None), "ctrl", None)
            if solver_ctrl is not None:
                solver_values = solver_ctrl.numpy()
                solver_flat = solver_values.reshape(-1, solver_values.shape[-1])
                for actuator_index, control_value in actuator_updates.items():
                    solver_flat[:, actuator_index] = control_value
                wp.copy(
                    solver_ctrl,
                    wp.array(solver_values, dtype=solver_ctrl.dtype, device=solver_ctrl.device),
                )

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

    def set_joint_position_targets(self, targets):
        # type: (np.ndarray) -> None
        self._apply_action(
            joint_positions=np.array(targets, dtype=np.float64),
        )

    def set_joint_position_target(self, joint_index, target):
        # type: (int, float) -> None
        """Command one DOF without writing targets for coupled followers.

        PhysX accepts a sparse ``ArticulationAction`` and therefore leaves
        mimic followers entirely under the mimic constraint.  The Newton
        backend boundary in :meth:`_apply_action` expands this sparse request
        to the finite full-array form required by Isaac Sim's Newton wrapper.
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
        # type: (int) -> Any
        """Return the USD path of the rigid body downstream of DOF `dof_index`.

        Tries multiple strategies in order so different robot asset
        layouts all resolve cleanly:

        1. Narrow walk under the articulation root with exact name match.
           Works for robots whose joints are descendants of the
           articulation root prim (the simple case).
        2. Narrow walk under articulation root with case-insensitive match.
        3. Full-stage walk with exact name match.
           Works for SimReady robot assets that author joints in a
           sibling scope (e.g., joints at `/robot/Physics/J1` while the
           articulation root sits at `/robot/Geometry/world`). v1.6
           shared_phases.effort_limit uses this pattern.
        4. Full-stage walk with case-insensitive match (catches DOF/prim
           name mismatches like "joint_1" vs "Joint_1").

        At each match attempt, reads the joint's body1 rel (authoritative). A
        sibling rigid body is used ONLY when it is unambiguous (exactly one). If
        more than one joint matches the DOF name, resolution is ambiguous and
        this returns None rather than guessing which joint a DOF maps to (a wrong
        guess silently pushes the wrong link and corrupts the effort result); the
        reason is recorded in ``self._child_body_resolve_detail`` for the caller
        to surface. Returns None when no strategy resolves a unique body.
        """
        self._child_body_resolve_detail = ""
        if self._stage is None or self._articulation is None:
            return None
        if dof_index < 0 or dof_index >= self.dof_count:
            return None
        try:
            dof_names = list(self._articulation.dof_names)
        except Exception:
            return None
        if dof_index >= len(dof_names):
            return None
        target_name = str(dof_names[dof_index])

        try:
            from pxr import Usd, UsdPhysics
        except Exception:
            return None

        def _is_joint(prim):
            return (
                prim.IsA(UsdPhysics.RevoluteJoint)
                or prim.IsA(UsdPhysics.PrismaticJoint)
                or prim.IsA(UsdPhysics.FixedJoint)
                or prim.IsA(UsdPhysics.SphericalJoint)
            )

        def _resolve_body(joint_prim):
            # Authoritative: the joint's body1 rel names the exact child body.
            try:
                joint = UsdPhysics.Joint(joint_prim)
                targets = joint.GetBody1Rel().GetTargets()
                if targets:
                    return str(targets[0])
            except Exception:
                pass
            # No body1 authored. Accept a sibling rigid body ONLY when it is
            # unambiguous (exactly one); never "the first of several" -- that
            # guess would silently push the wrong link.
            parent = joint_prim.GetParent()
            if parent and parent.IsValid():
                rb_siblings = [s for s in parent.GetChildren() if s.HasAPI(UsdPhysics.RigidBodyAPI)]
                if len(rb_siblings) == 1:
                    return str(rb_siblings[0].GetPath())
                self._child_body_resolve_detail = (
                    "joint '%s' has no physics:body1 and %d rigid-body sibling(s)"
                    " (cannot disambiguate)" % (joint_prim.GetName(), len(rb_siblings))
                )
            return None

        def _resolve_unique(iterator, match_name, case_insensitive):
            # Collect every joint whose name matches. More than one distinct
            # match is ambiguous -- we must not silently resolve to the first.
            # Returns ("found", body) | ("ambiguous", None) | ("none", None).
            matches = []
            for prim in iterator:
                if not _is_joint(prim):
                    continue
                name = prim.GetName()
                if case_insensitive:
                    if name.lower() != match_name.lower():
                        continue
                elif name != match_name:
                    continue
                matches.append(prim)
            if len(matches) > 1:
                self._child_body_resolve_detail = (
                    "ambiguous: %d joints named '%s' (case_insensitive=%s); refusing"
                    " to guess which one DOF %d maps to" % (len(matches), match_name, case_insensitive, dof_index)
                )
                return "ambiguous", None
            if matches:
                return "found", _resolve_body(matches[0])
            return "none", None

        # Try strategies in order: narrow exact, narrow case-insensitive, full
        # exact, full case-insensitive. A unique resolved match wins. An
        # ambiguous match (more than one joint with the name) stops the search
        # and returns None -- we never guess which joint a DOF maps to.
        strategies = []
        root = self._stage.GetPrimAtPath(self._robot_prim_path)
        if root and root.IsValid():

            def _narrow():
                return Usd.PrimRange(root, Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))

            strategies.append((_narrow, False))
            strategies.append((_narrow, True))

        def _full():
            return self._stage.Traverse(Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))

        strategies.append((_full, False))
        strategies.append((_full, True))

        for make_iter, case_insensitive in strategies:
            status, body = _resolve_unique(make_iter(), target_name, case_insensitive)
            if status == "ambiguous":
                return None
            if body:
                return body

        if not self._child_body_resolve_detail:
            self._child_body_resolve_detail = "no joint named '%s' resolved to a child body" % target_name
        return None

    # -- USD velocity limits -> tensor view ----------------------------

    def apply_velocity_limits_to_tensor_view(self, limits):
        # type: (np.ndarray) -> bool
        """Push per-DOF max joint velocities (rad/s) into the articulation.

        Prefers the PUBLIC ``set_max_joint_velocities`` API on the Isaac core
        articulation (view), which manages the physics tensor view and the
        init / physics-handle checks internally, and verifies via read-back
        (the setter silently no-ops if the physics handle is not yet valid).
        Falls back to the legacy private ``_physics_view.set_dof_max_velocities``
        accessor. ``limits`` is rad/s for revolute DOFs (Isaac's tensor
        convention; the caller already converted deg->rad).

        Returns True only when the limits were actually applied. On failure the
        reason is recorded in ``self._velocity_apply_detail`` for the caller to
        surface -- the previous code swallowed the error and joints silently ran
        uncapped (motion tests then overshoot / "jump" to targets).
        """
        self._velocity_apply_detail = ""
        limits_2d = np.asarray(limits, dtype=np.float32).reshape(1, self.dof_count)
        want = np.asarray(limits, dtype=np.float64).reshape(-1)[: self.dof_count]

        art = self._articulation
        view = getattr(art, "_articulation_view", None)
        for obj in (art, view):
            if obj is None:
                continue
            setter = getattr(obj, "set_max_joint_velocities", None)
            if not callable(setter):
                continue
            try:
                setter(limits_2d)
            except Exception as exc:
                self._velocity_apply_detail = "set_max_joint_velocities raised: %r" % (exc,)
                continue
            getter = getattr(obj, "get_joint_max_velocities", None) or getattr(obj, "get_max_joint_velocities", None)
            if not callable(getter):
                return True  # applied; no getter to verify with
            try:
                rb = np.asarray(getter(), dtype=np.float64).reshape(-1)[: self.dof_count]
                m = np.isfinite(rb) & np.isfinite(want)
                if m.any() and np.allclose(rb[m], want[m], rtol=0.1, atol=0.1):
                    return True
                self._velocity_apply_detail = (
                    "set_max_joint_velocities did not take effect (read-back %s != "
                    "requested %s); physics handle likely not valid yet"
                    % (np.round(rb, 2).tolist(), np.round(want, 2).tolist())
                )
            except Exception:
                return True  # applied; could not read back to verify

        # Legacy private physics-view fallback.
        try:
            pv = getattr(view if view is not None else art, "_physics_view", None)
            if pv is not None:
                pv.set_dof_max_velocities(limits_2d, np.array([0], dtype=np.int32))
                return True
            if not self._velocity_apply_detail:
                self._velocity_apply_detail = "no public set_max_joint_velocities and no _physics_view available"
        except Exception as exc:
            self._velocity_apply_detail = "_physics_view.set_dof_max_velocities raised: %r" % (exc,)
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

        This is the backend-neutral path used by Newton. PhysX continues to use
        its imperative simulation interface because that avoids articulation
        recooking in older Kit releases.
        """
        art = self._articulation
        view = getattr(art, "_articulation_view", None) or art
        body_names = list(getattr(view, "body_names", None) or [])
        physics_view = getattr(view, "_physics_view", None)
        if physics_view is None or not body_names:
            return False
        leaf_name = str(link_prim_path).rsplit("/", 1)[-1]
        matches = [index for index, name in enumerate(body_names) if str(name) == leaf_name]
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
        physics_view.apply_forces_and_torques_at_position(forces, None, None, indices, is_global=True)
        return True

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
