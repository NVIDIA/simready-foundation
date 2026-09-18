#!/usr/bin/env python3
"""Derive SimReady_Metadata provenance fields from a USD asset (FET_033_STANDARD / SR.003).

This helper only computes the fields that can be derived deterministically from
the stage:

- ``asset_extents`` (float3, meters, XYZ): world-space bounding-box size of the
  default prim, converted to meters using the stage ``metersPerUnit``.
- ``rigid_body_count`` (int): number of prims with ``UsdPhysicsRigidBodyAPI``
  applied.
- ``mass`` (float, kilograms): sum of authored ``physics:mass`` values on prims
  with ``UsdPhysicsMassAPI``. Reported as ``null`` (needs input) when no mass is
  authored -- this script never fabricates a mass.

``qcode`` (Wikidata Q-Code) is derived from the asset's default (root) prim
Wikidata semantic labels -- both the newer ``UsdSemantics`` form
(``semantics:labels:<taxonomy>`` where the taxonomy name contains ``qcode``)
and the legacy multi-apply ``SemanticsAPI`` form
(``semantic:<instance>:params:semanticData`` whose type is ``wikidata_qcode``).
Pass ``--set qcode=<Qxxxx>`` to override the authored value or to supply one when
the asset carries no Wikidata semantic.

The remaining string fields (``author``, ``asset_name``, ``asset_type``,
``asset_license``, ``category``, ``source_file``, ``usd_date_generated``) cannot
be derived and are NOT invented. Supply them explicitly with repeated
``--set KEY=VALUE`` flags when stamping.

By default the script only reports (``--dry-run``). Pass ``--output PATH`` or
``--in-place`` to stamp the derived (and any ``--set``) fields into the root
layer ``customLayerData.SimReady_Metadata`` dictionary. Existing values are kept
unless ``--overwrite`` is given.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
from pathlib import Path
from typing import Any

from pxr import Gf, Usd, UsdGeom, UsdPhysics

# Fields this script is allowed to derive from the stage.
DERIVED_FIELDS = ("asset_extents", "rigid_body_count", "mass", "qcode")

# Wikidata Q-Code: a capital "Q" followed by one or more digits (matches the
# SR.003 validator contract). Used only for an advisory warning on odd values.
QCODE_RE = re.compile(r"^Q[0-9]+$")

# Material-agnostic plausibility bounds for implied density (kg/m^3). No real
# solid material sits outside this range, so an implied density beyond it almost
# always means a wrong mass or a unit error (kg<->g, cm^3 treated as m^3, etc.).
# Values inside the range are left to agent/manual judgement per object type.
DENSITY_MIN_PLAUSIBLE = 1.0        # lighter than ~any real solid/hollow shell
DENSITY_MAX_PLAUSIBLE = 23000.0    # denser than osmium (~22590 kg/m^3)

# String fields callers must supply with --set; they cannot be derived here.
# ``qcode`` is intentionally NOT in this list: it is derived from the root prim
# Wikidata semantics (see derive_qcode) and only needs --set as an override.
SETTABLE_STRING_FIELDS = (
    "author",
    "asset_name",
    "asset_type",
    "asset_license",
    "category",
    "source_file",
    "usd_date_generated",
)


def parse_set(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"--set expects KEY=VALUE, got: {value}")
    key, _, val = value.partition("=")
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError(f"--set key must be non-empty: {value}")
    return key, val


def _first_token(value: Any) -> str | None:
    """Return the first non-empty string from a token/token[] semantic value."""
    if value is None:
        return None
    try:
        items = list(value)
    except TypeError:
        items = [value]
    for item in items:
        text = str(item).strip()
        if text:
            return text
    return None


def derive_qcode(prim: Usd.Prim) -> tuple[str | None, str | None]:
    """Read the Wikidata Q-Code from a prim's authored semantics.

    Supports both semantic encodings seen on SimReady root prims:

    1. Newer ``UsdSemantics`` (``SemanticsLabelsAPI``): a ``token[]`` attribute
       ``semantics:labels:<taxonomy>`` whose taxonomy name contains ``qcode``.
    2. Legacy multi-apply ``SemanticsAPI``: a ``string`` attribute
       ``semantic:<instance>:params:semanticData`` whose sibling
       ``...:params:semanticType`` (or the instance name) marks it as a
       ``wikidata_qcode``.

    Returns ``(qcode, source_attr_name)`` or ``(None, None)`` when the prim
    carries no Wikidata Q-Code semantic.
    """
    if not prim or not prim.IsValid():
        return None, None

    # 1) Newer UsdSemantics labels form (preferred).
    for attr in prim.GetAttributes():
        name = attr.GetName()
        if name.startswith("semantics:labels:") and "qcode" in name.lower():
            token = _first_token(attr.Get())
            if token:
                return token, name

    # 2) Legacy multi-apply SemanticsAPI form.
    suffix = ":params:semanticData"
    for attr in prim.GetAttributes():
        name = attr.GetName()
        if not (name.startswith("semantic:") and name.endswith(suffix)):
            continue
        instance = name[len("semantic:") : -len(suffix)]
        type_attr = prim.GetAttribute(f"semantic:{instance}:params:semanticType")
        type_val = type_attr.Get() if type_attr else None
        is_qcode = "qcode" in instance.lower() or (
            isinstance(type_val, str) and "qcode" in type_val.lower()
        )
        if not is_qcode:
            continue
        value = attr.Get()
        if isinstance(value, str) and value.strip():
            return value.strip(), name

    return None, None


def compute_extents_meters(stage: Usd.Stage, prim: Usd.Prim) -> tuple[list[float] | None, str | None]:
    """Return [x, y, z] size in meters for the prim's world bound, or (None, note)."""
    purposes = [UsdGeom.Tokens.default_, UsdGeom.Tokens.render]
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), purposes, useExtentsHint=True)
    bound = cache.ComputeWorldBound(prim)
    rng = bound.ComputeAlignedRange()
    if rng.IsEmpty():
        return None, "No boundable geometry under the default prim; asset_extents could not be computed."
    size = rng.GetSize()
    mpu = float(UsdGeom.GetStageMetersPerUnit(stage) or 1.0)
    return [float(size[0]) * mpu, float(size[1]) * mpu, float(size[2]) * mpu], None


