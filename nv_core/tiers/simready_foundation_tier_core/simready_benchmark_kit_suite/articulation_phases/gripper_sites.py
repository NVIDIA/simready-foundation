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
"""Runtime discovery and parsing of gripper sites for FET028.

A gripper site is discovered via ``simready:attachment:socketType = "Gripper"``
(or ``IsaacSiteAPI`` as a fallback), with child ``gripper_forward_axis`` and
``gripper_grip_line`` ``BasisCurves`` prims and a ``gripper_maxOpening`` float
attribute. Optional ``gripper_maxPayload`` declares the rated max payload in
kg. Unprefixed spellings (``forward_axis``, ``grip_line``, ``custom:maxOpening``,
``custom:maxPayload``) are accepted for existing assets. Static schema
validation lives in nv_core/sr_specs/.../physics_grippers/validation.py; this
module is the runtime read path that the FET028 close-and-lift phase consumes.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from pxr import Usd, UsdGeom


@dataclass
class GripperSite:
    """Snapshot of a gripper site at discovery time.

    The ``_initial`` suffix on pose-bearing fields is deliberate: callers
    must not assume these track the live prim transform — they are frozen
    at discovery and only used as reference frames for the test (e.g.
    object spawn pose).
    """

    prim_path: str
    pose_world_initial: np.ndarray  # 4x4
    forward_axis_world: np.ndarray  # unit 3-vector
    grip_line_world: Tuple[np.ndarray, np.ndarray]  # (p0, p1) world
    max_opening: float
    max_payload: Optional[float]

    def grasp_center_world_initial(self) -> np.ndarray:
        """Translation in world coords — the grasp center between finger pads."""
        return self.pose_world_initial[3, :3].copy()

    def closure_axis_world(self) -> np.ndarray:
        """Unit closure-motion axis = forward × grip_line direction.

        Suggested authoring keeps gripper_forward_axis ⟂ gripper_grip_line so
        this cross product is well-defined; GR.003 does not validate
        orthogonality. Sign is asset-frame-determined; treat as undirected
        (use abs(dot(axis, ref))). When the cross product degenerates
        (nearly parallel curves), falls back to +Z.
        """
        grip_dir = self.grip_line_world[1] - self.grip_line_world[0]
        n = np.linalg.norm(grip_dir)
        if n < 1e-9:
            return np.array([0.0, 0.0, 1.0])
        grip_dir = grip_dir / n
        c = np.cross(self.forward_axis_world, grip_dir)
        cn = np.linalg.norm(c)
        if cn < 1e-9:
            return np.array([0.0, 0.0, 1.0])
        return c / cn


def discover_gripper_sites(stage, asset_prim) -> List[GripperSite]:
    """Discover all gripper sites under ``asset_prim``.

    Returns an empty list if no qualifying sites exist.
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return []
    out: List[GripperSite] = []
    for prim in Usd.PrimRange(asset_prim):
        if not _is_qualifying_gripper_site(prim):
            continue
        site = _read_gripper_site(prim)
        if site is not None:
            out.append(site)
    return out


