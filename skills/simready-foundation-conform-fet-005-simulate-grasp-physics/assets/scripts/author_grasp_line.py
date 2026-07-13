#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import stat
from typing import Any

from pxr import Gf, Sdf, Usd, UsdGeom, Vt

GUIDE_DISPLAY_COLOR = Gf.Vec3f(float("0.10"), float("0.85"), float("0.20"))

def parse_point(value: str) -> list[float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"Point must be formatted as x,y,z: {value}")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Point contains a non-numeric value: {value}") from exc


def report_payload(
    *,
    asset_path: Path,
    output_path: Path,
    status: str,
    grasp_vector_path: str | None,
    parent_prim_path: str | None,
    points: list[list[float]],
    source_visual_asset: str | None,
    visual_evidence: list[str],
    rationale: str | None,
    coordinate_note: str | None,
    blocked_reasons: list[str],
    needed_inputs: list[str],
    validation_report: str | None,
    validation_status: str | None,
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any]:
    return {
        "asset_path": str(asset_path),
        "output_usd_path": str(output_path),
        "status": status,
        "passed": status == "PASS",
        "blocked": status == "BLOCKED",
        "grasp_vector_path": grasp_vector_path,
        "parent_prim_path": parent_prim_path,
        "points": points,
        "source_visual_asset": source_visual_asset,
        "visual_evidence": visual_evidence,
        "rationale": rationale,
        "coordinate_note": coordinate_note,
        "blocked_reasons": blocked_reasons,
        "needed_inputs": needed_inputs,
        "validation_report": validation_report,
        "validation_status": validation_status,
        "requirements_repaired": ["GSP.001"] if status == "PASS" else [],
        "requirements_blocked": ["GSP.001"] if status == "BLOCKED" else [],
        "warnings": warnings,
        "errors": errors,
        "next_step": "validate-simready-profile",
    }


def write_reports(payload: dict[str, Any], report: Path | None, markdown_report: Path | None) -> None:
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if markdown_report:
        markdown_report.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Grasp Line Authoring Report",
            "",
            f"- Status: `{payload['status']}`",
            f"- Output USD: `{payload['output_usd_path']}`",
            f"- Grasp vector: `{payload['grasp_vector_path']}`",
            f"- Parent prim: `{payload['parent_prim_path']}`",
            f"- Points: `{payload['points']}`",
            f"- Source visual asset: `{payload['source_visual_asset']}`",
            f"- Rationale: {payload['rationale'] or 'Not provided'}",
            f"- Coordinate note: {payload['coordinate_note'] or 'Not provided'}",
            f"- Validation report: `{payload['validation_report']}`",
            f"- Validation status: `{payload['validation_status']}`",
            "",
            "## Visual Evidence",
            "",
        ]
        lines.extend(f"- `{item}`" for item in payload["visual_evidence"])
        if not payload["visual_evidence"]:
            lines.append("- None provided")
        lines.extend([
            "",
            "## Warnings",
            "",
        ])
        lines.extend(f"- {item}" for item in payload["warnings"])
        if not payload["warnings"]:
            lines.append("- None")
        lines.extend(["", "## Blocked Reasons", ""])
        lines.extend(f"- {item}" for item in payload["blocked_reasons"])
        if not payload["blocked_reasons"]:
            lines.append("- None")
        lines.extend(["", "## Needed Inputs", ""])
        lines.extend(f"- {item}" for item in payload["needed_inputs"])
        if not payload["needed_inputs"]:
            lines.append("- None")
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in payload["errors"])
        if not payload["errors"]:
            lines.append("- None")
        lines.append("")
        markdown_report.write_text("\n".join(lines), encoding="utf-8")


def copy_sidecar(asset_path: Path, output_path: Path, force: bool) -> None:
    source_json = asset_path.with_suffix(".json")
    if not source_json.exists():
        return
    target_json = output_path.with_suffix(".json")
    if target_json.exists() and not force:
        return
    shutil.copy2(source_json, target_json)


def ensure_owner_writable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IWUSR)


