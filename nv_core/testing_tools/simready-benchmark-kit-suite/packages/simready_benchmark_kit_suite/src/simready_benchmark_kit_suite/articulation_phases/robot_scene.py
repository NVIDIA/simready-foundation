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
"""Compose a robot-ready test scene using Framework 2.0 primitives."""

from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
    compute_world_aligned_bbox,
    get_articulation_root_path,
)
from simready_benchmark_kit_suite.articulation_phases.passive_joints import (
    detect_passive_joints,
)
from simready_benchmark_kit_suite.articulation_phases.robot_handle import RobotHandle
from simready_benchmark_kit_suite.articulation_phases.robot_state import (
    capture_default_state,
)
from simready_benchmark_kit_suite.articulation_phases.robot_type import (
    RobotType,
    determine_robot_type,
    get_scene_defaults,
    has_authored_robot_type,
)

# ---------------------------------------------------------------------------
# Fix-message helpers
#
# Library value proposition: a failure message must teach the asset author
# EXACTLY how to fix the asset. Each helper below returns a message with
# (1) headline, (2) what was searched vs. expected, (3) the prim path /
# attribute to author, (4) a paste-ready USDA snippet, and (5) a spec +
# real-asset reference. Keep these as module-level pure functions so
# unit tests can snapshot them without scene setup.
# ---------------------------------------------------------------------------

_SPEC_BASE = "nv_core/sr_specs/docs/capabilities"
_REF_ARTICULATION_ROOT = (
    "REFERENCE:\n"
    "  Spec:      {base}/physics_bodies/base_articulation/requirements/\n"
    "             has-articulation-root.md  (BA.001)\n"
    "  Spec:      {base}/physics_bodies/physics_joints/requirements/\n"
    "             articulation.md           (JT.ART.001)\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/\n"
    "             2F-85/simready_isaac_usd/Robotiq_2F_85.usda\n"
    "             (PhysicsArticulationRootAPI on the gripper base Xform)"
).format(base=_SPEC_BASE)

_REF_ROBOT_TYPE = (
    "REFERENCE:\n"
    "  Spec:      {base}/isaac_sim/robot_core/requirements/robot-type.md\n"
    "             (RC.008 -- allowed tokens: Manipulator, End Effector,\n"
    "             Humanoid, Wheeled, Holonomic, Quadruped,\n"
    "             Mobile Manipulators, Aerial)\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/\n"
    "             2F-85/simready_isaac_usd/Robotiq_2F_85.usda\n"
    '             (token isaac:robotType = "End Effector")'
).format(base=_SPEC_BASE)


def _fix_message_asset_load_failed(asset_path):
    # type: (str) -> str
    """Asset prim is invalid after load_asset returned. The framework
    composed the layer but couldn't resolve the defaultPrim, so it is
    either missing, points to a path that does not exist, or the file
    itself failed to open.
    """
    return (
        "Asset failed to load (defaultPrim is missing or invalid):\n"
        "    {path}\n"
        "\n"
        "FIX: Open the USD file in a USD-aware tool (usdview, Kit, or a\n"
        "text editor for ASCII USDA) and confirm:\n"
        "  1. The file opens without composition errors.\n"
        "  2. The root layer declares a `defaultPrim` metadata entry and\n"
        "     that token names an actual top-level prim.\n"
        "  3. The defaultPrim is an Xform that contains the robot links\n"
        "     and joints (not an empty stub or an over).\n"
        "\n"
        "TEMPLATE -- minimal layer header at the top of your .usda:\n"
        "\n"
        "    #usda 1.0\n"
        "    (\n"
        '        defaultPrim = "Robot"\n'
        "        metersPerUnit = 1\n"
        '        upAxis = "Z"\n'
        "    )\n"
        "\n"
        '    def Xform "Robot" (\n'
        "        prepend apiSchemas = [\n"
        '            "PhysicsArticulationRootAPI",\n'
        '            "IsaacRobotAPI"\n'
        "        ]\n"
        "    )\n"
        "    {{\n"
        '        token isaac:robotType = "Manipulator"\n'
        "        # ... links + joints ...\n"
        "    }}\n"
        "\n"
        "If the file has sublayers / references / payloads, also verify\n"
        "each of those resolve from the asset's location.\n"
    ).format(path=asset_path)


