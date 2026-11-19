# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for multiphysics_upgrade core helpers and adapter registrations."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asset_handler_modules.multiphysics_upgrade import (  # noqa: E402
    core,
    edges,
    minimal_standard_0_1_0_to_1_0_1,
    rigid_body_physx_0_1_0_to_standard_0_2_0,
)
from asset_handler_modules.multiphysics_upgrade.runner import build_plan  # noqa: E402
from asset_handler_modules.multiphysics_upgrade.runner import main as runner_main  # noqa: E402


def _write_unibody_physx_package(package: Path, usd_name: str = "sm_test_prop_01.usda") -> Path:
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / usd_name
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/RootNode/Geometry/mesh")
    mesh.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
    mesh.CreateFaceVertexCountsAttr([3])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
    mesh.CreateNormalsAttr([Gf.Vec3f(0, 0, 1), Gf.Vec3f(0, 0, 1), Gf.Vec3f(0, 0, 1)])
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.MassAPI.Apply(root.GetPrim())
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
    mesh.GetPrim().CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token).Set("sdf")
    mesh.GetPrim().AddAppliedSchema("PhysxCollisionAPI")
    mesh.GetPrim().AddAppliedSchema("PhysxSDFMeshCollisionAPI")
    root.GetPrim().AddAppliedSchema("PhysxRigidBodyAPI")

    from pxr import UsdShade

    material = UsdShade.Material.Define(stage, "/RootNode/Looks/PhysMat")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())

    stage.GetRootLayer().Save()
    return usd_path


def _write_unibody_neutral_package(package: Path, usd_name: str = "sm_test_neutral_01.usda") -> Path:
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / usd_name
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/RootNode/Geometry/mesh")
    mesh.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
    mesh.CreateFaceVertexCountsAttr([3])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
    mesh.CreateNormalsAttr([Gf.Vec3f(0, 0, 1), Gf.Vec3f(0, 0, 1), Gf.Vec3f(0, 0, 1)])
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.MassAPI.Apply(root.GetPrim())
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())

    from pxr import UsdShade

    material = UsdShade.Material.Define(stage, "/RootNode/Looks/PhysMat")
    UsdPhysics.MaterialAPI.Apply(material.GetPrim())

    stage.GetRootLayer().Save()
    return usd_path


def _write_non_mesh_visual_package(package: Path) -> Path:
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / "sm_bad_prop_01.usda"
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Cube.Define(stage, "/RootNode/Cube")
    stage.GetRootLayer().Save()
    return usd_path


def _write_multibody_physx_package(package: Path) -> Path:
    package.mkdir(parents=True, exist_ok=True)
    usd_path = package / "sm_test_multibody_01.usda"
    stage = Usd.Stage.CreateNew(str(usd_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/RootNode")
    stage.SetDefaultPrim(root.GetPrim())
    UsdPhysics.ArticulationRootAPI.Apply(root.GetPrim())

    body_paths = ("/RootNode/BodyA", "/RootNode/BodyB")
    for index, body_path in enumerate(body_paths):
        body = UsdGeom.Xform.Define(stage, body_path)
        UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
        mass = UsdPhysics.MassAPI.Apply(body.GetPrim())
        mass.CreateMassAttr(float(index + 1))
        body.GetPrim().AddAppliedSchema("PhysxRigidBodyAPI")
        body.GetPrim().CreateAttribute("physxRigidBody:angularDamping", Sdf.ValueTypeNames.Float).Set(1.0)

        mesh = UsdGeom.Mesh.Define(stage, f"{body_path}/Collider")
        mesh.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
        mesh.CreateFaceVertexCountsAttr([3])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
        mesh.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 3)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
        mesh.GetPrim().CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token).Set("sdf")
        mesh.GetPrim().AddAppliedSchema("PhysxCollisionAPI")
        mesh.GetPrim().AddAppliedSchema("PhysxSDFMeshCollisionAPI")

    joint = UsdPhysics.RevoluteJoint.Define(stage, "/RootNode/Joints/Hinge")
    joint.CreateBody0Rel().SetTargets([body_paths[0]])
    joint.CreateBody1Rel().SetTargets([body_paths[1]])
    joint.GetPrim().AddAppliedSchema("PhysxJointAPI")
    joint.GetPrim().CreateAttribute("physxJoint:jointFriction", Sdf.ValueTypeNames.Float).Set(0.5)
    stage.GetRootLayer().Save()
    return usd_path