def needed_inputs_for_block(
    *,
    points: list[list[float]],
    visual_evidence: list[str],
    rationale: str | None,
    coordinate_note: str | None,
) -> list[str]:
    needed: list[str] = []
    if len(points) < 2:
        needed.append("At least two explicit local-space --point x,y,z values selected from visual evidence.")
    if not visual_evidence:
        needed.append("One or more --visual-evidence paths inspected by a vision-capable agent.")
    if not rationale:
        needed.append("A --rationale explaining why the selected region is graspable and what was avoided.")
    if not coordinate_note:
        needed.append("A --coordinate-note explaining how visual evidence maps to authored USD local coordinates.")
    return needed


def next_grasp_name(parent_prim: Usd.Prim) -> str:
    used_names = {child.GetName() for child in parent_prim.GetChildren()}
    for index in range(1, 1000):
        name = f"grasp_identifier_{index:02d}"
        if name not in used_names:
            return name
    raise RuntimeError("No available grasp_identifier_## name below parent prim")


def make_extent(points: list[list[float]], width: float) -> Vt.Vec3fArray:
    pad = max(float(width), 0.0) * 0.5
    mins = [float(points[0][0]), float(points[0][1]), float(points[0][2])]
    maxs = mins.copy()
    for point in points[1:]:
        for index in range(3):
            value = float(point[index])
            if value < mins[index]:
                mins[index] = value
            elif value > maxs[index]:
                maxs[index] = value
    mins = [value - pad for value in mins]
    maxs = [value + pad for value in maxs]
    return Vt.Vec3fArray([Gf.Vec3f(*mins), Gf.Vec3f(*maxs)])