def _fix_message_no_articulation_root(asset_prim_path):
    # type: (str) -> str
    """No prim under the asset has PhysicsArticulationRootAPI applied.
    The framework refuses to test an asset with no declared articulation
    because PhysX would otherwise infer a root heuristically and produce
    silently wrong results.
    """
    return (
        "No articulation root found under {root}.\n"
        "The framework searched every descendant for\n"
        "`PhysicsArticulationRootAPI` and found none.\n"
        "\n"
        "FIX: Apply `PhysicsArticulationRootAPI` to ONE prim per\n"
        "articulated asset. The correct prim depends on the robot style:\n"
        "\n"
        "  * Fixed-base robot (arm bolted to a table, gripper bolted to\n"
        "    a flange): apply it to the root JOINT that connects the\n"
        "    robot to the world (a PhysicsFixedJoint with body0 unset\n"
        "    or pointing to world). This is the OpenUSD-canonical pattern\n"
        "    for fixed articulations.\n"
        "\n"
        "  * Free-floating robot (mobile base, quadruped, humanoid):\n"
        "    apply it to the root BODY -- the top-level Xform that\n"
        "    carries `PhysicsRigidBodyAPI` and is the base link of the\n"
        "    kinematic tree.\n"
        "\n"
        "Apply to exactly ONE prim; nested articulation roots produce\n"
        "undefined behavior (see articulation-no-nesting.md).\n"
        "\n"
        "TEMPLATE A -- fixed-base robot (apply to root joint):\n"
        "\n"
        '    def PhysicsFixedJoint "root_joint" (\n'
        '        prepend apiSchemas = ["PhysicsArticulationRootAPI"]\n'
        "    )\n"
        "    {{\n"
        "        rel physics:body1 = </Robot/base_link>\n"
        "    }}\n"
        "\n"
        "TEMPLATE B -- free-floating robot (apply to base body):\n"
        "\n"
        '    def Xform "base_link" (\n'
        "        prepend apiSchemas = [\n"
        '            "PhysicsRigidBodyAPI",\n'
        '            "PhysicsArticulationRootAPI"\n'
        "        ]\n"
        "    )\n"
        "    {{\n"
        "        # ... mass, collision, child links ...\n"
        "    }}\n"
        "\n"
        "{ref}"
    ).format(root=asset_prim_path, ref=_REF_ARTICULATION_ROOT)


def _fix_message_no_root_body_for_pin(robot_root_path):
    # type: (str) -> str
    """Gripper classified but find_root_body() returned empty. The
    framework's pin step needs ONE rigid body to attach a temporary
    FixedJoint to so per-joint tests don't rotate the whole gripper.
    """
    return (
        "Cannot pin gripper base to world: no candidate base body found\n"
        "under articulation root {root}.\n"
        "\n"
        "The framework searched two ways and both failed:\n"
        "  1. Descendant scan -- no prim under the articulation root\n"
        "     carries `PhysicsRigidBodyAPI`.\n"
        "  2. Joint-rooted scan -- no joint immediately under the root\n"
        "     has a `body1` (or `body0`) relationship pointing to a prim\n"
        "     with `PhysicsRigidBodyAPI`.\n"
        "\n"
        "Without a pin, per-joint torque tests (vel/sta/dgv/eff) rotate\n"
        "the whole gripper via action-reaction instead of moving the\n"
        "tested joint, so their results are not trustworthy.\n"
        "\n"
        "FIX: Decide which physical link is the gripper's base (the\n"
        "flange / palm / wrist body) and ensure ONE of the following\n"
        "is authored:\n"
        "\n"
        "  Option 1 (preferred) -- apply PhysicsRigidBodyAPI to the\n"
        "  base link and place PhysicsArticulationRootAPI on the same\n"
        "  prim or on an Xform ancestor:\n"
        "\n"
        '    def Xform "base_link" (\n'
        "        prepend apiSchemas = [\n"
        '            "PhysicsRigidBodyAPI",\n'
        '            "PhysicsArticulationRootAPI"\n'
        "        ]\n"
        "    )\n"
        "    {{\n"
        "        float physics:mass = 0.85\n"
        "        # ... colliders, child links ...\n"
        "    }}\n"
        "\n"
        "  Option 2 -- joint-rooted articulation: place\n"
        "  PhysicsArticulationRootAPI on a fixed joint whose `body1`\n"
        "  rel targets the base link:\n"
        "\n"
        '    def PhysicsFixedJoint "root_joint" (\n'
        '        prepend apiSchemas = ["PhysicsArticulationRootAPI"]\n'
        "    )\n"
        "    {{\n"
        "        rel physics:body1 = </Robot/base_link>\n"
        "    }}\n"
        "\n"
        '    def Xform "base_link" (\n'
        '        prepend apiSchemas = ["PhysicsRigidBodyAPI"]\n'
        "    )\n"
        "    {{ ... }}\n"
        "\n"
        "{ref}"
    ).format(root=robot_root_path, ref=_REF_ARTICULATION_ROOT)