def diagnose_missing_sites(stage, asset_prim) -> str:
    """Build a copy-paste-ready fix message for an asset with no sites.

    Library philosophy: when a test cannot run because of missing asset
    authoring, the failure message must teach the asset author EXACTLY
    how to fix the asset -- not just say "missing X". The output of this
    function lands in ``result.json`` and on the HTML report, where it is
    the only signal an asset author gets back from CI.

    Two failure modes get distinct messages:

    * **Mode A -- no discovery candidates**: nothing under ``asset_prim``
      matches either FET028 discovery rule. The asset has no gripper-site
      authoring at all. Returns a full Xform template the author can
      drop under the gripper base link and adapt to their geometry.

    * **Mode B -- candidate exists but is incomplete**: at least one prim
      qualifies (via ``simready:attachment:socketType`` or
      ``IsaacSiteAPI``) but lacks the required child BasisCurves or the
      ``custom:maxOpening`` attribute. Returns the path of the actual
      candidate prim, the specific pieces missing on it, and the
      minimal USDA snippet to paste UNDER that prim.

    Both modes link to the spec, the canonical validator, and a working
    real-asset example so the author has multiple references.
    """
    if stage is None or asset_prim is None or not asset_prim.IsValid():
        return "Asset prim is not valid; cannot search for gripper sites."

    qualifying = []
    socket_hits = 0
    isaac_hits = 0
    for prim in Usd.PrimRange(asset_prim):
        if not _is_qualifying_gripper_site(prim):
            continue
        qualifying.append(prim)
        sock = prim.GetAttribute(_SOCKET_TYPE_ATTR)
        if sock and sock.IsDefined() and sock.Get() == _SOCKET_TYPE_VALUE:
            socket_hits += 1
        elif _has_applied(prim, "IsaacSiteAPI"):
            isaac_hits += 1

    if not qualifying:
        return _fix_message_no_candidates(asset_prim.GetPath())

    # At least one candidate; report the first one specifically (most
    # grippers have exactly one site, and per-site authoring is uniform).
    target = qualifying[0]
    missing_children = []
    missing_attrs = []
    if not _first_child(target, _FORWARD_AXIS_NAMES):
        missing_children.append("gripper_forward_axis")
    if not _first_child(target, _GRIP_LINE_NAMES):
        missing_children.append("gripper_grip_line")
    mo = _read_float_attr_aliases(target, _MAX_OPENING_NAMES)
    if mo is None or mo <= 0.0:
        missing_attrs.append("gripper_maxOpening")
    # ``via`` reports how THIS specific target qualified -- decided per-prim,
    # not from the aggregate counts (which can mix discovery rules across
    # multiple qualifying prims).
    sock = target.GetAttribute(_SOCKET_TYPE_ATTR)
    target_via_socket = bool(sock and sock.IsDefined() and sock.Get() == _SOCKET_TYPE_VALUE)
    via = "socketType" if target_via_socket else "IsaacSiteAPI"
    return _fix_message_incomplete_candidate(
        target_path=target.GetPath(),
        via=via,
        missing_children=missing_children,
        missing_attrs=missing_attrs,
        extra_candidates=len(qualifying) - 1,
    )


_SPEC_REFERENCE = (
    "REFERENCE:\n"
    "  Spec:      nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_grippers/requirements/\n"
    "  Validator: nv_core/sr_specs/docs/capabilities/physics_bodies/"
    "physics_grippers/validation.py\n"
    "  Example:   sample_content/common_assets/robots_general/Robotiq/"
    "2F-85/simready_isaac_usd/Robotiq_2F_85.usda\n"
    '             (search for: def Xform "gripper_01")'
)