def count_rigid_bodies(stage: Usd.Stage) -> int:
    count = 0
    for prim in stage.Traverse():
        has = False
        try:
            has = prim.HasAPI(UsdPhysics.RigidBodyAPI)
        except Exception:
            has = False
        # By-name fallback in case the physics plugin is not registered.
        if not has and "PhysicsRigidBodyAPI" in prim.GetAppliedSchemas():
            has = True
        if has:
            count += 1
    return count


def sum_authored_mass(stage: Usd.Stage) -> tuple[float | None, int]:
    masses: list[float] = []
    for prim in stage.Traverse():
        has_mass_api = False
        try:
            has_mass_api = prim.HasAPI(UsdPhysics.MassAPI)
        except Exception:
            has_mass_api = False
        if not has_mass_api and "PhysicsMassAPI" not in prim.GetAppliedSchemas():
            continue
        attr = prim.GetAttribute("physics:mass")
        if attr and attr.HasAuthoredValue():
            value = attr.Get()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                masses.append(float(value))
    if not masses:
        return None, 0
    return float(sum(masses)), len(masses)


def mesh_volume_stage_units(mesh: UsdGeom.Mesh, xform_cache: UsdGeom.XformCache) -> float | None:
    """Signed solid volume of a mesh in stage units (world space).

    Sums per-triangle tetrahedron volumes from the origin: V = (1/6) sum a.(b x c).
    Assumes a closed, consistently wound mesh; the result is the enclosed volume
    (so a hollow shell reports its enclosed volume, which is expected). Returns
    None when the mesh has no usable topology.
    """
    points = mesh.GetPointsAttr().Get()
    counts = mesh.GetFaceVertexCountsAttr().Get()
    indices = mesh.GetFaceVertexIndicesAttr().Get()
    if not points or not counts or not indices:
        return None
    matrix = xform_cache.GetLocalToWorldTransform(mesh.GetPrim())
    world = [matrix.Transform(Gf.Vec3d(p[0], p[1], p[2])) for p in points]
    vol6 = 0.0
    cursor = 0
    for count in counts:
        if count >= 3:
            i0 = indices[cursor]
            for tri in range(1, count - 1):
                a = world[i0]
                b = world[indices[cursor + tri]]
                c = world[indices[cursor + tri + 1]]
                vol6 += (
                    a[0] * (b[1] * c[2] - b[2] * c[1])
                    - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])
                )
        cursor += count
    return abs(vol6) / 6.0


