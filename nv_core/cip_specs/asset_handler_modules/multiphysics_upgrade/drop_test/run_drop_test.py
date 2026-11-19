# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Run a referenced SimReady prop through a simple ovphysx drop test.

The prop's rigid bodies are discovered from the composed stage rather than
assumed to sit at the reference root, so single-body and multibody props (which
carry PhysicsRigidBodyAPI on each part under Geometry) both work.
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ovphysx import OVPHYSX_TENSOR_RIGID_BODY_POSE_F32, PhysX
from pxr import Usd, UsdPhysics

PROP_ASSET = "@./prop.usd@"
PROP_PRIM_PATH = "/DropTest/Prop"
TEMPLATE_PATH = Path(__file__).with_name("drop_test_template.usda")
TEMPLATE_VARIANT = 'variants = {string PhysX = "Enabled"}'

RUNTIME_VARIANTS = ("PhysX", "Newton", "MuJoCo", "none")

# A body must lose this much height to count as dropped, and must never sink
# this far below the ground collider (which would mean it tunneled through).
FELL_MIN_DROP_M = 0.1
FLOOR_LIMIT_M = -0.5


@dataclass
class BodyTrack:
    """Start, end, and lowest height for one simulated rigid body."""

    name: str
    initial_z: float
    final_z: float
    min_z: float


def make_scene(prop_usd: Path, output_usda: Path, variant: str) -> None:
    """Write the fixture with a relative reference to ``prop_usd``."""
    prop_usd = prop_usd.resolve()
    output_usda = output_usda.resolve()
    output_usda.parent.mkdir(parents=True, exist_ok=True)

    relative_prop = os.path.relpath(prop_usd, output_usda.parent).replace("\\", "/")
    if not relative_prop.startswith("."):
        relative_prop = f"./{relative_prop}"
    if "@" in relative_prop:
        raise ValueError(f"USD asset paths containing '@' are unsupported: {prop_usd}")

    selection = "" if variant == "none" else f'variants = {{string {variant} = "Enabled"}}'
    scene_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    scene_text = scene_text.replace(PROP_ASSET, f"@{relative_prop}@")
    scene_text = scene_text.replace(TEMPLATE_VARIANT, selection)
    output_usda.write_text(scene_text, encoding="utf-8")


def find_rigid_bodies(scene_usda: Path) -> list[str]:
    """Return the prop's enabled rigid-body prim paths, outermost first.

    Instance proxies are excluded: PhysX cannot address a prim inside a
    prototype individually, so only the instanceable root is bindable.
    """
    stage = Usd.Stage.Open(str(scene_usda))
    if stage is None:
        raise RuntimeError(f"Could not open fixture stage: {scene_usda}")

    prop = stage.GetPrimAtPath(PROP_PRIM_PATH)
    if not prop:
        raise RuntimeError(f"Fixture is missing {PROP_PRIM_PATH}")

    paths: list[str] = []
    for prim in Usd.PrimRange(prop, Usd.TraverseInstanceProxies(Usd.PrimIsActive)):
        if prim.IsInstanceProxy() or not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        enabled = prim.GetAttribute("physics:rigidBodyEnabled")
        if enabled and enabled.HasAuthoredValue() and not enabled.Get():
            continue
        paths.append(prim.GetPath().pathString)
    return paths


def read_poses(binding, poses: np.ndarray) -> np.ndarray:
    """Read the pose tensor and return it as a 2D ``[N, 7]`` view."""
    binding.read(poses)
    return poses.reshape(-1, poses.shape[-1])


