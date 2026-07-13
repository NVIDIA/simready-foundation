#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any, Callable
import zlib

from pxr import Gf, Usd, UsdGeom


Color = tuple[int, int, int]
Point = tuple[float, float, float]
ProjectedPoint = tuple[float, float, float]
ISO_ANGLE_RADIANS = math.radians(38.0)
ISO_COS = math.cos(ISO_ANGLE_RADIANS)
ISO_SIN = math.sin(ISO_ANGLE_RADIANS)
PNG_COMPRESSION_LEVEL = 6


FONT_5X7 = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["11111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "01010", "00100", "00100", "00100", "01010", "10001"],
    "Y": ["10001", "01010", "00100", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "11100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00100", "00100"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
}


def parse_point(value: str) -> Point:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"Point must be formatted as x,y,z: {value}")
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Point contains a non-numeric value: {value}") from exc


def clamp_channel(value: int) -> int:
    return max(0, min(255, value))


class Canvas:
    def __init__(self, width: int, height: int, background: Color = (250, 250, 248)) -> None:
        self.width = width
        self.height = height
        self._color_cache: dict[Color, bytes] = {}
        self.pixels = bytearray(self.color_bytes(background) * (width * height))

    def color_bytes(self, color: Color) -> bytes:
        cached = self._color_cache.get(color)
        if cached is None:
            cached = bytes(clamp_channel(channel) for channel in color)
            self._color_cache[color] = cached
        return cached

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset : offset + 3] = self.color_bytes(color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        x_start = max(0, x0)
        x_end = min(self.width, x1)
        y_start = max(0, y0)
        y_end = min(self.height, y1)
        if x_start >= x_end or y_start >= y_end:
            return
        row = self.color_bytes(color) * (x_end - x_start)
        for y in range(y_start, y_end):
            start = (y * self.width + x_start) * 3
            self.pixels[start : start + len(row)] = row

    def dot(self, x: int, y: int, radius: int, color: Color) -> None:
        radius = max(1, radius)
        if radius == 1:
            self.set_pixel(x, y, color)
            return
        r2 = radius * radius
        for yy in range(y - radius, y + radius + 1):
            for xx in range(x - radius, x + radius + 1):
                if (xx - x) * (xx - x) + (yy - y) * (yy - y) <= r2:
                    self.set_pixel(xx, yy, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color, width: int = 1) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.dot(x0, y0, max(1, width), color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def text(self, x: int, y: int, value: str, color: Color = (30, 30, 30), scale: int = 2) -> None:
        cursor_x = x
        for char in value.upper():
            glyph = FONT_5X7.get(char, FONT_5X7[" "])
            for glyph_y, row in enumerate(glyph):
                for glyph_x, pixel in enumerate(row):
                    if pixel == "1":
                        self.rect(
                            cursor_x + glyph_x * scale,
                            y + glyph_y * scale,
                            cursor_x + (glyph_x + 1) * scale,
                            y + (glyph_y + 1) * scale,
                            color,
                        )
            cursor_x += (len(glyph[0]) + 1) * scale

    def write_png(self, output_path: Path) -> None:
        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        raw = bytearray()
        row_width = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * row_width : (y + 1) * row_width])
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, PNG_COMPRESSION_LEVEL))
            + chunk(b"IEND", b"")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(png)


def collect_mesh_points(stage: Usd.Stage, default_prim: Usd.Prim, max_points_per_mesh: int) -> tuple[list[Point], dict[str, Any]]:
    xform_cache = UsdGeom.XformCache()
    points: list[Point] = []
    mesh_count = 0
    source_point_count = 0
    sampled_point_count = 0

    for prim in Usd.PrimRange(default_prim):
        if prim.GetTypeName() != "Mesh":
            continue
        point_attr = prim.GetAttribute("points")
        mesh_points = point_attr.Get() if point_attr else None
        if mesh_points is None or len(mesh_points) == 0:
            continue

        mesh_count += 1
        source_point_count += len(mesh_points)
        stride = max(1, math.ceil(len(mesh_points) / max(1, max_points_per_mesh)))
        matrix = xform_cache.GetLocalToWorldTransform(prim)
        for point in mesh_points[::stride]:
            world_point = matrix.Transform(point)
            points.append((float(world_point[0]), float(world_point[1]), float(world_point[2])))
            sampled_point_count += 1

    stats = {
        "mesh_count": mesh_count,
        "source_point_count": source_point_count,
        "sampled_point_count": sampled_point_count,
    }
    return points, stats