def _fix_message_no_candidates(asset_path) -> str:
    return (
        "No FET028 gripper-site authoring found under {root}.\n"
        "\n"
        "FIX: Author one Xform prim per grasp point. Most parallel-jaw\n"
        "grippers have ONE site at the grasp center between the finger\n"
        "pads. Place the prim under a stable parent (the gripper base\n"
        "link) so it translates with the end-effector, and translate it\n"
        "to the grasp center in local coordinates.\n"
        "\n"
        "The prim must declare:\n"
        "  - a discovery marker (spec-canonical socketType OR IsaacSiteAPI)\n"
        "  - child BasisCurves 'gripper_forward_axis' (approach direction)\n"
        "  - child BasisCurves 'gripper_grip_line'    (between finger pad tips)\n"
        "  - custom float 'gripper_maxOpening' (max jaw separation, METERS)\n"
        "\n"
        "TEMPLATE -- paste under your gripper base prim, edit the\n"
        "translate / maxOpening / curve points to match your asset:\n"
        "\n"
        '    def Xform "gripper_01" (\n'
        '        prepend apiSchemas = ["IsaacSiteAPI"]\n'
        "    )\n"
        "    {{\n"
        "        # Spec-canonical discovery (preferred, OpenUSD-compatible)\n"
        '        token simready:attachment:socketType = "Gripper"\n'
        "\n"
        "        # Isaac runtime metadata (recommended)\n"
        '        string isaac:Description = "Parallel-jaw grasp center"\n'
        "\n"
        "        # Max jaw opening between the two pads, in METERS\n"
        "        custom float gripper_maxOpening = 0.085\n"
        "        # Rated payload in kg (optional, used by FET028 to size\n"
        "        # the test object mass)\n"
        "        custom float gripper_maxPayload = 5.0\n"
        "\n"
        "        # Translate to grasp center in local parent coords\n"
        "        double3 xformOp:translate = (0, 0, 0.16)\n"
        '        uniform token[] xformOpOrder = ["xformOp:translate"]\n'
        "\n"
        "        # Approach direction: from grasp center along close-in path\n"
        '        def BasisCurves "gripper_forward_axis"\n'
        "        {{\n"
        "            point3f[] points = [(0, 0, 0), (0, 0, 0.05)]\n"
        "            int[] curveVertexCounts = [2]\n"
        '            uniform token type = "linear"\n'
        '            uniform token purpose = "guide"\n'
        "        }}\n"
        "\n"
        "        # Pad-to-pad line: two points at finger pad tip positions\n"
        "        # when FULLY OPEN. The segment length should equal\n"
        "        # gripper_maxOpening.\n"
        '        def BasisCurves "gripper_grip_line"\n'
        "        {{\n"
        "            point3f[] points = [(-0.0425, 0, 0.05),"
        " (0.0425, 0, 0.05)]\n"
        "            int[] curveVertexCounts = [2]\n"
        '            uniform token type = "linear"\n'
        '            uniform token purpose = "guide"\n'
        "        }}\n"
        "    }}\n"
        "\n"
        "{ref}"
    ).format(root=asset_path, ref=_SPEC_REFERENCE)


def _fix_message_incomplete_candidate(
    target_path,
    via,
    missing_children,
    missing_attrs,
    extra_candidates,
) -> str:
    missing_lines = []
    for child in missing_children:
        if child == "gripper_forward_axis":
            missing_lines.append("    - child 'gripper_forward_axis' (BasisCurves, 2 points," " approach direction)")
        elif child == "gripper_grip_line":
            missing_lines.append(
                "    - child 'gripper_grip_line'    (BasisCurves, 2 points," " pad-to-pad at max open)"
            )
    for attr in missing_attrs:
        if attr == "gripper_maxOpening":
            missing_lines.append("    - attribute 'gripper_maxOpening' (positive float," " METERS, jaw separation)")
    extra_note = ""
    if extra_candidates > 0:
        extra_note = (
            "  ({n} additional candidate prim(s) also need fixing;"
            " repeat the same edits per prim.)\n".format(n=extra_candidates)
        )
    snippet_parts = []
    if missing_attrs and "gripper_maxOpening" in missing_attrs:
        snippet_parts.append(
            "        # Max jaw opening between the two pads, in METERS\n"
            "        custom float gripper_maxOpening = 0.085\n"
            "        # Optional rated payload in kg\n"
            "        custom float gripper_maxPayload = 5.0\n"
        )
    if "gripper_forward_axis" in missing_children:
        snippet_parts.append(
            '        def BasisCurves "gripper_forward_axis"\n'
            "        {\n"
            "            point3f[] points = [(0, 0, 0), (0, 0, 0.05)]\n"
            "            int[] curveVertexCounts = [2]\n"
            '            uniform token type = "linear"\n'
            '            uniform token purpose = "guide"\n'
            "        }\n"
        )
    if "gripper_grip_line" in missing_children:
        snippet_parts.append(
            '        def BasisCurves "gripper_grip_line"\n'
            "        {\n"
            "            # Segment length should equal gripper_maxOpening,\n"
            "            # at the finger pad tip positions when fully open\n"
            "            point3f[] points = [(-0.0425, 0, 0.05),"
            " (0.0425, 0, 0.05)]\n"
            "            int[] curveVertexCounts = [2]\n"
            '            uniform token type = "linear"\n'
            '            uniform token purpose = "guide"\n'
            "        }\n"
        )
    snippet = "\n".join(snippet_parts)
    return (
        "FET028 gripper-site authoring incomplete on {path}.\n"
        "  Qualified via: {via}\n"
        "  Missing:\n"
        "{missing}\n"
        "{extra}"
        "\n"
        "FIX: Edit your USD file so the prim at\n"
        "    {path}\n"
        "carries the missing pieces. Paste the following INSIDE that\n"
        "prim's body (edit values to match your asset's actual grasp\n"
        "geometry, then re-run):\n"
        "\n"
        "{snippet}\n"
        "{ref}"
    ).format(
        path=target_path,
        via=via,
        missing="\n".join(missing_lines) if missing_lines else "    (none)",
        extra=extra_note,
        snippet=snippet if snippet else "    (no snippet -- nothing to add)",
        ref=_SPEC_REFERENCE,
    )