def author_curve(
    *,
    stage: Usd.Stage,
    parent_prim: Usd.Prim,
    name: str,
    points: list[list[float]],
    width: float,
    force: bool,
) -> str:
    if not Sdf.Path.IsValidIdentifier(name):
        raise ValueError(f"Invalid USD prim name: {name}")
    path = parent_prim.GetPath().AppendChild(name)
    existing = stage.GetPrimAtPath(path)
    if existing and existing.IsValid() and existing.GetTypeName() != "BasisCurves":
        raise ValueError(f"Existing prim at {path} is not BasisCurves")
    if existing and existing.IsValid() and not force:
        raise ValueError(f"Grasp vector prim already exists: {path}")

    curve = UsdGeom.BasisCurves.Define(stage, path)
    curve.CreateTypeAttr(UsdGeom.Tokens.linear)
    curve.CreateCurveVertexCountsAttr(Vt.IntArray([len(points)]))
    curve.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*point) for point in points]))
    curve.CreateWidthsAttr(Vt.FloatArray([float(width)]))
    curve.SetWidthsInterpolation(UsdGeom.Tokens.constant)
    curve.CreateExtentAttr(make_extent(points, width))
    curve.CreateDisplayColorAttr(Vt.Vec3fArray([GUIDE_DISPLAY_COLOR]))
    curve.CreateDisplayOpacityAttr(Vt.FloatArray([1.0]))
    UsdGeom.Imageable(curve.GetPrim()).CreatePurposeAttr(UsdGeom.Tokens.guide)
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Author a SimReady FET005 grasp line as BasisCurves.")
    parser.add_argument("asset_path", type=Path)
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--output", type=Path)
    output_group.add_argument("--in-place", action="store_true")
    parser.add_argument("--parent-prim", help="Parent prim for the grasp line. Defaults to the stage default prim.")
    parser.add_argument("--name", help="Grasp prim name. Defaults to the next grasp_identifier_##.")
    parser.add_argument("--point", action="append", type=parse_point, default=[], dest="points")
    parser.add_argument("--width", type=float, default=0.01)
    parser.add_argument("--source-visual-asset", help="Source asset used for visual evidence when different from the authored USD.")
    parser.add_argument("--visual-evidence", action="append", default=[], help="Render, screenshot, or evidence file used to choose the grasp line.")
    parser.add_argument("--rationale", help="Short explanation of why the selected region is graspable.")
    parser.add_argument("--coordinate-note", help="Short note describing any source-to-local coordinate conversion.")
    parser.add_argument("--blocked-reason", action="append", default=[], help="Record a first-class BLOCKED report instead of authoring a grasp line.")
    parser.add_argument("--validation-report", help="Validation report path produced after successful repair, if already available.")
    parser.add_argument("--validation-status", help="Validation status produced after successful repair, if already available.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    asset_path = args.asset_path.resolve()
    output_path = asset_path if args.in_place else args.output.resolve()
    warnings: list[str] = []
    errors: list[str] = []
    blocked_reasons: list[str] = list(args.blocked_reason)
    grasp_path: str | None = None
    parent_path: str | None = args.parent_prim
    points: list[list[float]] = [[float(coord) for coord in point] for point in args.points]

    if len(points) < 2:
        if not blocked_reasons:
            blocked_reasons.append(
                "No grasp line was authored because fewer than two explicit vision-selected --point values were supplied."
            )
    elif points[0] == points[-1]:
        errors.append("The first and last grasp line points must not be identical.")
    if not asset_path.exists():
        errors.append(f"Asset path does not exist: {asset_path}")
    if asset_path.suffix.lower() not in {".usd", ".usda", ".usdc"}:
        errors.append("Asset must be a .usd, .usda, or .usdc root layer.")
    if not blocked_reasons and output_path.exists() and output_path != asset_path and not args.force:
        errors.append(f"Output path already exists: {output_path}")
    if args.name and not args.name.startswith("grasp_identifier"):
        warnings.append("GSP.001 validator expects grasp vector names to start with 'grasp_identifier'.")

    needed_inputs = needed_inputs_for_block(
        points=points,
        visual_evidence=args.visual_evidence,
        rationale=args.rationale,
        coordinate_note=args.coordinate_note,
    )

    if errors or blocked_reasons:
        status = "FAIL" if errors else "BLOCKED"
        payload = report_payload(
            asset_path=asset_path,
            output_path=output_path,
            status=status,
            grasp_vector_path=grasp_path,
            parent_prim_path=parent_path,
            points=points,
            source_visual_asset=args.source_visual_asset,
            visual_evidence=args.visual_evidence,
            rationale=args.rationale,
            coordinate_note=args.coordinate_note,
            blocked_reasons=blocked_reasons,
            needed_inputs=needed_inputs if blocked_reasons else [],
            validation_report=args.validation_report,
            validation_status=args.validation_status,
            warnings=warnings,
            errors=errors,
        )
        write_reports(payload, args.report, args.markdown_report)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if errors else 2

    if output_path != asset_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset_path, output_path)
            ensure_owner_writable(output_path)
            copy_sidecar(asset_path, output_path, args.force)
        except OSError as exc:
            errors.append(f"Failed to stage output asset: {exc}")

    if not errors:
        stage = Usd.Stage.Open(str(output_path))
        if stage is None:
            errors.append(f"Failed to open stage: {output_path}")
        else:
            default_prim = stage.GetDefaultPrim()
            if not default_prim or not default_prim.IsValid():
                errors.append("Stage has no valid default prim.")
            else:
                parent_prim = stage.GetPrimAtPath(args.parent_prim) if args.parent_prim else default_prim
                if not parent_prim or not parent_prim.IsValid():
                    errors.append(f"Parent prim is invalid: {args.parent_prim}")
                elif not parent_prim.GetPath().HasPrefix(default_prim.GetPath()):
                    errors.append("Parent prim must be under the default prim.")
                else:
                    parent_path = str(parent_prim.GetPath())
                    name = args.name or next_grasp_name(parent_prim)
                    try:
                        grasp_path = author_curve(
                            stage=stage,
                            parent_prim=parent_prim,
                            name=name,
                            points=points,
                            width=args.width,
                            force=args.force,
                        )
                        if not stage.GetRootLayer().Save():
                            errors.append("Failed to save root layer.")
                    except Exception as exc:
                        errors.append(str(exc))

    payload = report_payload(
        asset_path=asset_path,
        output_path=output_path,
        status="PASS" if not errors else "FAIL",
        grasp_vector_path=grasp_path,
        parent_prim_path=parent_path,
        points=points,
        source_visual_asset=args.source_visual_asset,
        visual_evidence=args.visual_evidence,
        rationale=args.rationale,
        coordinate_note=args.coordinate_note,
        blocked_reasons=[],
        needed_inputs=[],
        validation_report=args.validation_report,
        validation_status=args.validation_status,
        warnings=warnings,
        errors=errors,
    )
    write_reports(payload, args.report, args.markdown_report)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