def _nearest_body_path(prim: Usd.Prim, body_paths: set[str]) -> str | None:
    node = prim
    while node and node.IsValid():
        if str(node.GetPath()) in body_paths:
            return str(node.GetPath())
        node = node.GetParent()
    return None


def build_mass_report(
    stage: Usd.Stage,
    mpu: float,
    total_mass: float | None,
    expected_min: float | None,
    expected_max: float | None,
    rationale: str | None,
) -> dict[str, Any]:
    """Report per-body and aggregate volume + implied density as facts for an agent.

    The plausibility verdict is intentionally advisory (warning-level): a
    deterministic check only flags implied densities outside the physically
    possible range, and the agent-supplied [expected_min, expected_max] range is
    compared but never turned into a hard failure here.
    """
    scale = float(mpu) ** 3
    xform_cache = UsdGeom.XformCache()

    body_paths: set[str] = set()
    body_mass: dict[str, float | None] = {}
    for prim in stage.Traverse():
        is_body = False
        try:
            is_body = prim.HasAPI(UsdPhysics.RigidBodyAPI)
        except Exception:
            is_body = False
        if not is_body and "PhysicsRigidBodyAPI" not in prim.GetAppliedSchemas():
            continue
        path = str(prim.GetPath())
        body_paths.add(path)
        attr = prim.GetAttribute("physics:mass")
        value = attr.Get() if attr and attr.HasAuthoredValue() else None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = None
        body_mass[path] = float(value) if value is not None else None

    body_volume: dict[str, float] = {path: 0.0 for path in body_paths}
    total_volume = 0.0
    unassigned_volume = 0.0
    warnings: list[str] = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        vol = mesh_volume_stage_units(UsdGeom.Mesh(prim), xform_cache)
        if vol is None:
            continue
        vol_m3 = vol * scale
        total_volume += vol_m3
        owner = _nearest_body_path(prim, body_paths)
        if owner is None:
            unassigned_volume += vol_m3
        else:
            body_volume[owner] += vol_m3

    def implied(mass: float | None, volume: float | None) -> float | None:
        if mass is None or not volume or volume <= 0:
            return None
        return mass / volume

    bodies = []
    for path in sorted(body_paths):
        mass = body_mass.get(path)
        volume = body_volume.get(path, 0.0)
        density = implied(mass, volume)
        if density is not None and not (DENSITY_MIN_PLAUSIBLE <= density <= DENSITY_MAX_PLAUSIBLE):
            warnings.append(
                f"{path}: implied density {density:.1f} kg/m^3 is outside the plausible "
                f"[{DENSITY_MIN_PLAUSIBLE:g}, {DENSITY_MAX_PLAUSIBLE:g}] range; likely a mass or unit error."
            )
        bodies.append({
            "path": path,
            "mass": mass,
            "volume_m3": volume,
            "implied_density": density,
        })

    overall_density = implied(total_mass, total_volume)
    if overall_density is not None and not (DENSITY_MIN_PLAUSIBLE <= overall_density <= DENSITY_MAX_PLAUSIBLE):
        warnings.append(
            f"aggregate: implied density {overall_density:.1f} kg/m^3 is outside the plausible "
            f"[{DENSITY_MIN_PLAUSIBLE:g}, {DENSITY_MAX_PLAUSIBLE:g}] range; likely a mass or unit error."
        )

    verdict = "unknown"
    if expected_min is not None or expected_max is not None:
        lo = expected_min if expected_min is not None else 0.0
        hi = expected_max if expected_max is not None else float("inf")
        if total_mass is None:
            verdict = "no_authored_mass"
        elif lo <= total_mass <= hi:
            verdict = "plausible"
        else:
            # How far outside the band, as a multiplicative factor.
            if total_mass < lo:
                factor = lo / total_mass if total_mass > 0 else float("inf")
            else:
                factor = total_mass / hi if hi > 0 else float("inf")
            verdict = "implausible" if factor >= 100 else "review"
            warnings.append(
                f"aggregate authored mass {total_mass} kg is outside the agent-expected "
                f"[{expected_min}, {expected_max}] kg range (~{factor:.1f}x); manual review."
            )

    return {
        "total_mass_kg": total_mass,
        "total_volume_m3": total_volume,
        "unassigned_volume_m3": unassigned_volume,
        "implied_density_kg_m3": overall_density,
        "expected_mass_min_kg": expected_min,
        "expected_mass_max_kg": expected_max,
        "rationale": rationale,
        "verdict": verdict,
        "bodies": bodies,
        "warnings": warnings,
    }