def _fix_message_zero_dofs(robot_root_path):
    # type: (str) -> str
    """Articulation cooked but reports 0 DOFs. Either no movable joints
    are authored under the root, or every joint is fixed/locked.
    """
    return (
        "Articulation has zero degrees of freedom at {root}.\n"
        "\n"
        "PhysX cooked the articulation successfully but reports 0 DOFs.\n"
        "That means the articulation's joint tree contains no movable\n"
        "joints reachable from the root. Common authoring causes:\n"
        "\n"
        "  * The root has no child joints -- the articulation root was\n"
        "    applied to a leaf prim that has no PhysicsRevoluteJoint /\n"
        "    PhysicsPrismaticJoint / PhysicsSphericalJoint underneath.\n"
        "  * Every joint under the root is a PhysicsFixedJoint (which\n"
        "    contributes 0 DOFs) or has its motion axes locked\n"
        "    (lowerLimit == upperLimit, or jointEnabled = false).\n"
        "  * The chain is broken: child joints exist but their\n"
        "    `physics:body0` / `physics:body1` relationships do not\n"
        "    reach back to the articulation root, so PhysX treats them\n"
        "    as detached and excludes them from the articulation.\n"
        "\n"
        "FIX: Open the USD and confirm:\n"
        "  1. At least one PhysicsRevoluteJoint or PhysicsPrismaticJoint\n"
        "     exists at or below {root}.\n"
        "  2. For each such joint, `physics:body0` and `physics:body1`\n"
        "     target prims with `PhysicsRigidBodyAPI`, forming a\n"
        "     connected tree rooted at the articulation root's base body.\n"
        "  3. Each movable joint has `physics:lowerLimit` <\n"
        "     `physics:upperLimit` (or no limits at all -- both means\n"
        "     unlimited motion).\n"
        "  4. `physics:jointEnabled = true` (or unset, which defaults\n"
        "     to enabled).\n"
        "\n"
        "TEMPLATE -- minimal movable joint between two rigid bodies:\n"
        "\n"
        '    def PhysicsRevoluteJoint "joint_1"\n'
        "    {{\n"
        "        rel physics:body0 = </Robot/base_link>\n"
        "        rel physics:body1 = </Robot/link_1>\n"
        '        uniform token physics:axis = "Z"\n'
        "        float physics:lowerLimit = -180.0\n"
        "        float physics:upperLimit =  180.0\n"
        "    }}\n"
        "\n"
        "{ref}"
    ).format(root=robot_root_path, ref=_REF_ARTICULATION_ROOT)