def run_drop_test(
    scene_usda: Path,
    csv_path: Path,
    *,
    steps: int,
    dt: float,
    realtime: bool,
) -> bool:
    """Simulate the fixture and return whether every prop body fell cleanly."""
    names = find_rigid_bodies(scene_usda)
    if not names:
        raise RuntimeError(
            f"No rigid bodies found under {PROP_PRIM_PATH}. The referenced asset must "
            "apply PhysicsRigidBodyAPI to its body prims (a multibody prop carries it "
            "on each part under Geometry, not on the asset root)."
        )
    print(f"bodies:    {len(names)}")
    for name in names:
        print(f"  {name}")

    # CPU simulation keeps the pose tensors host-side, which is what the numpy
    # read path below requires; a GPU instance hands back device tensors.
    physx = PhysX(device="cpu")
    binding = None
    usd_handle = None

    try:
        usd_handle, _ = physx.add_usd(str(scene_usda))
        physx.wait_all()

        binding = physx.create_tensor_binding(
            prim_paths=names,
            tensor_type=OVPHYSX_TENSOR_RIGID_BODY_POSE_F32,
        )
        if binding.count != len(names):
            raise RuntimeError(
                f"PhysX bound {binding.count} of {len(names)} rigid bodies. The unbound "
                "prims were not parsed as rigid bodies; check that each has a collider."
            )

        poses = np.zeros(binding.shape, dtype=np.float32)
        initial = read_poses(binding, poses)[:, 2].copy()
        lowest = initial.copy()

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        wall_start = time.monotonic()

        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["step", "time", "body", "px", "py", "pz", "qx", "qy", "qz", "qw"])

            for step in range(steps + 1):
                if step > 0:
                    physx.step(dt, step * dt)
                    physx.wait_all()

                rows = read_poses(binding, poses)
                np.minimum(lowest, rows[:, 2], out=lowest)
                for index, name in enumerate(names):
                    writer.writerow(
                        [step, step * dt, name, *[float(value) for value in rows[index]]]
                    )

                if realtime:
                    remaining = step * dt - (time.monotonic() - wall_start)
                    if remaining > 0:
                        time.sleep(remaining)

            final = rows[:, 2].copy()

        tracks = [
            BodyTrack(
                name=names[index],
                initial_z=float(initial[index]),
                final_z=float(final[index]),
                min_z=float(lowest[index]),
            )
            for index in range(len(names))
        ]

        fell = all(track.final_z < track.initial_z - FELL_MIN_DROP_M for track in tracks)
        on_floor = all(track.min_z > FLOOR_LIMIT_M for track in tracks)

        print("\nresults:")
        for track in tracks:
            print(
                f"  {track.name}: z {track.initial_z:.4f} -> {track.final_z:.4f} "
                f"(min {track.min_z:.4f})"
            )
        print(f"poses:     {csv_path}")
        if not fell:
            print("note:      a body did not drop; check gravity, mass, and colliders")
        if not on_floor:
            print("note:      a body passed through the ground collider")
        print(f"result:    {'PASS' if fell and on_floor else 'FAIL'}")
        return fell and on_floor
    finally:
        if binding is not None:
            binding.destroy()
        if usd_handle is not None:
            physx.remove_usd(usd_handle)
        physx.release()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prop_usd", type=Path, help="SimReady prop root USD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("drop_test_output"),
        help="Generated fixture and pose CSV directory",
    )
    parser.add_argument(
        "--variant",
        choices=RUNTIME_VARIANTS,
        default="PhysX",
        help="Runtime variant to enable on the prop, or 'none' for the neutral base",
    )
    parser.add_argument("--steps", type=int, default=300, help="Simulation steps")
    parser.add_argument("--dt", type=float, default=1.0 / 60.0, help="Step duration in seconds")
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Throttle simulation to wall-clock speed (does not create a viewer)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prop_usd = args.prop_usd.resolve()
    if not prop_usd.is_file():
        raise FileNotFoundError(prop_usd)
    if args.steps <= 0 or args.dt <= 0:
        raise ValueError("--steps and --dt must be positive")

    output_dir = args.output_dir.resolve()
    scene_usda = output_dir / "drop_test_scene.usda"
    csv_path = output_dir / "poses.csv"
    make_scene(prop_usd, scene_usda, args.variant)
    print(f"scene:     {scene_usda}")
    print(f"variant:   {args.variant}")

    passed = run_drop_test(
        scene_usda,
        csv_path,
        steps=args.steps,
        dt=args.dt,
        realtime=args.realtime,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