def ensure_owner_writable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IWUSR)


def write_reports(payload: dict[str, Any], report: Path | None, markdown_report: Path | None) -> None:
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if markdown_report:
        markdown_report.parent.mkdir(parents=True, exist_ok=True)
        derived = payload["derived"]
        lines = [
            "# SimReady Metadata Extraction Report",
            "",
            f"- Status: `{payload['status']}`",
            f"- Input: `{payload['asset_path']}`",
            f"- Output: `{payload['output_path']}`",
            f"- Stamped: `{payload['stamped']}`",
            f"- metersPerUnit: `{payload['meters_per_unit']}`",
            "",
            "## Derived Fields",
            "",
            f"- asset_extents (m): `{derived['asset_extents']}`",
            f"- rigid_body_count: `{derived['rigid_body_count']}`",
            f"- mass (kg): `{derived['mass']}`",
            f"- qcode: `{derived.get('qcode')}`",
            "",
            "## Needs Input (not derivable here)",
            "",
        ]
        needs = payload["needs_input"]
        lines.extend(f"- {item}" for item in needs) if needs else lines.append("- None")
        mass_check = payload.get("mass_check")
        if mass_check:
            lines.extend([
                "",
                "## Mass Plausibility (advisory)",
                "",
                f"- Verdict: `{mass_check['verdict']}`",
                f"- Total mass (kg): `{mass_check['total_mass_kg']}`",
                f"- Total volume (m^3): `{mass_check['total_volume_m3']}`",
                f"- Implied density (kg/m^3): `{mass_check['implied_density_kg_m3']}`",
                f"- Expected range (kg): `[{mass_check['expected_mass_min_kg']}, {mass_check['expected_mass_max_kg']}]`",
                f"- Rationale: {mass_check['rationale'] or 'Not provided'}",
                "",
                "### Per-Body",
                "",
            ])
            for body in mass_check["bodies"]:
                lines.append(
                    f"- `{body['path']}`: mass=`{body['mass']}` kg, "
                    f"volume=`{body['volume_m3']}` m^3, "
                    f"implied_density=`{body['implied_density']}` kg/m^3"
                )
            if not mass_check["bodies"]:
                lines.append("- No rigid bodies found")
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in payload["warnings"]) if payload["warnings"] else lines.append("- None")
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"]) if payload["errors"] else lines.append("- None")
        lines.append("")
        markdown_report.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive (and optionally stamp) SimReady_Metadata fields from a USD asset."
    )
    parser.add_argument("asset_path", type=Path)
    out_group = parser.add_mutually_exclusive_group(required=True)
    out_group.add_argument("--output", type=Path, help="Stage a copy here and stamp derived fields into it.")
    out_group.add_argument("--in-place", action="store_true", help="Stamp derived fields into the source asset.")
    out_group.add_argument("--dry-run", action="store_true", help="Only report derived fields; do not write.")
    parser.add_argument(
        "--set",
        action="append",
        type=parse_set,
        default=[],
        dest="sets",
        metavar="KEY=VALUE",
        help="Also stamp a caller-supplied field (e.g. --set qcode=Q42177). Repeatable.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing metadata values.")
    parser.add_argument("--force", action="store_true", help="Allow writing over an existing --output file.")
    parser.add_argument(
        "--expected-mass-min",
        type=float,
        help="Agent-estimated lower bound (kg) of a plausible real-world mass for this asset.",
    )
    parser.add_argument(
        "--expected-mass-max",
        type=float,
        help="Agent-estimated upper bound (kg) of a plausible real-world mass for this asset.",
    )
    parser.add_argument(
        "--mass-rationale",
        help="Short agent explanation of how the expected mass range was chosen (object type, material, size).",
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    asset_path = args.asset_path.resolve()
    warnings: list[str] = []
    errors: list[str] = []

    if not asset_path.exists():
        errors.append(f"Asset path does not exist: {asset_path}")
    if asset_path.suffix.lower() not in {".usd", ".usda", ".usdc"}:
        errors.append("Asset must be a .usd, .usda, or .usdc root layer.")

    if errors:
        payload = _payload(asset_path, asset_path, False, None, {}, [], warnings, errors)
        write_reports(payload, args.report, args.markdown_report)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    # Read from the source; write to output when stamping.
    read_stage = Usd.Stage.Open(str(asset_path))
    if read_stage is None:
        errors.append(f"Failed to open stage: {asset_path}")
        payload = _payload(asset_path, asset_path, False, None, {}, [], warnings, errors)
        write_reports(payload, args.report, args.markdown_report)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    default_prim = read_stage.GetDefaultPrim()
    root_prim = default_prim if (default_prim and default_prim.IsValid()) else read_stage.GetPseudoRoot()
    if not default_prim or not default_prim.IsValid():
        warnings.append("Stage has no valid default prim; extents computed over the whole stage.")

    mpu = UsdGeom.GetStageMetersPerUnit(read_stage) or 1.0
    extents, extents_note = compute_extents_meters(read_stage, root_prim)
    if extents_note:
        warnings.append(extents_note)
    rigid_body_count = count_rigid_bodies(read_stage)
    mass, mass_body_count = sum_authored_mass(read_stage)

    set_keys = {key for key, _ in args.sets}
    qcode, qcode_source = derive_qcode(root_prim)
    if qcode is not None and QCODE_RE.match(qcode) is None:
        warnings.append(
            f"Derived qcode {qcode!r} (from {qcode_source}) is not a Wikidata Q-Code "
            "(expected 'Q' + digits); stamping it anyway, but SR.003 will reject it."
        )
    # An explicit --set qcode wins: leave derived qcode out so the --set value is
    # the one that gets stamped, without an overwrite conflict.
    stamp_qcode = None if "qcode" in set_keys else qcode

    derived: dict[str, Any] = {
        "asset_extents": extents,
        "rigid_body_count": rigid_body_count,
        "mass": mass,
        "qcode": stamp_qcode,
    }

    mass_check = build_mass_report(
        read_stage,
        mpu,
        mass,
        args.expected_mass_min,
        args.expected_mass_max,
        args.mass_rationale,
    )
    warnings.extend(mass_check["warnings"])

    needs_input: list[str] = []
    if extents is None:
        needs_input.append("asset_extents: no boundable geometry found; provide or fix geometry.")
    if mass is None:
        needs_input.append("mass: no authored physics:mass found; author UsdPhysicsMassAPI or supply --set mass=<kg>.")
    if qcode is None and "qcode" not in set_keys:
        needs_input.append(
            "qcode: no Wikidata Q-Code semantic on the root prim; author "
            "SemanticsLabelsAPI:wikidata_qcode or supply --set qcode=<Qxxxx>."
        )
    for field in SETTABLE_STRING_FIELDS:
        if field not in set_keys:
            needs_input.append(f"{field}: string field; supply with --set {field}=<value>.")

    stamped = False
    output_path = asset_path
    if not args.dry_run:
        output_path = asset_path if args.in_place else args.output.resolve()
        if output_path != asset_path and output_path.exists() and not args.force:
            errors.append(f"Output path already exists: {output_path}")
        if not errors:
            try:
                if output_path != asset_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(asset_path, output_path)
                    ensure_owner_writable(output_path)
                stamped = _stamp(
                    output_path=output_path,
                    derived=derived,
                    sets=args.sets,
                    overwrite=args.overwrite,
                    warnings=warnings,
                    errors=errors,
                )
            except Exception as exc:  # noqa: BLE001 - surface any USD/IO failure in the report
                errors.append(f"Failed to stamp metadata: {exc}")

    status = "FAIL" if errors else ("STAMPED" if stamped else "REPORTED")
    payload = _payload(asset_path, output_path, stamped, mpu, derived, needs_input, warnings, errors)
    payload["status"] = status
    payload["mass_body_count"] = mass_body_count
    payload["mass_check"] = mass_check
    write_reports(payload, args.report, args.markdown_report)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if errors else 0


def _stamp(
    *,
    output_path: Path,
    derived: dict[str, Any],
    sets: list[tuple[str, str]],
    overwrite: bool,
    warnings: list[str],
    errors: list[str],
) -> bool:
    stage = Usd.Stage.Open(str(output_path))
    if stage is None:
        errors.append(f"Failed to open output stage: {output_path}")
        return False
    root_layer = stage.GetRootLayer()
    custom = dict(root_layer.customLayerData)
    meta = dict(custom.get("SimReady_Metadata", {}))

    def put(key: str, value: Any) -> None:
        if value is None:
            return
        if key in meta and not overwrite:
            warnings.append(f"Kept existing SimReady_Metadata['{key}']; pass --overwrite to replace.")
            return
        meta[key] = value

    if derived.get("asset_extents") is not None:
        ext = derived["asset_extents"]
        put("asset_extents", Gf.Vec3f(float(ext[0]), float(ext[1]), float(ext[2])))
    put("rigid_body_count", int(derived["rigid_body_count"]))
    if derived.get("mass") is not None:
        put("mass", float(derived["mass"]))
    if derived.get("qcode") is not None:
        put("qcode", str(derived["qcode"]))
    for key, val in sets:
        put(key, val)

    custom["SimReady_Metadata"] = meta
    root_layer.customLayerData = custom
    if not root_layer.Save():
        errors.append("Failed to save root layer after stamping metadata.")
        return False
    return True


def _payload(
    asset_path: Path,
    output_path: Path,
    stamped: bool,
    mpu: float | None,
    derived: dict[str, Any],
    needs_input: list[str],
    warnings: list[str],
    errors: list[str],
    mass_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "asset_path": str(asset_path),
        "output_path": str(output_path),
        "stamped": stamped,
        "meters_per_unit": mpu,
        "derived": {
            "asset_extents": derived.get("asset_extents"),
            "rigid_body_count": derived.get("rigid_body_count"),
            "mass": derived.get("mass"),
            "qcode": derived.get("qcode"),
        },
        "needs_input": needs_input,
        "requirement": "SR.003",
        "mass_check": mass_check,
        "warnings": warnings,
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())