def _fix_message_robot_type_unauthored_gripper_signals():
    # type: () -> str
    """isaac:robotType not authored, but the asset clearly looks like a
    gripper (PhysxMimicJointAPI or gripper_* + IsaacSiteAPI). Reclassify
    silently to GRIPPER, but tell the author how to make it explicit.
    """
    return (
        "Asset has no `isaac:robotType` authored on the default prim,\n"
        "but the framework detected positive gripper signals\n"
        "(PhysxMimicJointAPI joints or gripper_* sites with\n"
        "IsaacSiteAPI). Reclassifying as GRIPPER for this run so we\n"
        "skip the ik/jik phases and pin the base correctly.\n"
        "\n"
        "FIX: Author `isaac:robotType` explicitly so the classification\n"
        "does not rely on heuristics. Add to the asset's default prim:\n"
        "\n"
        '    over "Robot" (\n'
        '        prepend apiSchemas = ["IsaacRobotAPI"]\n'
        "    )\n"
        "    {\n"
        '        token isaac:robotType = "End Effector"\n'
        "    }\n"
        "\n" + _REF_ROBOT_TYPE
    )


def _fix_message_robot_type_unauthored_default_arm():
    # type: () -> str
    """isaac:robotType not authored and asset doesn't look like a
    gripper. Treat as ARM (Manipulator), but tell the author how to
    make it explicit.
    """
    return (
        "Asset has no `isaac:robotType` authored on the default prim;\n"
        "the framework is defaulting to ARM (Manipulator) for this run.\n"
        "Type-specific tuning (ik/jik phases, gravity disable, ground\n"
        "plane suppression) is driven by this value -- defaulting may\n"
        "exercise the wrong phase set if the asset is actually a mobile\n"
        "base or end effector.\n"
        "\n"
        "FIX: Author `isaac:robotType` explicitly on the asset's default\n"
        "prim. Add:\n"
        "\n"
        '    over "Robot" (\n'
        '        prepend apiSchemas = ["IsaacRobotAPI"]\n'
        "    )\n"
        "    {\n"
        '        token isaac:robotType = "Manipulator"\n'
        "    }\n"
        "\n" + _REF_ROBOT_TYPE
    )


def _has_gripper_signals(stage, asset_prim):
    # type: (Any, Any) -> bool
    """Return True iff the asset's USD shows a positive gripper signal:

    - Any joint prim has ``PhysxMimicJointAPI`` applied (a gripper / 4-bar
      linkage signature; bare arms don't typically use mimic), OR
    - Any descendant carries the spec-canonical
      ``simready:attactment:socketType = "Gripper"`` attribute on an Xform, OR
    - Any descendant has a ``gripper_*`` prim name with ``IsaacSiteAPI``
      applied (Isaac-format gripper-site authoring).

    Conservative — false negatives (a gripper without any of these signals
    stays classified as ARM) are preferable to false positives (an arm
    without isaac:robotType authored gets reclassified as a gripper and
    loses its ik/jik coverage). Pure-USD inspection; no articulation
    initialization required.
    """
    if asset_prim is None or not asset_prim.IsValid():
        return False
    try:
        from pxr import Usd
    except Exception:
        return False
    for prim in Usd.PrimRange(asset_prim):
        try:
            applied = list(prim.GetAppliedSchemas())
            try:
                applied.extend(list(prim.GetPrimTypeInfo().GetAppliedAPISchemas()))
            except Exception:
                pass
        except Exception:
            applied = []
        for s in applied:
            s_str = str(s)
            # Multi-apply: "PhysxMimicJointAPI:rotZ" etc.
            if s_str.startswith("PhysxMimicJointAPI"):
                return True
        # Spec-canonical: simready:attactment:socketType = "Gripper"
        sock = prim.GetAttribute("simready:attactment:socketType")
        if sock and sock.IsDefined():
            try:
                if sock.Get() == "Gripper":
                    return True
            except Exception:
                pass
        if prim.GetName().startswith("gripper_"):
            for s in applied:
                if str(s) == "IsaacSiteAPI":
                    return True
    return False


