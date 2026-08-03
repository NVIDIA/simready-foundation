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


def _to_dof_array(raw, dof_count):
    # type: (Any, int) -> np.ndarray
    """Coerce a (possibly broken) tensor read into a 1-D float array.

    Returns a NaN-filled array of shape ``(dof_count,)`` when ``raw`` is
    ``None``, a 0-D array, or a wrong-length array. This protects callers
    from ``IndexError`` when the underlying physics view is invalidated.
    """
    if raw is None:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 0 or arr.size == 0:
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    if arr.ndim > 1:
        arr = arr.reshape(-1)
    if dof_count and arr.shape[0] != int(dof_count):
        # Length mismatch — physics view returned a partial / stale frame;
        # treat as invalidated and return NaNs at the expected size.
        return np.full(int(dof_count), np.nan, dtype=np.float64)
    return arr


class RobotHandle:
    """Wrapper over SingleArticulation exposing phase-facing joint API."""

    def __init__(self, stage, robot_prim_path, asset_prim, robot_type):
        # type: (Any, str, Any, RobotType) -> None
        self._stage = stage
        self._robot_prim_path = str(robot_prim_path)
        self._asset_prim = asset_prim
        self._root_prim = None
        self._robot_type = robot_type
        self._articulation = None  # type: Optional[Any]
        self._world = None  # type: Optional[Any]
        self._initialized = False
        self._name = "robot_%d" % id(self)  # unique within this Kit session

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

    async def reinitialize_articulation(self, ctx):
        # type: (Any) -> None
        """Rebuild the SingleArticulation view after the articulation's DOF
        count/topology changed at runtime (e.g. a test-owned prismatic rail
        merges a prismatic joint into the articulation, changing the DOF count).

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
        return _to_dof_array(self._articulation.get_joint_positions(), self.dof_count)

    def get_joint_velocities(self):
        # type: () -> np.ndarray
        """Return joint velocities as a 1-D array of shape (dof_count,).
        See ``get_joint_positions`` for the invalidation-handling rationale.
        """
        return _to_dof_array(self._articulation.get_joint_velocities(), self.dof_count)

    def get_applied_joint_efforts(self):
        # type: () -> np.ndarray
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
        from isaacsim.core.utils.types import ArticulationAction  # type: ignore

        self._articulation.apply_action(ArticulationAction(**kwargs))

    def set_joint_position_targets(self, targets):
        # type: (np.ndarray) -> None
        self._apply_action(
            joint_positions=np.array(targets, dtype=np.float64),
        )

    def set_joint_velocity_targets(self, targets):
        # type: (np.ndarray) -> None
        self._apply_action(
            joint_velocities=np.array(targets, dtype=np.float64),
        )

    def set_joint_positions(self, positions):
        # type: (np.ndarray) -> None
        self._articulation.set_joint_positions(np.array(positions, dtype=np.float64))

    def set_joint_velocities(self, velocities):
        # type: (np.ndarray) -> None
        self._articulation.set_joint_velocities(np.array(velocities, dtype=np.float64))

    # -- Limits --------------------------------------------------------

    def get_joint_position_limits(self):
        # type: () -> Tuple[np.ndarray, np.ndarray]
        props = getattr(self._articulation, "dof_properties", None)
        lowers = get_dof_property(props, "lower")
        uppers = get_dof_property(props, "upper")
        if lowers is None:
            lowers = np.full(self.dof_count, np.nan)
        if uppers is None:
            uppers = np.full(self.dof_count, np.nan)
        return (np.asarray(lowers, dtype=np.float64), np.asarray(uppers, dtype=np.float64))

    def get_joint_velocity_limits(self):
        # type: () -> np.ndarray
        props = getattr(self._articulation, "dof_properties", None)
        out = get_dof_property(props, "max_velocity")
        if out is None:
            return np.full(self.dof_count, np.nan, dtype=np.float64)
        return np.asarray(out, dtype=np.float64)

    def get_joint_effort_limits(self):
        # type: () -> np.ndarray
        props = getattr(self._articulation, "dof_properties", None)
        out = get_dof_property(props, "max_effort")
        if out is None:
            return np.full(self.dof_count, np.nan, dtype=np.float64)
        return np.asarray(out, dtype=np.float64)

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