# Per FET028 spec (nv_core/sr_specs/.../physics_grippers/requirements/
# gripper-socket-type.md GR.001), the discovery attribute for a gripper
# site is ``simready:attachment:socketType = "Gripper"`` on an Xform
# prim. Prim NAME is explicitly unconstrained -- the spec example shows
# ``grasp_site_left`` and ``site_a`` as valid -- and the canonical
# validator at ``physics_grippers/validation.py`` keys discovery off
# this attribute alone.
_SOCKET_TYPE_ATTR = "simready:attachment:socketType"
_SOCKET_TYPE_VALUE = "Gripper"


def _is_qualifying_gripper_site(prim) -> bool:
    """Return True iff ``prim`` is a discoverable gripper site.

    Discovery rules (in spec priority order):

    1. ``simready:attachment:socketType = "Gripper"`` (Neutral format,
       GR.001) -- prim name is unconstrained per the spec.
    2. ``IsaacSiteAPI`` applied to an Xform (Isaac format, GR.ISA.001) --
       kept as a backwards-compatibility path for assets that were
       authored under the older Isaac-only spec draft before the
       socketType attribute became the canonical discovery mechanism
       (e.g. the Robotiq 2F-85 currently in our sample_content).

    The previous implementation also required the prim name to start
    with ``gripper_``; that requirement was never in the FET028 spec
    and silently disqualified spec-compliant assets whose IsaacSiteAPI prims
    have asset-specific names. Dropped.
    """
    if not prim.IsA(UsdGeom.Xform):
        return False
    # Exclude surface-gripper sites (suction/magnet style); FET028 covers
    # parallel-jaw close+lift only. This filter applies regardless of
    # which discovery path matched below.
    if _has_applied(prim, "IsaacSurfaceGripperAPI"):
        return False
    parent = prim.GetParent()
    if parent and parent.IsValid() and _has_applied(parent, "IsaacSurfaceGripperAPI"):
        return False
    # Spec-canonical discovery: simready:attachment:socketType = "Gripper".
    socket_attr = prim.GetAttribute(_SOCKET_TYPE_ATTR)
    if socket_attr and socket_attr.IsDefined():
        try:
            if socket_attr.Get() == _SOCKET_TYPE_VALUE:
                return True
        except Exception:
            pass
    # Backwards-compat: legacy Isaac-format authoring without socketType.
    if _has_applied(prim, "IsaacSiteAPI"):
        return True
    return False


def _has_applied(prim, schema_name) -> bool:
    """Detect an applied API schema by name.

    Checks both ``GetAppliedSchemas`` (the public accessor, which filters
    out unregistered schemas) and ``GetPrimTypeInfo().GetAppliedAPISchemas``
    (the raw apiSchemas metadata view, which includes unregistered names).
    The latter is what makes this work in pure-Python USD test environments
    where Isaac schemas aren't registered, while the former remains the
    canonical accessor in production where Kit is loaded.
    """
    for schema in prim.GetAppliedSchemas():
        if schema == schema_name:
            return True
    try:
        type_info = prim.GetPrimTypeInfo()
        for schema in type_info.GetAppliedAPISchemas():
            if schema == schema_name:
                return True
    except Exception:
        pass
    return False