async def setup_robot_test_scene(ctx, config_overrides=None):
    # type: (Any, Optional[Dict[str, Any]]) -> Tuple[Any, Dict[str, Any]]
    """Build a robot-ready scene and return (RobotHandle, scene_info).

    Performs the full sequence: load asset, determine RobotType, create room
    (auto-size), add physics, apply scene defaults (gravity / ground plane),
    create RobotHandle, start timeline, settle, initialize tensor view,
    capture default state + initial bbox + passive joints.

    Calls ctx.precheck_failure(msg) on precondition failures (no articulation
    root, zero DOFs). Callers should `return` after the precheck_failure.
    Returns (None, {}) on precheck_failure so callers can guard.
    """
    cfg = dict(ctx.config)
    if config_overrides:
        cfg.update(config_overrides)

    # 1. Load asset
    timeout = int(cfg.get("asset_load_timeout", 30))
    asset_handle = ctx.scene.load_asset(ctx.asset_path, timeout=timeout)
    stage = ctx.scene.stage
    asset_prim = stage.GetPrimAtPath(asset_handle.prim_path)
    if not asset_prim or not asset_prim.IsValid():
        ctx.precheck_failure(_fix_message_asset_load_failed(ctx.asset_path))
        return (None, {})

    # 1a. De-instance every `instanceable=true` prim under the asset.
    # Fanuc-style robots author their geometry inside instanced
    # ``visuals/`` and ``collisions/`` Xforms. Omni Fabric cannot resolve
    # attribute lookups through instance proxies, so any code path that
    # queries Fabric by a child path (SingleArticulation registering
    # link colliders, text_3d creating overlay GeomSubsets, the render
    # update walking the articulation) emits warnings like
    # "getAttributeCount called on non-existent path
    # /World/AssetRoot/Asset/robot_base/visuals/base" and can lead to
    # silent Kit crashes shortly after. v1.6 avoided this by
    # de-instancing as a side effect of FET001 material override; we
    # do it explicitly here before World/PhysX touches the stage.
    try:
        from pxr import Usd

        deinstanced = 0
        for prim in Usd.PrimRange(asset_prim):
            if prim.IsInstance():
                prim.SetInstanceable(False)
                deinstanced += 1
        if deinstanced:
            ctx.step(
                "setup_robot_test_scene: de-instanced %d prim(s) under %s "
                "so Fabric can resolve child paths" % (deinstanced, asset_handle.prim_path)
            )
    except Exception as exc:
        ctx.step(
            "INTERNAL: de-instance pass raised an unexpected exception "
            "(ignored; Fabric child-path lookups may emit warnings on "
            "instanced visuals/collisions): %s" % exc
        )

    # 2. Determine RobotType
    robot_type = determine_robot_type(stage, asset_prim)

    # 2a. Heuristic for unauthored robotType: only reclassify ARM->GRIPPER
    # when there are POSITIVE gripper signals in the asset (mimic joints or
    # gripper_* sites with IsaacSiteAPI). The earlier "always assume gripper
    # when unauthored" rule was too aggressive — it misclassified arms that
    # declare isaac:robotType but don't author a value (e.g. the UR10),
    # silently skipping their ik/jik tests.
    #
    # If the asset is plainly unauthored AND has no gripper signals, leave it
    # as ARM but still warn so the user knows authoring is the proper fix.
    if not has_authored_robot_type(stage, asset_prim) and robot_type == RobotType.ARM:
        if _has_gripper_signals(stage, asset_prim):
            ctx.warn(_fix_message_robot_type_unauthored_gripper_signals())
            robot_type = RobotType.GRIPPER
        else:
            ctx.warn(_fix_message_robot_type_unauthored_default_arm())

    # 3. Articulation root
    robot_root_path = get_articulation_root_path(stage, asset_prim)
    if not robot_root_path:
        ctx.precheck_failure(_fix_message_no_articulation_root(asset_prim.GetPath()))
        return (None, {})

    # 4. Scene defaults from robot type
    scene_defaults = get_scene_defaults(robot_type)

    # 5. Room
    room = ctx.scene.add_room()
    room.auto_size(asset_handle)
    # Robots that do not use a ground plane (ARM, SCARA) often reach below
    # the asset base during a sweep; keep walls for lighting / bbox framing
    # but hide the floor so the arm is not clipped visually and does not
    # collide with a surface it should not be touching.
    if not scene_defaults.get("activate_ground_plane", False):
        try:
            room.hide_ground()
        except Exception:
            pass

    # 6. Physics. Gravity is always enabled (9.81 m/s^2) for every robot type;
    # the scene is authored with the value at creation time so there is nothing
    # to override afterwards.
    physics_fps = float(cfg.get("physics_fps", 240.0))
    scene_gravity = 9.81
    ctx.step("setup_robot_test_scene: add_physics(gravity=9.81, fps=%s)" % physics_fps)
    physics = ctx.scene.add_physics(gravity=scene_gravity, fps=physics_fps)
    # PhysX cold init (CUDA/tensor backend) can run hundreds of ms to
    # multiple seconds on the first session, all silent because
    # add_physics is synchronous and does not pump the renderer. Emit
    # a step so the watchdog sees activity before the next await.
    ctx.step("setup_robot_test_scene: add_physics returned (PhysicsScene cooked)")

    # 8. Ground plane
    if scene_defaults.get("activate_ground_plane", False):
        ctx.scene.enable_ground_plane(friction=0.5)

    # 9. Lighting
    ctx.scene.lighting.add_dome(intensity=1000.0)

    # 10. Build RobotHandle (pre-init)
    robot = RobotHandle(
        stage=stage,
        robot_prim_path=robot_root_path,
        asset_prim=asset_prim,
        robot_type=robot_type,
    )

    # 11. Camera follow
    ctx.scene.setup_camera_follow(cfg)

    # 11a. Pin gripper base to world.
    # Without a pin, applying joint torque to a free-floating gripper rotates
    # the entire articulation (action-reaction), making per-joint tests measure
    # base rotation instead of joint motion. State accuracy, mimic, multi-joint
    # coordination, and JIK all degrade. The pin is a temporary FixedJoint at
    # ``physics_utils.WORLD_PIN_PATH`` (single slot — fine because we only test
    # one robot per session). It is harmless on already-pinned assets (the
    # solver sees a redundant zero-motion constraint).
    pinned_body_path = ""
    if robot_type == RobotType.GRIPPER:
        try:
            from simready_benchmark_engine_kit.physics_utils import (
                find_root_body,
                pin_body_to_world,
            )

            base_body = find_root_body(stage, robot_root_path)
            if base_body:
                if pin_body_to_world(stage, base_body):
                    pinned_body_path = base_body
                    ctx.step("setup_robot_test_scene: pinned gripper base to world: %s" % base_body)
                else:
                    ctx.warn(
                        "INTERNAL: pin_body_to_world(%s) returned False; "
                        "the framework could not author the temporary "
                        "FixedJoint at WORLD_PIN_PATH. This is not an "
                        "asset bug -- file an issue against simready-benchmark "
                        "with the asset path and this log. Per-joint "
                        "tests may rotate the whole gripper for this "
                        "run." % base_body
                    )
            else:
                ctx.warn(_fix_message_no_root_body_for_pin(robot_root_path))
        except Exception as exc:
            ctx.warn(
                "INTERNAL: gripper pin step raised an unexpected "
                "exception (ignored, per-joint tests may rotate the whole "
                "gripper): %s" % exc
            )

    # 12. Let the asset finish composing BEFORE World creation + reset.
    # World.reset_async() (called inside robot.initialize) plays the
    # timeline, attaches PhysX, cooks the articulation, and steps once,
    # so we don't need a manual physics.play() + settle pair here.
    ctx.step("setup_robot_test_scene: settle for asset composition")
    await ctx.settle(count=1)

    # 12a. Cook dynamic mesh colliders (and author missing mass) OFF the
    # timeline path, time-boxed, BEFORE robot.initialize() -- which plays the
    # timeline, attaches PhysX, and cooks the articulation. A cold SDF cook
    # there can freeze the run; doing it here as a pumped, time-boxed step
    # keeps the run alive and reports a clean failure if a collider cannot cook.
    from simready_benchmark_engine_kit.physics_utils import cook_skip_message

    cook_skip = cook_skip_message(await ctx.scene.prepare_physics())
    if cook_skip is not None:
        ctx.precheck_failure(cook_skip[5:].strip())
        return (None, {})

    # 13. Initialize via World + SingleArticulation + reset_async
    # (v1.6 pattern; see robot_handle.initialize docstring).
    ctx.step("setup_robot_test_scene: awaiting robot.initialize(ctx)")
    await robot.initialize(ctx)
    ctx.step("setup_robot_test_scene: robot.initialize(ctx) returned")

    # 14. Precondition: DOFs must exist.
    # Return ``(None, {})`` (not ``(robot, {})``) so callers' standard
    # ``if robot is None: return`` guard triggers and downstream phases
    # don't try to operate on a 0-DOF articulation -- which would fail
    # with obscure errors (empty position arrays, index out of range on
    # dof_names) instead of the actionable precheck message above.
    if robot.dof_count == 0:
        ctx.precheck_failure(_fix_message_zero_dofs(robot_root_path))
        return (None, {})

    # Capture default state + initial bbox + passive joints
    default_state = capture_default_state(robot)
    initial_bbox = compute_world_aligned_bbox(robot.root_prim or asset_prim)
    passive_indices, passive_names = detect_passive_joints(stage, robot_root_path, robot.dof_names)

    # Mimic followers: detect once and expose to all phases via scene_info.
    # Each per-joint phase (sta/vel/dgv/eff) skips these because their
    # position is determined by the reference (master) joint via
    # PhysxMimicJointAPI — commanding them independently is futile and
    # produces noise, not signal. Empty set on assets with no mimic.
    mimic_follower_indices = set()  # type: set
    mimic_follower_names = []  # type: list
    try:
        from simready_benchmark_kit_suite.articulation_phases.mimic_joints import (
            detect_mimic_joints,
        )

        specs = detect_mimic_joints(stage, asset_prim, robot_root_path, robot.dof_names)
        for s in specs:
            if s.follower_dof_index is None:
                continue
            mimic_follower_indices.add(int(s.follower_dof_index))
            try:
                name = robot.dof_names[int(s.follower_dof_index)]
                mimic_follower_names.append(str(name))
            except Exception:
                pass
    except Exception as exc:
        ctx.warn(
            "INTERNAL: mimic-follower detection raised an unexpected "
            "exception (ignored, mimic followers will be commanded "
            "directly and may produce noisy results): %s" % exc
        )

    # Closed-loop / parallel-linkage joints (e.g. a parallelogram counterbalance
    # on heavy arms). These are not independently commandable -- the loop
    # constraint fights an independent position target -- so per-joint phases
    # exclude them, exactly like passive and mimic-follower joints. Empty set on
    # normal open-chain robots.
    loop_joint_indices = set()  # type: set
    loop_joint_names = []  # type: list
    try:
        from simready_benchmark_kit_suite.articulation_phases.joint_utils import (
            detect_loop_joints,
        )

        loop_joint_indices, loop_joint_names = detect_loop_joints(stage, robot_root_path, list(robot.dof_names))
        if loop_joint_names:
            ctx.warn(
                "Closed kinematic loop detected; excluding parallel-linkage "
                "joints from independent per-joint driving (they are "
                "constrained by the loop and cannot track an independent "
                "target): %s. Refer to DJ.011 (no articulation loops)." % ", ".join(loop_joint_names)
            )
    except Exception as exc:
        ctx.warn(
            "INTERNAL: loop-joint detection raised (ignored; loop joints will "
            "be driven directly and may fail spuriously): %s" % exc
        )

    scene_info = {
        "asset_handle": asset_handle,
        "physics": physics,
        "robot_type": robot_type,
        "default_state": default_state,
        "initial_bbox": initial_bbox,
        "passive_joint_indices": passive_indices,
        "passive_dof_names": passive_names,
        "mimic_follower_indices": mimic_follower_indices,
        "mimic_follower_names": mimic_follower_names,
        "loop_joint_indices": loop_joint_indices,
        "loop_joint_names": loop_joint_names,
        "stage": stage,
        "asset_prim": asset_prim,
        "robot_root_prim": robot.root_prim,
        "camera_prim_path": "/World/Camera",
        # Empty string = no pin applied; non-empty = path of the pinned base body.
        "pinned_to_world": pinned_body_path,
    }
    return (robot, scene_info)