def points_bounds(points: list[Point]) -> dict[str, list[float]]:
    first = points[0]
    mins = [first[0], first[1], first[2]]
    maxs = [first[0], first[1], first[2]]
    for point in points[1:]:
        for index in range(3):
            value = point[index]
            if value < mins[index]:
                mins[index] = value
            elif value > maxs[index]:
                maxs[index] = value
    return {"min": mins, "max": maxs}


def transform_local_points(stage: Usd.Stage, parent_prim_path: str | None, points: list[Point]) -> tuple[list[Point], str | None]:
    if not points:
        return [], None

    default_prim = stage.GetDefaultPrim()
    parent_prim = stage.GetPrimAtPath(parent_prim_path) if parent_prim_path else default_prim
    if not parent_prim or not parent_prim.IsValid():
        raise ValueError(f"Parent prim is invalid: {parent_prim_path}")

    matrix = UsdGeom.XformCache().GetLocalToWorldTransform(parent_prim)
    transformed = []
    for point in points:
        world_point = matrix.Transform(Gf.Vec3d(*point))
        transformed.append((float(world_point[0]), float(world_point[1]), float(world_point[2])))
    return transformed, str(parent_prim.GetPath())


def project_top_xy(point: Point) -> ProjectedPoint:
    return (point[0], point[1], point[2])


def project_front_xz(point: Point) -> ProjectedPoint:
    return (point[0], point[2], point[1])


def project_side_yz(point: Point) -> ProjectedPoint:
    return (point[1], point[2], point[0])


def project_iso(point: Point) -> ProjectedPoint:
    x, y, z = point
    iso_x = x * ISO_COS - y * ISO_SIN
    iso_y = x * ISO_SIN + y * ISO_COS
    return (iso_x, z + 0.35 * iso_y, iso_y)


def panel_transform(
    bounds: tuple[int, int, int, int], projected: list[ProjectedPoint]
) -> Callable[[ProjectedPoint], tuple[int, int]]:
    x0, y0, x1, y1 = bounds
    first = projected[0]
    amin = amax = first[0]
    bmin = bmax = first[1]
    for point in projected[1:]:
        if point[0] < amin:
            amin = point[0]
        elif point[0] > amax:
            amax = point[0]
        if point[1] < bmin:
            bmin = point[1]
        elif point[1] > bmax:
            bmax = point[1]
    padding = max(42, int(min(x1 - x0, y1 - y0) * 0.11))
    scale = min((x1 - x0 - 2 * padding) / (amax - amin or 1.0), (y1 - y0 - 2 * padding) / (bmax - bmin or 1.0))
    origin_x = (x0 + x1) * 0.5 - (amin + amax) * 0.5 * scale
    origin_y = (y0 + y1) * 0.5 + (bmin + bmax) * 0.5 * scale

    def transform(point: ProjectedPoint) -> tuple[int, int]:
        return (int(origin_x + point[0] * scale), int(origin_y - point[1] * scale))

    return transform


def draw_panel(
    canvas: Canvas,
    *,
    bounds: tuple[int, int, int, int],
    title: str,
    points: list[Point],
    projection: Callable[[Point], ProjectedPoint],
    overlay_points: list[Point],
    point_radius: int,
    line_width: int,
) -> None:
    x0, y0, x1, y1 = bounds
    canvas.rect(x0, y0, x1, y1, (255, 255, 255))
    canvas.rect(x0, y0, x1, y0 + 1, (210, 210, 210))
    canvas.rect(x0, y1 - 1, x1, y1, (210, 210, 210))
    canvas.rect(x0, y0, x0 + 1, y1, (210, 210, 210))
    canvas.rect(x1 - 1, y0, x1, y1, (210, 210, 210))
    canvas.text(x0 + 14, y0 + 12, title)

    projected = [projection(point) for point in points]
    transform = panel_transform(bounds, projected)
    dmin = dmax = projected[0][2]
    for point in projected[1:]:
        if point[2] < dmin:
            dmin = point[2]
        elif point[2] > dmax:
            dmax = point[2]

    projected.sort(key=lambda item: item[2])
    for point in projected:
        depth_t = (point[2] - dmin) / (dmax - dmin or 1.0)
        shade = int(65 + 130 * depth_t)
        x, y = transform(point)
        canvas.dot(x, y, point_radius, (shade, shade, shade))

    if overlay_points:
        projected_overlay = [projection(point) for point in overlay_points]
        screen_overlay = [transform(point) for point in projected_overlay]
        for start, end in zip(screen_overlay, screen_overlay[1:]):
            canvas.line(start[0], start[1], end[0], end[1], (225, 20, 30), line_width)
        for x, y in screen_overlay:
            canvas.dot(x, y, max(3, line_width + 2), (225, 20, 30))