_SOURCE_PROFILE_ARGS = ("--source-profile", "Robotics-Prop", "--source-version", "3.1.0")


class MultiphysicsUpgradeTests(unittest.TestCase):
    def test_adapter_registrations_present(self):
        meta = getattr(minimal_standard_0_1_0_to_1_0_1, "_feature_adapter", None)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["input_feature_id"], "FET001_MinimalPlaceableVisual.0-1-0")
        self.assertEqual(meta["output_feature_id"], "FET001_MinimalPlaceableVisual.1-0-1")
        self.assertEqual(len(edges.ORDERED_EDGES), 12)

    def test_plan_lists_exact_edges(self):
        plan = build_plan(source_profile="Robotics-Prop", source_version="3.1.0")
        keys = [(e["input"], e["output"]) for e in plan["edges"]]
        self.assertIn(("FET001_MinimalPlaceableVisual.0-1-0", "FET001_MinimalPlaceableVisual.1-0-1"), keys)
        self.assertIn(("FET003_RigidBody.PhysX.0-1-0", "FET003_RigidBody.0-2-0"), keys)
        self.assertIn(("CAP000_Core.0-1-0", "CAP000_Core.PhysX.0-1-0"), keys)
        self.assertIn(("FET003_RigidBody.0-2-0", "FET003_RigidBody.PhysX.0-4-0"), keys)
        self.assertEqual(plan["invalid_selected_features"], [])

    def test_minimal_refuses_non_mesh_visual(self):
        with tempfile.TemporaryDirectory() as tmp:
            usd_path = _write_non_mesh_visual_package(Path(tmp) / "pkg")
            stage = Usd.Stage.Open(str(usd_path))
            with self.assertRaises(core.UpgradeError) as ctx:
                core.apply_minimal_upgrade(stage)
            self.assertTrue(any(b.code == "NON_MESH_VISIBLE_GEOMETRY" for b in ctx.exception.blockers))

    def test_minimal_sets_z_up_and_extents(self):
        with tempfile.TemporaryDirectory() as tmp:
            usd_path = _write_unibody_physx_package(Path(tmp) / "pkg")
            stage = Usd.Stage.Open(str(usd_path))
            core.apply_minimal_upgrade(stage)
            self.assertEqual(UsdGeom.GetStageUpAxis(stage), UsdGeom.Tokens.z)
            mesh = stage.GetPrimAtPath("/RootNode/Geometry/mesh")
            extent = UsdGeom.Boundable(mesh).GetExtentAttr().Get()
            self.assertIsNotNone(extent)

    def test_minimal_refuses_up_axis_metadata_only_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            usd_path = _write_unibody_physx_package(Path(tmp) / "pkg")
            stage = Usd.Stage.Open(str(usd_path))
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            with self.assertRaises(core.UpgradeError) as ctx:
                core.apply_minimal_upgrade(stage)
            self.assertTrue(
                any(b.code == "UP_AXIS_REORIENTATION_REQUIRED" for b in ctx.exception.blockers)
            )

    def test_physx_peel_moves_runtime_to_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "pkg"
            usd_path = _write_unibody_physx_package(package)
            stage = Usd.Stage.Open(str(usd_path))
            core.apply_physx_to_standard_rigid_body(stage)

            # Base clean.
            mesh = stage.GetPrimAtPath("/RootNode/Geometry/mesh")
            schemas = core.authored_api_schemas(stage.GetRootLayer(), mesh.GetPath())
            self.assertFalse(any(s.startswith("Physx") for s in schemas))
            self.assertNotIn("PhysicsMeshCollisionAPI", schemas)
            self.assertIsNone(core.read_approximation(stage, mesh))

            payload = package / "runnables" / "physics" / "physx.usda"
            self.assertTrue(payload.is_file())
            text = payload.read_text(encoding="utf-8")
            self.assertIn("PhysxCollisionAPI", text)
            self.assertIn('physics:approximation = "sdf"', text)

    def test_scaffold_and_runtime_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "pkg"
            usd_path = _write_unibody_physx_package(package)
            stage = Usd.Stage.Open(str(usd_path))
            core.apply_minimal_upgrade(stage)
            core.apply_physx_to_standard_rigid_body(stage)

            stage = Usd.Stage.Open(str(usd_path))
            core.apply_runtime_scaffold(stage, "PhysX")
            core.apply_runtime_scaffold(stage, "Newton")
            core.apply_runtime_scaffold(stage, "MuJoCo")

            stage = Usd.Stage.Open(str(usd_path))
            root = stage.GetDefaultPrim()
            names = root.GetVariantSets().GetNames()
            self.assertIn("PhysX", names)
            self.assertIn("Newton", names)
            self.assertIn("MuJoCo", names)
            self.assertEqual(root.GetVariantSets().GetVariantSet("PhysX").GetVariantSelection(), "Disabled")

            core.apply_standard_to_physx_rigid_body(stage)
            core.apply_standard_to_newton_rigid_body(stage)
            core.apply_standard_to_mujoco_rigid_body(stage)
            core.inspect_neutral_runtime_isolation(stage)

            newton = (package / "runnables" / "physics" / "newton.usda").read_text(encoding="utf-8")
            self.assertIn("NewtonCollisionAPI", newton)
            self.assertIn("NewtonMaterialAPI", newton)
            mujoco = (package / "runnables" / "physics" / "mujoco.usda").read_text(encoding="utf-8")
            self.assertIn("convexHull", mujoco)

    def test_runner_plan_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            code = runner_main(["--plan", *_SOURCE_PROFILE_ARGS, "--report", str(report), str(tmp)])
            self.assertEqual(code, 0)
            self.assertTrue(report.is_file())

    def test_multibody_peel_preserves_physx_joint_in_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "pkg"
            usd_path = _write_multibody_physx_package(package)
            stage = Usd.Stage.Open(str(usd_path))
            core.apply_physx_to_standard_rigid_body(stage)
            core.apply_physx_to_standard_multibody(stage)
            core.assert_neutral_base_clean(stage)

            payload = (package / "runnables" / "physics" / "physx.usda").read_text(encoding="utf-8")
            self.assertIn("PhysxRigidBodyAPI", payload)
            self.assertIn("PhysxJointAPI", payload)
            self.assertIn("physxJoint:jointFriction", payload)

    def test_runner_promotes_complete_multibody_package_without_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            report = Path(tmp) / "report.json"
            usd_path = _write_multibody_physx_package(source)
            code = runner_main(
                [
                    *_SOURCE_PROFILE_ARGS,
                    "--skip-validation",
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                    str(usd_path),
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(output.is_dir())
            payloads = output / "runnables" / "physics"
            self.assertTrue((payloads / "physx.usda").is_file())
            self.assertTrue((payloads / "newton.usda").is_file())
            self.assertTrue((payloads / "mujoco.usda").is_file())
            written = json.loads(report.read_text(encoding="utf-8"))
            self.assertIn("profiling", written)
            profiling = written["profiling"]
            self.assertIn("adapters", profiling)
            self.assertIn("overhead", profiling)
            self.assertIn("total_s", profiling)
            self.assertIn("adapters_total_s", profiling)
            self.assertIn("adapters_loop_s", profiling)
            self.assertTrue(profiling["adapters"])
            by_category = profiling["overhead"]["by_category"]
            self.assertIn("copy_package", by_category)
            self.assertIn("stage_open", by_category)
            self.assertIn("stage_save", by_category)
            self.assertIn("stage_release", by_category)
            self.assertIn("promote_output", by_category)
            self.assertTrue(all("elapsed_s" in item for item in profiling["adapters"]))
            adapter_steps = [s for s in written["steps"] if s.get("kind") == "adapter"]
            self.assertTrue(adapter_steps)
            self.assertTrue(all("elapsed_s" in s for s in adapter_steps))
            # All adapters share one stage; open/save/release are each paid once.
            overhead_steps = [s for s in written["steps"] if s.get("kind") == "overhead"]
            self.assertEqual(sum(s["step"] == "stage_open" for s in overhead_steps), 1)
            self.assertEqual(sum(s["step"] == "stage_save" for s in overhead_steps), 1)
            self.assertEqual(sum(s["step"] == "stage_release" for s in overhead_steps), 1)

    def test_runner_assets_json_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_a = root / "pkg_a"
            src_b = root / "pkg_b"
            usd_a = _write_unibody_physx_package(src_a, "sm_pkg_a_01.usda")
            usd_b = _write_unibody_physx_package(src_b, "sm_pkg_b_01.usda")
            assets = root / "assets.json"
            assets.write_text(
                json.dumps(
                    [
                        {
                            "input_path": str(usd_a),
                            "output_folder": str(root / "out_a"),
                        },
                        {
                            "input_path": str(usd_b),
                            "output_folder": str(root / "out_b"),
                        },
                        {
                            "input_path": str(root / "missing" / "sm_missing_01.usda"),
                            "output_folder": str(root / "out_missing"),
                        },
                    ]
                ),
                encoding="utf-8",
            )
            batch_report_path = root / "batch_report.json"
            code = runner_main(
                [
                    *_SOURCE_PROFILE_ARGS,
                    "--skip-validation",
                    "--assets-json",
                    str(assets),
                    "--report",
                    str(batch_report_path),
                ]
            )
            self.assertEqual(code, 2)
            self.assertTrue((root / "out_a").is_dir())
            self.assertTrue((root / "out_b").is_dir())
            self.assertTrue(batch_report_path.is_file())
            batch_report = json.loads(batch_report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(batch_report["assets"]), 3)
            self.assertEqual([asset["pass"] for asset in batch_report["assets"]], [True, True, False])
            self.assertTrue(any("not found" in err.lower() for err in batch_report["assets"][2]["errors"]))
            pkg_a_report = batch_report["assets"][0]
            self.assertTrue(pkg_a_report["pass"])
            self.assertEqual(pkg_a_report["errors"], [])
            self.assertTrue(pkg_a_report.get("detected_unibody"))
            skipped = [s for s in pkg_a_report["steps"] if s.get("status") == "skipped"]
            self.assertTrue(any("multibody" in s["step"] for s in skipped))

    def test_feature_adapter_wrapper_callable(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "pkg"
            usd_path = _write_unibody_physx_package(package)
            # Minimal first so peel preflight is about physics, not missing normals.
            in_stage = Usd.Stage.Open(str(usd_path))
            out_stage = Usd.Stage.Open(str(usd_path))
            minimal_standard_0_1_0_to_1_0_1(in_stage, out_stage)
            in_stage = Usd.Stage.Open(str(usd_path))
            out_stage = Usd.Stage.Open(str(usd_path))
            rigid_body_physx_0_1_0_to_standard_0_2_0(in_stage, out_stage)
            self.assertTrue((package / "runnables" / "physics" / "physx.usda").is_file())

    def test_neutral_to_runtimes_authors_all_payloads(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import upgrade_stage

        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "pkg"
            usd_path = _write_unibody_neutral_package(package)
            stage = Usd.Stage.Open(str(usd_path))
            upgrade_stage(stage)

            payloads = package / "runnables" / "physics"
            self.assertTrue((payloads / "physx.usda").is_file())
            self.assertTrue((payloads / "newton.usda").is_file())
            self.assertTrue((payloads / "mujoco.usda").is_file())

            root = stage.GetDefaultPrim()
            vsets = root.GetVariantSets()
            for runtime in ("PhysX", "Newton", "MuJoCo"):
                self.assertIn(runtime, vsets.GetNames())
                self.assertEqual(vsets.GetVariantSet(runtime).GetVariantSelection(), "Disabled")

    def test_neutral_to_runtimes_imports_physx_tuning_values_only(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import upgrade_stage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            neutral_usd = _write_unibody_neutral_package(root / "neutral")
            tuned_usd = _write_unibody_neutral_package(root / "tuned")

            for usd_path in (neutral_usd, tuned_usd):
                setup_stage = Usd.Stage.Open(str(usd_path))
                lid = UsdGeom.Xform.Define(setup_stage, "/RootNode/Lid")
                UsdPhysics.RigidBodyAPI.Apply(lid.GetPrim())
                if usd_path == tuned_usd:
                    UsdPhysics.MassAPI.Apply(lid.GetPrim())
                collider = UsdGeom.Mesh.Define(setup_stage, "/RootNode/Lid/Collider")
                collider.CreatePointsAttr(
                    [Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)]
                )
                collider.CreateFaceVertexCountsAttr([3])
                collider.CreateFaceVertexIndicesAttr([0, 1, 2])
                collider.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 3)
                collider.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
                UsdPhysics.CollisionAPI.Apply(collider.GetPrim())
                joint = UsdPhysics.RevoluteJoint.Define(setup_stage, "/RootNode/Joints/Hinge")
                joint.CreateBody0Rel().SetTargets(["/RootNode"])
                joint.CreateBody1Rel().SetTargets(["/RootNode/Lid"])
                joint.CreateAxisAttr().Set(UsdPhysics.Tokens.y)
                joint.CreateLowerLimitAttr().Set(0.0)
                joint.CreateUpperLimitAttr().Set(90.0)
                joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.25, 0.0, 0.0))
                joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0))
                setup_stage.GetRootLayer().Save()

            tuned_stage = Usd.Stage.Open(str(tuned_usd))
            tuned_root = tuned_stage.GetDefaultPrim()
            mass = UsdPhysics.MassAPI(tuned_root)
            mass.CreateMassAttr(2.5)
            mass.CreateCenterOfMassAttr(Gf.Vec3f(0.1, 0.2, 0.3))
            UsdPhysics.MassAPI(tuned_stage.GetPrimAtPath("/RootNode/Lid")).CreateMassAttr(0.75)
            tuned_root.AddAppliedSchema("PhysxRigidBodyAPI")
            tuned_root.CreateAttribute(
                "physxRigidBody:linearDamping", Sdf.ValueTypeNames.Float
            ).Set(0.125)

            tuned_mesh = tuned_stage.GetPrimAtPath("/RootNode/Geometry/mesh")
            tuned_mesh.AddAppliedSchema("PhysicsMeshCollisionAPI")
            tuned_mesh.AddAppliedSchema("PhysxCollisionAPI")
            tuned_mesh.AddAppliedSchema("PhysxSDFMeshCollisionAPI")
            tuned_mesh.CreateAttribute(
                "physics:approximation", Sdf.ValueTypeNames.Token
            ).Set("sdf")
            tuned_mesh.CreateAttribute(
                "physxSDFMeshCollision:sdfResolution", Sdf.ValueTypeNames.Int
            ).Set(384)

            tuned_material = UsdPhysics.MaterialAPI(
                tuned_stage.GetPrimAtPath("/RootNode/Looks/PhysMat")
            )
            tuned_material.CreateDynamicFrictionAttr(0.82)
            tuned_joint = UsdPhysics.RevoluteJoint(
                tuned_stage.GetPrimAtPath("/RootNode/Joints/Hinge")
            )
            tuned_joint.GetUpperLimitAttr().Set(72.0)
            tuned_joint.GetBody1Rel().SetTargets(["/RootNode/Lid/Collider"])
            tuned_stage.GetRootLayer().Save()

            stage = Usd.Stage.Open(str(neutral_usd))
            report = upgrade_stage(stage, tuned_stage)

            self.assertEqual(report["status"], "applied")
            self.assertEqual(UsdPhysics.MassAPI(stage.GetDefaultPrim()).GetMassAttr().Get(), 2.5)
            self.assertTrue(stage.GetPrimAtPath("/RootNode/Lid").HasAPI(UsdPhysics.MassAPI))
            self.assertEqual(
                UsdPhysics.MassAPI(
                    stage.GetPrimAtPath("/RootNode/Lid")
                ).GetMassAttr().Get(),
                0.75,
            )
            self.assertAlmostEqual(
                UsdPhysics.MaterialAPI(
                    stage.GetPrimAtPath("/RootNode/Looks/PhysMat")
                ).GetDynamicFrictionAttr().Get(),
                0.82,
                places=6,
            )
            joint = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath("/RootNode/Joints/Hinge"))
            self.assertEqual(joint.GetUpperLimitAttr().Get(), 72.0)
            self.assertEqual(joint.GetBody1Rel().GetTargets(), [Sdf.Path("/RootNode/Lid")])
            self.assertIsNone(core.read_approximation(stage, stage.GetPrimAtPath("/RootNode/Geometry/mesh")))
            self.assertNotIn("PhysxRigidBodyAPI", stage.GetDefaultPrim().GetAppliedSchemas())

            physx_text = (
                neutral_usd.parent / "runnables" / "physics" / "physx.usda"
            ).read_text(encoding="utf-8")
            self.assertIn("physxRigidBody:linearDamping", physx_text)
            self.assertIn("physxSDFMeshCollision:sdfResolution", physx_text)
            self.assertIn("384", physx_text)
            self.assertTrue(
                any(
                    item["property"] == "physics:body1"
                    and "structural" in item["reason"]
                    for item in report["skipped"]
                )
            )
            core.assert_neutral_base_clean(stage)

    def test_physx_tuning_counterpart_discovery_and_missing(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import (
            resolve_physx_tuning_usd,
            upgrade_stage,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            neutral_usd = _write_unibody_neutral_package(
                root / "simready_usd", "sm_test_01.usda"
            )
            tuned_usd = _write_unibody_neutral_package(
                root / "simready_physx_usd", "sm_test_01.usda"
            )
            self.assertEqual(resolve_physx_tuning_usd(neutral_usd), tuned_usd.resolve())
            self.assertEqual(
                resolve_physx_tuning_usd(neutral_usd, tuned_usd),
                tuned_usd.resolve(),
            )

            tuned_usd.unlink()
            self.assertIsNone(resolve_physx_tuning_usd(neutral_usd))
            stage = Usd.Stage.Open(str(neutral_usd))
            report = upgrade_stage(stage)
            self.assertEqual(report["status"], "not_found")
            self.assertEqual(report["changes"], [])

    def _write_relocation_pair(self, root: Path, tuned_body_mass: float):
        """Build a neutral/tuned pair whose mass block sits on different prims.

        The neutral package keeps the mass block on the collider, matching the
        Blender export. The tuned package also carries a body-level block whose
        center of mass and inertia are expressed in the body frame.
        """
        neutral_usd = _write_unibody_neutral_package(root / "neutral")
        tuned_usd = _write_unibody_neutral_package(root / "tuned")
        collider_mass = 0.75

        for usd_path in (neutral_usd, tuned_usd):
            setup_stage = Usd.Stage.Open(str(usd_path))
            lid = UsdGeom.Xform.Define(setup_stage, "/RootNode/Lid")
            UsdPhysics.RigidBodyAPI.Apply(lid.GetPrim())
            collider = UsdGeom.Mesh.Define(setup_stage, "/RootNode/Lid/Collider")
            collider.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(0, 1, 0)])
            collider.CreateFaceVertexCountsAttr([3])
            collider.CreateFaceVertexIndicesAttr([0, 1, 2])
            collider.CreateNormalsAttr([Gf.Vec3f(0, 0, 1)] * 3)
            collider.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
            UsdPhysics.CollisionAPI.Apply(collider.GetPrim())
            collider_mass_api = UsdPhysics.MassAPI.Apply(collider.GetPrim())
            collider_mass_api.CreateMassAttr(collider_mass)
            collider_mass_api.CreateCenterOfMassAttr(Gf.Vec3f(0.0, -0.042, 0.037))
            collider_mass_api.CreateDiagonalInertiaAttr(Gf.Vec3f(3.1e-6, 3.5e-5, 3.2e-5))
            collider_mass_api.CreatePrincipalAxesAttr(Gf.Quatf(0.7071068, 0, 0, 0.70710677))
            setup_stage.GetRootLayer().Save()

        tuned_stage = Usd.Stage.Open(str(tuned_usd))
        body_mass_api = UsdPhysics.MassAPI.Apply(tuned_stage.GetPrimAtPath("/RootNode/Lid"))
        body_mass_api.CreateMassAttr(tuned_body_mass)
        body_mass_api.CreateCenterOfMassAttr(Gf.Vec3f(0.0436, 0.0, 0.0293))
        body_mass_api.CreateDiagonalInertiaAttr(Gf.Vec3f(2.8e-5, 3.1e-6, 2.5e-5))
        body_mass_api.CreatePrincipalAxesAttr(Gf.Quatf(1, 0, 0, 0))
        tuned_stage.GetRootLayer().Save()
        return neutral_usd, tuned_stage, collider_mass

    def test_physx_tuning_reports_relocated_mass_block_without_authoring(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import upgrade_stage

        with tempfile.TemporaryDirectory() as tmp:
            neutral_usd, tuned_stage, collider_mass = self._write_relocation_pair(
                Path(tmp), tuned_body_mass=0.75
            )
            stage = Usd.Stage.Open(str(neutral_usd))
            report = upgrade_stage(stage, tuned_stage)

            lid = stage.GetPrimAtPath("/RootNode/Lid")
            self.assertFalse(lid.HasAPI(UsdPhysics.MassAPI))
            for name in (
                "physics:mass",
                "physics:centerOfMass",
                "physics:diagonalInertia",
                "physics:principalAxes",
            ):
                attr = lid.GetAttribute(name)
                self.assertFalse(attr and attr.HasAuthoredValueOpinion(), name)

            relocated = {
                item["property"]: item
                for item in report["relocated"]
                if item["path"] == "/RootNode/Lid"
            }
            self.assertEqual(report["summary"]["relocated"], 4)
            self.assertEqual(relocated["physics:mass"]["basis"], "equal_value")
            self.assertEqual(relocated["physics:centerOfMass"]["basis"], "mass_block")
            self.assertEqual(
                relocated["physics:mass"]["neutral_path"], "/RootNode/Lid/Collider"
            )
            self.assertFalse(
                any(item["path"] == "/RootNode/Lid" for item in report["changes"])
            )
            self.assertAlmostEqual(
                UsdPhysics.MassAPI(
                    stage.GetPrimAtPath("/RootNode/Lid/Collider")
                ).GetMassAttr().Get(),
                collider_mass,
                places=6,
            )
            core.assert_neutral_base_clean(stage)

    def test_physx_tuning_applies_mass_block_when_mass_differs(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import upgrade_stage

        with tempfile.TemporaryDirectory() as tmp:
            neutral_usd, tuned_stage, _ = self._write_relocation_pair(
                Path(tmp), tuned_body_mass=1.5
            )
            stage = Usd.Stage.Open(str(neutral_usd))
            report = upgrade_stage(stage, tuned_stage)

            lid = stage.GetPrimAtPath("/RootNode/Lid")
            self.assertTrue(lid.HasAPI(UsdPhysics.MassAPI))
            self.assertAlmostEqual(
                UsdPhysics.MassAPI(lid).GetMassAttr().Get(), 1.5, places=6
            )
            applied = {
                item["property"]
                for item in report["changes"]
                if item["path"] == "/RootNode/Lid"
            }
            self.assertIn("physics:mass", applied)
            self.assertIn("physics:centerOfMass", applied)
            self.assertFalse(
                any(item["path"] == "/RootNode/Lid" for item in report["relocated"])
            )

    def test_neutral_to_runtimes_copies_source_folder_to_dest(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import main as ntr_main

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            dest = Path(tmp) / "dest"
            usd_path = _write_unibody_neutral_package(source)
            extra = source / "sidecar.txt"
            extra.write_text("keep", encoding="utf-8")

            code = ntr_main([str(usd_path), str(dest)])
            self.assertEqual(code, 0)
            self.assertFalse((source / "runnables").exists())
            self.assertTrue((dest / extra.name).is_file())
            self.assertEqual((dest / extra.name).read_text(encoding="utf-8"), "keep")
            payloads = dest / "runnables" / "physics"
            self.assertTrue((payloads / "physx.usda").is_file())
            self.assertTrue((payloads / "newton.usda").is_file())
            self.assertTrue((payloads / "mujoco.usda").is_file())

    def test_neutral_to_runtimes_assets_json_batch(self):
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import main as ntr_main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            usd_a = _write_unibody_neutral_package(root / "pkg_a", "sm_pkg_a_01.usda")
            usd_b = _write_unibody_neutral_package(root / "pkg_b", "sm_pkg_b_01.usda")
            assets = root / "asset_list.json"
            assets.write_text(
                json.dumps(
                    [
                        {
                            "input_path": str(usd_a),
                            "output_folder": str(root / "out_a"),
                        },
                        {
                            "input_path": str(usd_b),
                            "output_folder": str(root / "out_b"),
                        },
                        {
                            "input_path": str(root / "missing" / "sm_missing_01.usda"),
                            "output_folder": str(root / "out_missing"),
                        },
                    ]
                ),
                encoding="utf-8",
            )
            batch_report_path = root / "batch_report.json"
            code = ntr_main(
                [
                    "--assets-json",
                    str(assets),
                    "--report",
                    str(batch_report_path),
                ]
            )
            self.assertEqual(code, 2)
            self.assertTrue((root / "out_a" / "runnables" / "physics" / "physx.usda").is_file())
            self.assertTrue((root / "out_b" / "runnables" / "physics" / "newton.usda").is_file())
            self.assertFalse((root / "out_missing").exists())
            batch_report = json.loads(batch_report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(batch_report["assets"]), 3)
            self.assertEqual(
                [asset["pass"] for asset in batch_report["assets"]],
                [True, True, False],
            )
            self.assertTrue(
                any("could not find" in err.lower() for err in batch_report["assets"][2]["errors"])
            )
        from asset_handler_modules.multiphysics_upgrade.neutral_to_runtimes import main as ntr_main

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            dest = Path(tmp) / "dest"
            usd_path = _write_unibody_neutral_package(source)
            extra = source / "sidecar.txt"
            extra.write_text("keep", encoding="utf-8")

            code = ntr_main([str(usd_path), str(dest)])
            self.assertEqual(code, 0)
            self.assertFalse((source / "runnables").exists())
            self.assertTrue((dest / extra.name).is_file())
            self.assertEqual((dest / extra.name).read_text(encoding="utf-8"), "keep")
            payloads = dest / "runnables" / "physics"
            self.assertTrue((payloads / "physx.usda").is_file())
            self.assertTrue((payloads / "newton.usda").is_file())
            self.assertTrue((payloads / "mujoco.usda").is_file())


if __name__ == "__main__":
    unittest.main()