# Preferred gripper_-prefixed names first; unprefixed spellings remain
# accepted for existing assets. The sample assets author the gripper_ form.
_FORWARD_AXIS_NAMES = ("gripper_forward_axis", "forward_axis")
_GRIP_LINE_NAMES = ("gripper_grip_line", "grip_line")
_MAX_OPENING_NAMES = ("gripper_maxOpening", "custom:maxOpening")
_MAX_PAYLOAD_NAMES = ("gripper_maxPayload", "custom:maxPayload")


def _first_child(prim, names):
    """First existing child prim among the accepted name spellings, or None."""
    for n in names:
        child = prim.GetChild(n)
        if child and child.IsValid():
            return child
    return None


def _read_float_attr_aliases(prim, names):
    """First defined float attribute among the accepted name spellings, or None."""
    for n in names:
        val = _read_float_attr(prim, n)
        if val is not None:
            return val
    return None


def _read_gripper_site(prim) -> Optional[GripperSite]:
    forward = _read_curve_direction(_first_child(prim, _FORWARD_AXIS_NAMES))
    if forward is None:
        return None
    grip = _read_curve_segment(_first_child(prim, _GRIP_LINE_NAMES))
    if grip is None:
        return None
    max_opening = _read_float_attr_aliases(prim, _MAX_OPENING_NAMES)
    if max_opening is None or max_opening <= 0.0:
        return None
    max_payload = _read_float_attr_aliases(prim, _MAX_PAYLOAD_NAMES)
    pose_world = _world_xform(prim)
    if not np.isfinite(pose_world).all():
        return None
    forward_world = _xform_dir(pose_world, forward)
    grip_world = (_xform_point(pose_world, grip[0]), _xform_point(pose_world, grip[1]))
    if not np.isfinite(forward_world).all() or not all(np.isfinite(point).all() for point in grip_world):
        return None
    return GripperSite(
        prim_path=str(prim.GetPath()),
        pose_world_initial=pose_world,
        forward_axis_world=forward_world,
        grip_line_world=grip_world,
        max_opening=float(max_opening),
        max_payload=(float(max_payload) if max_payload is not None and max_payload > 0.0 else None),
    )


def _read_float_attr(prim, name):
    attr = prim.GetAttribute(name)
    if attr is None or not attr.IsDefined():
        return None
    val = attr.Get()
    if val is None:
        return None
    value = float(val)
    return value if np.isfinite(value) else None


def _read_curve_segment(curve_prim):
    if not curve_prim or not curve_prim.IsValid() or not UsdGeom.BasisCurves(curve_prim):
        return None
    pts_attr = curve_prim.GetAttribute("points")
    if not pts_attr or not pts_attr.IsDefined():
        return None
    pts = pts_attr.Get()
    if pts is None or len(pts) < 2:
        return None
    p0 = np.array([pts[0][0], pts[0][1], pts[0][2]], dtype=np.float64)
    p1 = np.array([pts[1][0], pts[1][1], pts[1][2]], dtype=np.float64)
    if not np.isfinite(p0).all() or not np.isfinite(p1).all():
        return None
    return (p0, p1)


def _read_curve_direction(curve_prim):
    seg = _read_curve_segment(curve_prim)
    if seg is None:
        return None
    d = seg[1] - seg[0]
    n = np.linalg.norm(d)
    if n < 1e-9:
        return None
    return d / n


def _world_xform(prim) -> np.ndarray:
    cache = UsdGeom.XformCache()
    return np.array(cache.GetLocalToWorldTransform(prim)).reshape(4, 4)


def _xform_point(m, p):
    h = np.array([p[0], p[1], p[2], 1.0])
    out = h @ m
    return out[:3]


def _xform_dir(m, d):
    h = np.array([d[0], d[1], d[2], 0.0])
    out = h @ m
    n = np.linalg.norm(out[:3])
    return out[:3] if n < 1e-9 else out[:3] / n