def render_preview(
    *,
    asset_path: Path,
    output_path: Path,
    label: str | None,
    parent_prim_path: str | None,
    overlay_points: list[Point],
    max_points_per_mesh: int,
    width: int,
    height: int,
    point_radius: int,
    line_width: int,
) -> dict[str, Any]:
    stage = Usd.Stage.Open(str(asset_path))
    if stage is None:
        raise RuntimeError(f"Failed to open stage: {asset_path}")
    default_prim = stage.GetDefaultPrim()
    if not default_prim or not default_prim.IsValid():
        raise RuntimeError("Stage has no valid default prim.")

    points, stats = collect_mesh_points(stage, default_prim, max_points_per_mesh)
    if not points:
        raise RuntimeError(f"No mesh points found under default prim: {default_prim.GetPath()}")

    overlay_world_points, resolved_parent = transform_local_points(stage, parent_prim_path, overlay_points)

    canvas = Canvas(width, height)
    asset_label = label or asset_path.stem.replace("_", " ")
    canvas.text(20, 8, asset_label[:120])

    margin = 20
    header = 40
    gap = 40
    panel_width = (width - 2 * margin - gap) // 2
    panel_height = (height - header - margin - gap) // 2
    left = margin
    right = margin + panel_width + gap
    top = header
    bottom = header + panel_height + gap

    draw_panel(
        canvas,
        bounds=(left, top, left + panel_width, top + panel_height),
        title="TOP XY",
        points=points,
        projection=project_top_xy,
        overlay_points=overlay_world_points,
        point_radius=point_radius,
        line_width=line_width,
    )
    draw_panel(
        canvas,
        bounds=(right, top, right + panel_width, top + panel_height),
        title="FRONT XZ",
        points=points,
        projection=project_front_xz,
        overlay_points=overlay_world_points,
        point_radius=point_radius,
        line_width=line_width,
    )
    draw_panel(
        canvas,
        bounds=(left, bottom, left + panel_width, bottom + panel_height),
        title="SIDE YZ",
        points=points,
        projection=project_side_yz,
        overlay_points=overlay_world_points,
        point_radius=point_radius,
        line_width=line_width,
    )
    draw_panel(
        canvas,
        bounds=(right, bottom, right + panel_width, bottom + panel_height),
        title="ISO",
        points=points,
        projection=project_iso,
        overlay_points=overlay_world_points,
        point_radius=point_radius,
        line_width=line_width,
    )

    canvas.write_png(output_path)
    return {
        "asset_path": str(asset_path),
        "output_preview_path": str(output_path),
        "status": "PASS",
        "default_prim": str(default_prim.GetPath()),
        "parent_prim": resolved_parent,
        "mesh_count": stats["mesh_count"],
        "source_point_count": stats["source_point_count"],
        "sampled_point_count": stats["sampled_point_count"],
        "bounds": points_bounds(points),
        "overlay_points_local": [list(point) for point in overlay_points],
        "overlay_points_world": [list(point) for point in overlay_world_points],
        "views": ["TOP XY", "FRONT XZ", "SIDE YZ", "ISO"],
    }


def write_report(report_path: Path | None, payload: dict[str, Any]) -> None:
    if report_path is None:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a four-panel USD point-cloud preview for FET005 grasp selection.")
    parser.add_argument("asset_path", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--label", help="Optional title rendered above the panels.")
    parser.add_argument("--parent-prim", help="Prim whose local space contains --point values. Defaults to stage default prim.")
    parser.add_argument("--point", action="append", default=[], type=parse_point, help="Optional local-space grasp point to overlay. Use --point=x,y,z for negative values.")
    parser.add_argument("--max-points-per-mesh", type=int, default=120000)
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--point-radius", type=int, default=1)
    parser.add_argument("--line-width", type=int, default=2)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        payload = render_preview(
            asset_path=args.asset_path.resolve(),
            output_path=args.output.resolve(),
            label=args.label,
            parent_prim_path=args.parent_prim,
            overlay_points=args.point,
            max_points_per_mesh=args.max_points_per_mesh,
            width=args.width,
            height=args.height,
            point_radius=args.point_radius,
            line_width=args.line_width,
        )
    except Exception as exc:
        payload = {
            "asset_path": str(args.asset_path.resolve()),
            "output_preview_path": str(args.output.resolve()),
            "status": "FAIL",
            "errors": [str(exc)],
        }
        write_report(args.report, payload)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    write_report(args.report, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
