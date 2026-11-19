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

Core's PhysX initialize() constructs an isaacsim.core.api.World and resets it
to cook the articulation before initializing its SingleArticulation tensor view.
The separate initialize_newton() path attaches directly to Newton's tensor bridge.
"""

import numpy as np
from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import (
    get_dof_property,
)
from simready.foundation.tier_core.runtime_tests.articulation_phases.required_readback import (
    as_real_array,
)


def _authored_articulation_local_scale(stage, prim_path):
    """Retain local dimensions when Isaac canonicalizes an articulation xform.

    USD uses row-vector S*R*T transforms. Row lengths give the local scales
    only when the normalized basis is orthogonal and right-handed. This also
    supports even signed scales through their compensating proper rotation;
    reflected, sheared, singular and reset-stack layouts cannot be preserved
    by the native constructor's scale argument alone and are setup errors.
    Stage units and ancestor scales are deliberately not multiplied in.
    """
    from pxr import UsdGeom

    if stage is None:
        raise RuntimeError("Cannot preserve articulation scale without a valid USD stage.")
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"Cannot preserve articulation scale: root prim {prim_path} is missing or invalid.")
    ancestor = prim
    while ancestor and ancestor.IsValid():
        ancestor_xform = UsdGeom.Xformable(ancestor)
        if ancestor_xform and ancestor_xform.GetResetXformStack():
            raise RuntimeError(
                f"Cannot preserve articulation transform {prim_path}: reset transform stack on {ancestor.GetPath()} is unsupported."
            )
        ancestor = ancestor.GetParent()
    xformable = UsdGeom.Xformable(prim)
    if not xformable:
        # A valid world-pin joint can carry the articulation API without a
        # transform; do not author a scale on that non-transformable joint.
        return None
    if any(op.GetNumTimeSamples() for op in xformable.GetOrderedXformOps()):
        raise RuntimeError(
            f"Cannot preserve articulation transform {prim_path}: time-sampled root xform ops are unsupported."
        )

    def _orthogonal_scales(matrix, frame):
        values = np.asarray(matrix, dtype=np.float64)
        if values.shape != (4, 4) or not np.all(np.isfinite(values)):
            raise RuntimeError(f"Cannot preserve articulation {frame} transform {prim_path}: nonfinite matrix.")
        if not np.allclose(values[:3, 3], 0.0, rtol=0.0, atol=1e-12) or not np.isclose(
            values[3, 3], 1.0, rtol=0.0, atol=1e-12
        ):
            raise RuntimeError(f"Cannot preserve articulation {frame} transform {prim_path}: non-affine matrix.")
        scales = np.linalg.norm(values[:3, :3], axis=1)
        if not np.all(np.isfinite(scales)) or np.any(scales <= 0.0):
            raise RuntimeError(f"Cannot preserve articulation {frame} scale {prim_path}: singular or nonfinite scale.")
        rotation = values[:3, :3] / scales[:, None]
        if not np.allclose(rotation @ rotation.T, np.eye(3), rtol=0.0, atol=1e-6):
            raise RuntimeError(f"Cannot preserve articulation {frame} transform {prim_path}: shear is unsupported.")
        if np.linalg.det(rotation) <= 0.0:
            raise RuntimeError(
                f"Cannot preserve articulation {frame} transform {prim_path}: reflection is unsupported."
            )
        return scales

    local_scale = _orthogonal_scales(xformable.GetLocalTransformation(), "local")
    # SingleArticulation's NumPy backend converts this public argument to
    # float32. Reject overflow/underflow before it can destroy dimensions.
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        native_scale = local_scale.astype(np.float32)
    if not np.all(np.isfinite(native_scale)) or np.any(native_scale <= 0.0):
        raise RuntimeError(
            f"Cannot preserve articulation scale {prim_path}: scale is outside the native float32 range."
        )
    # Isaac obtains its rotation from the composed world basis before resetting
    # xform ops. An ancestor can introduce shear/reflection even when the root's
    # own local matrix is representable; reject rather than silently distort it.
    _orthogonal_scales(UsdGeom.XformCache().GetLocalToWorldTransform(prim), "composed world")
    return local_scale


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
        for coefficient, offset, scale in zip(actuator["coefficients"], offsets, scales, strict=False)
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

    def set_articulation_root_path(self, prim_path):
        """Select the API prim for the next stopped-timeline initialization.

        A transient carrier may suspend a fixed-joint root and put its API on
        the physical body. Rebinding deliberately invalidates the cached prim;
        callers must initialize again before using the articulation controller.
        """
        prim = self._stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"Cannot rebind articulation to missing prim {prim_path}")
        self._robot_prim_path = str(prim_path)
        self._root_prim = None
        self._initialized = False

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
        local_scale = _authored_articulation_local_scale(self._stage, self._robot_prim_path)
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
            "RobotHandle.initialize: World(stage_units_in_meters=1.0) [gravity-enabled; using PhysicsContext defaults]"
        )
        world = World(stage_units_in_meters=1.0)

        ctx.step("RobotHandle.initialize: awaiting initialize_simulation_context_async()")
        await world.initialize_simulation_context_async()

        ctx.step("RobotHandle.initialize: constructing SingleArticulation(name=%s)" % self._name)
        articulation = SingleArticulation(
            prim_path=self._robot_prim_path,
            name=self._name,
            scale=local_scale,
        )

        ctx.step("RobotHandle.initialize: world.scene.add(articulation)")
        try:
            world.scene.add(articulation)
        except Exception as exc:
            raise RuntimeError("Cannot initialize articulation: registering the articulation view failed.") from exc

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
        # Signal the engine proxy that Isaac's World/SimulationContext
        # now owns the timeline. ctx.physics_step() must NOT externally
        # call ``timeline.pause()`` -- doing so corrupts the PhysX tensor
        # simulation view and crashes Kit on the next render/capture.
        engine_session = getattr(ctx, "_engine_session", None)
        if engine_session is not None:
            try:
                engine_session._world_managed_timeline = True
                ctx.step("RobotHandle.initialize: flagged engine session _world_managed_timeline=True")
            except Exception:
                pass

        self._world = world

        # Apply qualified authored velocity-cap requests through the tensor
        # boundary, using resolve_usd_max_velocities's source/unit policy.
        # Preserve live native caps for unauthored DOFs, including existing
        # finite, zero or unlimited values; never fabricate a fallback cap.
        # Application/readback is setup evidence, not physical enforcement.
        try:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.motion_utils import (
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
                        # The boundary preserves unauthored live native caps
                        # or fails before writing. No physical cap is invented.
                        vel_limits = np.where(authored, usd_vels, np.nan)
                        applied = self.apply_velocity_limits_to_tensor_view(vel_limits)
                        vel_summary = ", ".join(
                            "%s=%.2f" % (n, usd_vels[i])
                            for i, n in enumerate(dof_names)
                            if i < len(usd_vels) and authored[i]
                        )
                        if applied:
                            ctx.step(
                                "RobotHandle.initialize: authored joint velocity-cap "
                                f"application acknowledged (native coordinates/s: {vel_summary}); "
                                "unauthored native limits preserved"
                            )
                        else:
                            raise RuntimeError(
                                "Required authored velocity-cap setup failed: " + self._velocity_apply_detail
                            )
                    else:
                        ctx.step(
                            "RobotHandle.initialize: no joint authored a "
                            "velocity limit; PhysX native per-DOF limits "
                            "left unchanged"
                        )
        except BaseException as primary:
            from simready.foundation.tier_core.runtime_tests.articulation_phases.error_utils import (
                note_secondary_error,
                record_required_cleanup_failure,
            )

            try:
                self.teardown(required=True)
            except BaseException as cleanup_error:
                record_required_cleanup_failure(ctx, "required initialization cleanup failed", primary)
                note_secondary_error(
                    primary, lambda error=cleanup_error: f"Required initialization cleanup failed: {error}"
                )
            raise

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
        local_scale = _authored_articulation_local_scale(self._stage, self._robot_prim_path)
        ctx.step("RobotHandle.reinitialize_articulation: removing stale view")
        # registry_only=True drops ONLY the Python registration -- it must NOT
        # delete the USD prims (the default remove_object deletes them, which
        # invalidates the live tensor view: "prim ... was deleted while being
        # used by a shape in a tensor view class"). An unsupported registry-only
        # API is a setup error, never permission to invoke destructive removal.
        try:
            world.scene.remove_object(self._name, registry_only=True)
        except Exception as exc:
            raise RuntimeError("Cannot safely rebuild articulation: registry-only removal failed.") from exc
        articulation = SingleArticulation(prim_path=self._robot_prim_path, name=self._name, scale=local_scale)
        try:
            world.scene.add(articulation)
        except Exception as exc:
            raise RuntimeError("Cannot rebuild articulation: registering the replacement view failed.") from exc
        ctx.step("RobotHandle.reinitialize_articulation: awaiting reset_async()")
        await world.reset_async()
        self._articulation = articulation
        ctx.step(
            "RobotHandle.reinitialize_articulation: rebuilt; dof_names=%r" % (getattr(articulation, "dof_names", None),)
        )

    def teardown(self, *, required=False):
        # type: () -> None
        """Release the World singleton and drop tensor-view references.

        Idempotent. Safe to call multiple times. Call at the end of each
        test that used RobotHandle so the next test starts from a clean
        state; World.clear_instance() at the next initialize() also
        handles this defensively, so teardown here is belt-and-braces.
        ``required=True`` preserves the first cleanup failure for callers that
        must retire a session when controller cleanup cannot be acknowledged.
        """
        first_error = None
        try:
            from isaacsim.core.api import World  # type: ignore

            cleared = World.clear_instance()
            if required and cleared is False:
                raise RuntimeError("Required World singleton cleanup was rejected")
        except BaseException as exc:
            if not required and not isinstance(exc, Exception):
                raise
            first_error = exc
        manager = getattr(self, "_newton_actuators", None)
        if manager is not None:
            try:
                closed = manager.close()
                if required and closed is False:
                    raise RuntimeError("Required Newton controller cleanup was rejected")
            except BaseException as exc:
                if not required and not isinstance(exc, Exception):
                    raise
                if first_error is None:
                    first_error = exc
        self._newton_actuators = None
        self._mjc_tendon_controls = []
        self._world = None
        self._articulation = None
        self._root_prim = None
        self._initialized = False
        if required and first_error is not None:
            raise first_error

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
        """Read the controller target buffer; never substitute measured state.

        PhysX SingleArticulation exposes this through public get_applied_action
        on supported Isaac versions without a direct target getter. Only a
        complete unambiguous action buffer may be used for sparse restoration.
        """
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
            for legacy_index, value in zip(legacy_indices, np.asarray(position_values).reshape(-1), strict=False)
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
                f"(experimental_view={type(experimental_view).__name__} attrs={_diagnostic_attrs(experimental_view)}, legacy_physics_view={type(legacy_physics_view).__name__} attrs={_diagnostic_attrs(legacy_physics_view)}, backend={type(backend).__name__}, "
                f"labels_type={type(labels).__name__}, ctrl={type(ctrl).__name__})"
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
        from simready.foundation.tier_core.runtime_tests.articulation_phases.joint_identity import (
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
                setter(limits_2d)
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
            try:
                setter(limits_2d, np.array([0], dtype=np.int32))
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

    def get_child_body_world_com(self, body_path):
        """Read one live child-body COM in native world coordinates.

        The cooked articulation tensor view supplies both the live link pose
        and link-local COM offset. This strict identity check does not use the
        coincident-row alias accepted by other link callers.
        """
        path = str(body_path)
        prim = self._stage.GetPrimAtPath(path) if self._stage is not None else None
        if not prim or not prim.IsValid():
            raise RuntimeError(f"COM readback: requested child body is missing: {path}")
        view = getattr(self._articulation, "_articulation_view", None) if self._articulation is not None else None
        pv = getattr(view, "_physics_view", None)
        names = list(getattr(view, "body_names", None) or [])
        if pv is None or not names:
            raise RuntimeError("COM readback: cooked articulation physics view or body names are unavailable")
        native_paths = getattr(pv, "link_paths", None)
        if native_paths is None:
            raise RuntimeError("COM readback: authoritative cooked link paths are unavailable")
        if (
            not isinstance(native_paths, (list, tuple))
            or len(native_paths) != 1
            or not isinstance(native_paths[0], (list, tuple))
            or len(native_paths[0]) != len(names)
        ):
            raise RuntimeError("COM readback: cooked link path rows do not match body names")
        matches = [index for index, candidate in enumerate(native_paths[0]) if str(candidate) == path]
        if len(matches) != 1:
            raise RuntimeError("COM readback: requested child path does not uniquely match cooked link paths")

        def single_row(raw, kind):
            try:
                value = raw.detach() if hasattr(raw, "detach") else raw
                value = value.cpu() if hasattr(value, "cpu") else value
                value = value.numpy() if hasattr(value, "numpy") else value
                array = np.asarray(as_real_array(value), dtype=np.float64)
            except Exception as exc:
                raise RuntimeError(f"COM readback: {kind} is not a real numeric tensor") from exc
            if array.ndim == 3 and array.shape[0] == 1:
                array = array[0]
            if array.shape != (len(names), 7) or not np.isfinite(array).all():
                raise RuntimeError(f"COM readback: {kind} has invalid shape or nonfinite values")
            return array[matches[0]]

        try:
            pose = single_row(pv.get_link_transforms(), "live link poses")
            com = single_row(pv.get_coms(), "link-local COM offsets")
        except AttributeError as exc:
            raise RuntimeError("COM readback: required cooked tensor accessor is unavailable") from exc
        q = pose[3:7]
        norm = float(np.linalg.norm(q))
        # Tensor poses are float32 in the native view. Below its unit-scale
        # machine epsilon, normalization would magnify unresolved components.
        min_quat_norm = np.finfo(np.float32).eps
        if not np.isfinite(norm) or norm <= min_quat_norm:
            raise RuntimeError("COM readback: unusable live link quaternion")
        local_com_norm = float(np.linalg.norm(com[3:7]))
        if not np.isfinite(local_com_norm) or local_com_norm <= min_quat_norm:
            raise RuntimeError("COM readback: unusable link-local COM quaternion")
        q = q / norm
        xyz = q[:3]
        offset = com[:3]
        rotated = offset + 2.0 * np.cross(xyz, np.cross(xyz, offset) + q[3] * offset)
        world = pose[:3] + rotated
        if not np.isfinite(world).all():
            raise RuntimeError("COM readback: transformed world point is nonfinite")
        return tuple(float(value) for value in world)

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
