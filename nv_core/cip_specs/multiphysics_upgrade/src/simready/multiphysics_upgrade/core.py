# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""pxr-only multiphysics upgrade helpers.

Procedural mutation and preflight utilities shared by CIP ``@feature_adapter``
wrappers and the standalone runner. Fail closed on ambiguous topology/policy.
Never create geometry, joints, or mass values.
"""

from __future__ import annotations

import errno
import json
import math
import os
import shutil
import stat
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

from .types import (
    Blocker,
    MutationReport,
    PhysicsTuningChange,
    PhysicsTuningRelocation,
    PhysicsTuningSkip,
    PreflightResult,
)

PHYSX_DELTA_APPROXIMATION = "sdf"
MUJOCO_DELTA_APPROXIMATION = "convexHull"

RUNTIME_VARIANT_SETS = ("PhysX", "Newton", "MuJoCo")
RUNTIME_PAYLOAD_STEMS = {
    "PhysX": "physx",
    "Newton": "newton",
    "MuJoCo": "mujoco",
}

# Neutral UsdPhysics APIs that stay on the base.
_NEUTRAL_PHYSICS_SCHEMAS = {
    "PhysicsCollisionAPI",
    "PhysicsRigidBodyAPI",
    "PhysicsMassAPI",
    "PhysicsMaterialAPI",
    "PhysicsFilteredPairsAPI",
    "PhysicsArticulationRootAPI",
    "PhysicsJoint",
    "PhysicsRevoluteJoint",
    "PhysicsPrismaticJoint",
    "PhysicsSphericalJoint",
    "PhysicsFixedJoint",
    "PhysicsDistanceJoint",
    "LimitAPI",
    "DriveAPI",
}

# Mesh-collision + approximation belong in runtimes for multiphysics isolation.
_MOVE_TO_RUNTIME_SCHEMAS = {
    "PhysicsMeshCollisionAPI",
}

_PHYSX_SCHEMA_PREFIXES = ("Physx",)
_NEWTON_SCHEMA_PREFIXES = ("Newton",)
_MUJOCO_SCHEMA_PREFIXES = ("Mjc",)

_PHYSX_ATTR_PREFIXES = ("physx", "Physx")
_NEWTON_ATTR_PREFIXES = ("newton:", "Newton")
_MUJOCO_ATTR_PREFIXES = ("mjc:", "Mjc")

_BODY_WORK_SCHEMAS = {
    "PhysxMimicJointAPI",
    "NewtonMimicAPI",
    "MjcActuator",
    "PhysxArticulationAPI",
    "PhysxSceneAPI",
}

_VALUE_PHYSICS_SCHEMAS = {
    "PhysicsMassAPI",
    "PhysicsMaterialAPI",
    "PhysicsDriveAPI",
    "PhysicsJointStateAPI",
    "PhysicsLimitAPI",
}

_VISIBLE_NON_MESH = (
    UsdGeom.Cube,
    UsdGeom.Sphere,
    UsdGeom.Cylinder,
    UsdGeom.Capsule,
    UsdGeom.Cone,
    UsdGeom.Points,
    UsdGeom.BasisCurves,
    UsdGeom.NurbsCurves,
    UsdGeom.NurbsPatch,
)


class UpgradeError(RuntimeError):
    """Raised when an adapter must refuse rather than guess."""

    def __init__(self, blockers: list[Blocker]):
        self.blockers = blockers
        codes = ", ".join(b.code for b in blockers)
        super().__init__(f"upgrade blocked: {codes}")


# ---------------------------------------------------------------------------
# Path / layer helpers
# ---------------------------------------------------------------------------


def asset_root_for_stage(stage: Usd.Stage) -> Path:
    root_path = stage.GetRootLayer().realPath or stage.GetRootLayer().identifier
    if not root_path or root_path.startswith("anon:"):
        raise UpgradeError(
            [
                Blocker(
                    code="NO_REAL_ROOT_LAYER",
                    requirement="AA.001",
                    detail="Stage root layer has no real path; cannot locate asset package root.",
                )
            ]
        )
    return Path(root_path).resolve().parent


def find_root_usd(package_dir: Path) -> Path:
    package_dir = package_dir.resolve()
    candidates: list[Path] = []
    for pattern in ("*.usda", "*.usd", "*.usdc"):
        candidates.extend(p for p in package_dir.glob(pattern) if p.is_file())
    # Prefer non-payload root files at package top level.
    top = [p for p in candidates if p.parent == package_dir]
    if len(top) == 1:
        return top[0]
    if len(top) > 1:
        # Prefer names that look like sm_*/asset roots over materials.
        preferred = [p for p in top if p.name.lower().startswith("sm_")]
        if len(preferred) == 1:
            return preferred[0]
        raise UpgradeError(
            [
                Blocker(
                    code="AMBIGUOUS_ROOT_USD",
                    requirement="AA.001",
                    detail="Multiple candidate root USD files at package root.",
                    paths=[str(p) for p in sorted(top)],
                )
            ]
        )
    # One level down (e.g. simready_usd/).
    nested: list[Path] = []
    for child in package_dir.iterdir():
        if child.is_dir() and child.name not in {"runnables", "payloads", "Textures", "textures", ".thumbs"}:
            for pattern in ("*.usda", "*.usd", "*.usdc"):
                nested.extend(p for p in child.glob(pattern) if p.is_file())
    sm = [p for p in nested if p.name.lower().startswith("sm_")]
    if len(sm) == 1:
        return sm[0]
    if len(nested) == 1:
        return nested[0]
    raise UpgradeError(
        [
            Blocker(
                code="AMBIGUOUS_ROOT_USD",
                requirement="AA.001",
                detail="Could not uniquely identify the package root USD.",
                paths=[str(p) for p in sorted(nested or candidates)[:20]],
            )
        ]
    )


def runnables_physics_dir(asset_root: Path) -> Path:
    return asset_root / "runnables" / "physics"


def payload_path(asset_root: Path, runtime: str, prefer_existing: bool = True) -> Path:
    stem = RUNTIME_PAYLOAD_STEMS[runtime]
    directory = runnables_physics_dir(asset_root)
    usda = directory / f"{stem}.usda"
    usd = directory / f"{stem}.usd"
    if prefer_existing:
        if usda.is_file():
            return usda
        if usd.is_file():
            return usd
    return usda


def ensure_payload_layer(path: Path, default_prim_name: str, doc: str = "") -> Sdf.Layer:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        layer = Sdf.Layer.FindOrOpen(str(path))
        if layer is None:
            raise UpgradeError(
                [
                    Blocker(
                        code="PAYLOAD_OPEN_FAILED",
                        requirement="RV.002",
                        detail=f"Could not open existing payload layer {path}.",
                    )
                ]
            )
        return layer

    layer = Sdf.Layer.CreateNew(str(path))
    layer.defaultPrim = default_prim_name
    if doc:
        layer.documentation = doc
    root_path = Sdf.Path(f"/{default_prim_name}")
    Sdf.CreatePrimInLayer(layer, root_path)
    layer.GetPrimAtPath(root_path).specifier = Sdf.SpecifierOver
    layer.Save()
    return layer


def rel_chain(path: Sdf.Path, default_prim: Sdf.Path) -> tuple[str, ...]:
    if not path.HasPrefix(default_prim):
        raise UpgradeError(
            [
                Blocker(
                    code="PATH_OUTSIDE_DEFAULT_PRIM",
                    requirement="HI.001",
                    detail=f"{path} is not under defaultPrim {default_prim}.",
                )
            ]
        )
    names: list[str] = []
    cur = path
    while cur != default_prim:
        names.append(cur.name)
        cur = cur.GetParentPath()
    return tuple(reversed(names))


def ensure_over_chain(layer: Sdf.Layer, default_prim_name: str, chain: tuple[str, ...]) -> Sdf.PrimSpec:
    path = Sdf.Path(f"/{default_prim_name}")
    for name in chain:
        path = path.AppendChild(name)
        if layer.GetPrimAtPath(path) is None:
            Sdf.CreatePrimInLayer(layer, path)
            layer.GetPrimAtPath(path).specifier = Sdf.SpecifierOver
    return layer.GetPrimAtPath(path)


# ---------------------------------------------------------------------------
# Schema / attribute introspection (layer-faithful)
# ---------------------------------------------------------------------------


def authored_api_schemas(layer: Sdf.Layer, path: Sdf.Path) -> list[str]:
    prim_spec = layer.GetPrimAtPath(path)
    if prim_spec is None or not prim_spec.HasInfo("apiSchemas"):
        return []
    op = prim_spec.GetInfo("apiSchemas")
    tokens: list[str] = []
    for items in (op.explicitItems, op.prependedItems, op.appendedItems, op.addedItems):
        if items:
            tokens.extend(str(i) for i in items)
    return tokens


def schema_base(token: str) -> str:
    return str(token).split(":")[0]


def all_schemas(stage: Usd.Stage, prim: Usd.Prim) -> set[str]:
    layer = stage.GetRootLayer()
    tokens = {schema_base(t) for t in authored_api_schemas(layer, prim.GetPath())}
    tokens.update(schema_base(str(s)) for s in prim.GetAppliedSchemas())
    return tokens


def read_approximation(stage: Usd.Stage, prim: Usd.Prim) -> str | None:
    attr = prim.GetAttribute("physics:approximation")
    if attr and attr.HasAuthoredValueOpinion():
        value = attr.Get()
        if value is not None:
            return str(value)
    prim_spec = stage.GetRootLayer().GetPrimAtPath(prim.GetPath())
    if prim_spec is not None:
        prop = prim_spec.attributes.get("physics:approximation")
        if prop is not None and prop.default is not None:
            return str(prop.default)
    return None


def _is_runtime_schema(name: str, runtime: str | None = None) -> bool:
    base = schema_base(name)
    if runtime in (None, "PhysX") and any(base.startswith(p) for p in _PHYSX_SCHEMA_PREFIXES):
        return True
    if runtime in (None, "Newton") and any(base.startswith(p) for p in _NEWTON_SCHEMA_PREFIXES):
        return True
    if runtime in (None, "MuJoCo") and any(base.startswith(p) for p in _MUJOCO_SCHEMA_PREFIXES):
        return True
    if runtime in (None, "PhysX") and base in _MOVE_TO_RUNTIME_SCHEMAS:
        return True
    return False


def _is_runtime_attr(name: str, runtime: str | None = None) -> bool:
    if runtime in (None, "PhysX") and (
        name == "physics:approximation" or any(name.startswith(p) for p in _PHYSX_ATTR_PREFIXES)
    ):
        return True
    if runtime in (None, "Newton") and any(name.startswith(p) for p in _NEWTON_ATTR_PREFIXES):
        return True
    if runtime in (None, "MuJoCo") and any(name.startswith(p) for p in _MUJOCO_ATTR_PREFIXES):
        return True
    return False


def _json_value(value):
    """Convert a USD value into a stable JSON-compatible representation."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Sdf.AssetPath):
        return value.path
    if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
        imaginary = value.GetImaginary()
        return [
            _json_value(value.GetReal()),
            *[_json_value(component) for component in imaginary],
        ]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


def _physics_attr_kind(name: str) -> str | None:
    if name == "physics:approximation" or any(name.startswith(prefix) for prefix in _PHYSX_ATTR_PREFIXES):
        return "physx"
    if name.startswith(("physics:", "drive:", "state:", "limit:")):
        return "neutral"
    return None


def _is_physics_prim(prim: Usd.Prim) -> bool:
    if not prim or not prim.IsValid():
        return False
    if prim.IsA(UsdPhysics.Joint):
        return True
    if any(
        prim.HasAPI(api)
        for api in (
            UsdPhysics.RigidBodyAPI,
            UsdPhysics.CollisionAPI,
            UsdPhysics.MassAPI,
            UsdPhysics.MaterialAPI,
            UsdPhysics.ArticulationRootAPI,
        )
    ):
        return True
    return any(
        schema_base(str(schema)).startswith(("Physics", "Physx"))
        for schema in prim.GetAppliedSchemas()
    )


def _mapped_tuning_path(
    tuned_path: Sdf.Path,
    tuned_default_path: Sdf.Path,
    target_default_path: Sdf.Path,
) -> Sdf.Path:
    if tuned_path == tuned_default_path:
        return target_default_path
    return tuned_path.ReplacePrefix(tuned_default_path, target_default_path)


_MASS_BLOCK_ANCHOR = "physics:mass"
_MASS_BLOCK_FRAME_ATTRS = (
    "physics:centerOfMass",
    "physics:diagonalInertia",
    "physics:principalAxes",
)


def _tuning_scope_prims(
    stage: Usd.Stage,
    target_prim: Usd.Prim,
    default_path: Sdf.Path,
):
    """Yield neutral prims that may already hold ``target_prim``'s physics values.

    The scope is the prim's own subtree plus its ancestor chain up to the
    default prim, which covers a rigid-body/collider pair without reaching
    across into sibling bodies.
    """
    seen = set()
    predicate = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for descendant in Usd.PrimRange(target_prim, predicate):
        path = descendant.GetPath()
        if path == target_prim.GetPath() or path in seen:
            continue
        seen.add(path)
        yield descendant
    path = target_prim.GetPath().GetParentPath()
    while path.HasPrefix(default_path):
        prim = stage.GetPrimAtPath(path)
        if prim and prim.IsValid() and path not in seen:
            seen.add(path)
            yield prim
        if path == default_path:
            break
        path = path.GetParentPath()


def _detect_tuning_relocations(
    stage: Usd.Stage,
    target_prim: Usd.Prim,
    default_path: Sdf.Path,
    tuned_attrs: list[Usd.Attribute],
) -> dict[str, tuple[Sdf.Path, str]]:
    """Map counterpart attributes onto neutral prims that already carry the value.

    Only ``physics:mass`` is frame independent, so it anchors the mass block. A
    center of mass, inertia, or principal-axes value that moved from the
    collider prim to the body prim is re-expressed in the body frame and cannot
    be compared numerically; an exact mass match elsewhere in scope is taken as
    proof the whole block describes the same mass distribution.
    """
    relocations: dict[str, tuple[Sdf.Path, str]] = {}
    pending_frame_attrs: list[str] = []
    mass_source: Sdf.Path | None = None
    candidates: list[Usd.Prim] | None = None

    for attr in tuned_attrs:
        name = attr.GetName()
        if _physics_attr_kind(name) != "neutral":
            continue
        existing = target_prim.GetAttribute(name)
        if existing and existing.HasAuthoredValueOpinion():
            continue
        if candidates is None:
            candidates = list(_tuning_scope_prims(stage, target_prim, default_path))
        wanted = _json_value(attr.Get())
        source = None
        for candidate in candidates:
            other = candidate.GetAttribute(name)
            if other and other.HasAuthoredValueOpinion() and _json_value(other.Get()) == wanted:
                source = candidate.GetPath()
                break
        if source is not None:
            relocations[name] = (source, "equal_value")
            if name == _MASS_BLOCK_ANCHOR:
                mass_source = source
        elif name in _MASS_BLOCK_FRAME_ATTRS:
            pending_frame_attrs.append(name)

    if mass_source is not None:
        for name in pending_frame_attrs:
            relocations[name] = (mass_source, "mass_block")
    return relocations


def _tuning_skip(
    skipped: list[PhysicsTuningSkip],
    *,
    path: Sdf.Path,
    property_name: str,
    reason: str,
    neutral_value=None,
    tuned_value=None,
) -> None:
    skipped.append(
        PhysicsTuningSkip(
            path=str(path),
            property=property_name,
            reason=reason,
            neutral_value=_json_value(neutral_value),
            tuned_value=_json_value(tuned_value),
        )
    )


def apply_physics_tuning(stage: Usd.Stage, tuned_stage: Usd.Stage) -> dict:
    """Import tunable USDPhysics/PhysX values from a matching counterpart.

    Structural topology is deliberately preserved: prim types, transforms,
    applied neutral Physics schemas, and relationships are compared and
    reported but never copied. Runtime-specific PhysX APIs and attributes are
    written into the PhysX payload; neutral ``physics:*`` values are authored
    on the working stage's root layer.
    """
    target_default = stage.GetDefaultPrim()
    tuned_default = tuned_stage.GetDefaultPrim()
    if not target_default or not tuned_default:
        raise UpgradeError(
            [
                Blocker(
                    code="TUNING_DEFAULT_PRIM_MISSING",
                    requirement="physics_tuning",
                    detail="Both neutral and tuned stages must have a defaultPrim.",
                )
            ]
        )

    target_default_path = target_default.GetPath()
    tuned_default_path = tuned_default.GetPath()
    root_layer = stage.GetRootLayer()
    physx_layer = ensure_payload_layer(
        payload_path(asset_root_for_stage(stage), "PhysX", prefer_existing=True),
        target_default.GetName(),
        doc="PhysX runtime overrides",
    )

    changes: list[PhysicsTuningChange] = []
    skipped: list[PhysicsTuningSkip] = []
    relocated: list[PhysicsTuningRelocation] = []
    unchanged = 0

    predicate = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    for tuned_prim in tuned_stage.Traverse(predicate):
        tuned_path = tuned_prim.GetPath()
        if not tuned_path.HasPrefix(tuned_default_path):
            continue
        target_path = _mapped_tuning_path(tuned_path, tuned_default_path, target_default_path)
        target_prim = stage.GetPrimAtPath(target_path)

        tuned_runtime_schemas = [
            str(schema)
            for schema in tuned_prim.GetAppliedSchemas()
            if _is_runtime_schema(str(schema), "PhysX")
        ]
        tuned_neutral_schemas = {
            str(schema)
            for schema in tuned_prim.GetAppliedSchemas()
            if schema_base(str(schema)).startswith("Physics")
            and not _is_runtime_schema(str(schema), "PhysX")
        }
        tuned_physics_attrs = [
            attr
            for attr in tuned_prim.GetAttributes()
            if _physics_attr_kind(attr.GetName()) is not None and attr.HasAuthoredValueOpinion()
        ]
        tuned_physics_rels = [
            rel
            for rel in tuned_prim.GetRelationships()
            if rel.GetName().startswith(("physics:", "physx:"))
        ]
        has_physics_content = bool(
            tuned_runtime_schemas
            or tuned_neutral_schemas
            or tuned_physics_attrs
            or tuned_physics_rels
            or tuned_prim.IsA(UsdPhysics.Joint)
        )
        if not has_physics_content:
            continue

        if not target_prim or not target_prim.IsValid():
            _tuning_skip(
                skipped,
                path=target_path,
                property_name="prim",
                reason="No matching prim in neutral stage.",
                tuned_value=str(tuned_prim.GetTypeName()),
            )
            continue
        if target_prim.GetTypeName() != tuned_prim.GetTypeName():
            _tuning_skip(
                skipped,
                path=target_path,
                property_name="typeName",
                reason="Prim type differs; topology is never imported.",
                neutral_value=target_prim.GetTypeName(),
                tuned_value=tuned_prim.GetTypeName(),
            )
        if not _is_physics_prim(target_prim):
            _tuning_skip(
                skipped,
                path=target_path,
                property_name="prim",
                reason="Matching neutral prim has no existing physics role.",
            )
            continue
        if target_prim.IsInstanceProxy():
            _tuning_skip(
                skipped,
                path=target_path,
                property_name="prim",
                reason="Cannot author tuning on an instance proxy.",
            )
            continue

        target_neutral_schemas = {
            str(schema)
            for schema in target_prim.GetAppliedSchemas()
            if schema_base(str(schema)).startswith("Physics")
            and not _is_runtime_schema(str(schema), "PhysX")
        }
        relocations = _detect_tuning_relocations(
            stage, target_prim, target_default_path, tuned_physics_attrs
        )
        has_neutral_tuning_values = any(
            _physics_attr_kind(attr.GetName()) == "neutral"
            and attr.GetName() not in relocations
            for attr in tuned_physics_attrs
        )
        for schema in sorted(tuned_neutral_schemas ^ target_neutral_schemas):
            schema_is_tuned = schema in tuned_neutral_schemas
            if (
                schema_is_tuned
                and has_neutral_tuning_values
                and schema_base(schema) in _VALUE_PHYSICS_SCHEMAS
            ):
                with Usd.EditContext(stage, root_layer):
                    target_prim.AddAppliedSchema(schema)
                target_neutral_schemas.add(schema)
                changes.append(
                    PhysicsTuningChange(
                        path=str(target_path),
                        property=f"apiSchemas:{schema}",
                        destination="base",
                        value_type="schema",
                        old_value=False,
                        tuned_value=True,
                    )
                )
                continue
            _tuning_skip(
                skipped,
                path=target_path,
                property_name=f"apiSchemas:{schema}",
                reason="Neutral physics schema topology differs and is not imported.",
                neutral_value=schema in target_neutral_schemas,
                tuned_value=schema in tuned_neutral_schemas,
            )

        for tuned_rel in tuned_physics_rels:
            target_rel = target_prim.GetRelationship(tuned_rel.GetName())
            target_targets = list(target_rel.GetTargets()) if target_rel else []
            tuned_targets = [
                _mapped_tuning_path(path, tuned_default_path, target_default_path)
                if path.HasPrefix(tuned_default_path)
                else path
                for path in tuned_rel.GetTargets()
            ]
            if target_targets != tuned_targets:
                _tuning_skip(
                    skipped,
                    path=target_path,
                    property_name=tuned_rel.GetName(),
                    reason="Physics relationships are structural and are not imported.",
                    neutral_value=[str(path) for path in target_targets],
                    tuned_value=[str(path) for path in tuned_targets],
                )

        chain = () if target_path == target_default_path else rel_chain(target_path, target_default_path)
        payload_prim = ensure_over_chain(physx_layer, target_default.GetName(), chain)
        existing_payload_schemas = set(authored_api_schemas(physx_layer, target_path))
        for schema in tuned_runtime_schemas:
            if schema in existing_payload_schemas:
                unchanged += 1
                continue
            _merge_schemas_onto_payload(payload_prim, [schema])
            existing_payload_schemas.add(schema)
            changes.append(
                PhysicsTuningChange(
                    path=str(target_path),
                    property=f"apiSchemas:{schema}",
                    destination="runnables/physics/physx.usda",
                    value_type="schema",
                    old_value=False,
                    tuned_value=True,
                )
            )

        for tuned_attr in tuned_physics_attrs:
            name = tuned_attr.GetName()
            if name in relocations:
                source_path, basis = relocations[name]
                relocated.append(
                    PhysicsTuningRelocation(
                        path=str(target_path),
                        property=name,
                        neutral_path=str(source_path),
                        value_type=str(tuned_attr.GetTypeName()),
                        tuned_value=_json_value(tuned_attr.Get()),
                        basis=basis,
                    )
                )
                continue
            if tuned_attr.GetNumTimeSamples() > 0:
                _tuning_skip(
                    skipped,
                    path=target_path,
                    property_name=name,
                    reason="Time-sampled physics values are not imported.",
                )
                continue
            connections = tuned_attr.GetConnections()
            if connections:
                _tuning_skip(
                    skipped,
                    path=target_path,
                    property_name=name,
                    reason="Connected physics values are not imported.",
                    tuned_value=[str(path) for path in connections],
                )
                continue

            tuned_value = tuned_attr.Get()
            value_type = str(tuned_attr.GetTypeName())
            kind = _physics_attr_kind(name)
            if kind == "physx":
                payload_attr = payload_prim.attributes.get(name)
                old_value = payload_attr.default if payload_attr is not None else None
                if _json_value(old_value) == _json_value(tuned_value):
                    unchanged += 1
                    continue
                if payload_attr is None:
                    payload_attr = Sdf.AttributeSpec(payload_prim, name, tuned_attr.GetTypeName())
                payload_attr.default = tuned_value
                destination = "runnables/physics/physx.usda"
            else:
                target_attr = target_prim.GetAttribute(name)
                old_value = target_attr.Get() if target_attr and target_attr.HasAuthoredValueOpinion() else None
                if _json_value(old_value) == _json_value(tuned_value):
                    unchanged += 1
                    continue
                with Usd.EditContext(stage, root_layer):
                    if not target_attr:
                        target_attr = target_prim.CreateAttribute(
                            name,
                            tuned_attr.GetTypeName(),
                            custom=tuned_attr.IsCustom(),
                            variability=tuned_attr.GetVariability(),
                        )
                    target_attr.Set(tuned_value)
                destination = "base"

            changes.append(
                PhysicsTuningChange(
                    path=str(target_path),
                    property=name,
                    destination=destination,
                    value_type=value_type,
                    old_value=_json_value(old_value),
                    tuned_value=_json_value(tuned_value),
                )
            )

    physx_layer.Save()
    root_layer.Save()
    return {
        "status": "applied" if changes else "no_changes",
        "summary": {
            "applied": len(changes),
            "unchanged": unchanged,
            "relocated": len(relocated),
            "skipped": len(skipped),
        },
        "changes": [asdict(change) for change in changes],
        "relocated": [asdict(item) for item in relocated],
        "skipped": [asdict(skip) for skip in skipped],
        "physx_payload": physx_layer.realPath,
    }


def raise_if_blocked(pre: PreflightResult) -> None:
    if pre.blockers:
        raise UpgradeError(pre.blockers)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _unsupported_standard_drives(stage: Usd.Stage) -> list[str]:
    """Preserve bounded authored USD drives; never synthesize runtime actuation."""
    unsupported: list[str] = []
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        opinions = prim.GetMetadata("apiSchemas")
        tokens = opinions.GetAppliedItems() if opinions else []
        for token in tokens:
            if schema_base(str(token)) != "PhysicsDriveAPI":
                continue
            axis = str(token).partition(":")[2]
            valid = (axis == "angular" and prim.IsA(UsdPhysics.RevoluteJoint)) or (
                axis == "linear" and prim.IsA(UsdPhysics.PrismaticJoint)
            )
            for field in (
                "type",
                "stiffness",
                "damping",
                "maxForce",
                "targetPosition",
                "targetVelocity",
            ):
                attribute = prim.GetAttribute(f"drive:{axis}:physics:{field}")
                value = attribute.Get() if attribute else None
                if not attribute or attribute.GetNumTimeSamples():
                    valid = False
                elif field == "type":
                    valid = valid and value in ("force", "acceleration")
                elif isinstance(value, bool) or not isinstance(value, (float, int)):
                    valid = False
                else:
                    valid = valid and (
                        math.isfinite(value)
                        or (field == "maxForce" and value == math.inf)
                    )
                    if field in ("stiffness", "damping", "maxForce"):
                        valid = valid and value >= 0
                if not valid:
                    break
            if not valid:
                unsupported.append(
                    f"{prim.GetPath()} [{token}: unsupported joint/axis or drive values]"
                )
    return unsupported


def preflight_physics_topology(
    stage: Usd.Stage,
    *,
    require_colliders: bool = True,
    refuse_existing_variants: bool = False,
    refuse_existing_payloads: bool = False,
    asset_root: Path | None = None,
) -> PreflightResult:
    """Collect topology facts and fail-closed blockers for physics edges."""
    result = PreflightResult()
    layer = stage.GetRootLayer()
    root = stage.GetDefaultPrim()
    if not root:
        result.blockers.append(
            Blocker(
                code="NO_DEFAULT_PRIM",
                requirement="HI.001",
                detail="Stage has no defaultPrim; owning prim is ambiguous.",
            )
        )
        return result

    result.default_prim_path = str(root.GetPath())
    result.default_prim_name = root.GetName()

    collision_prims: list[Usd.Prim] = []
    non_mesh_collision: list[str] = []
    foreign_runtime: list[str] = []
    body_work: list[str] = _unsupported_standard_drives(stage)

    for prim in stage.Traverse():
        schemas = all_schemas(stage, prim)
        path = str(prim.GetPath())

        if prim.HasAPI(UsdPhysics.RigidBodyAPI) or "PhysicsRigidBodyAPI" in schemas:
            result.rigid_bodies.append(path)
        if prim.HasAPI(UsdPhysics.MaterialAPI) or "PhysicsMaterialAPI" in schemas:
            if prim.IsA(UsdShade.Material):
                result.physics_materials.append(path)
        if prim.IsA(UsdPhysics.Joint):
            result.joints.append(path)
        if "PhysicsArticulationRootAPI" in schemas or prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            result.articulation_roots.append(path)

        is_collision = "PhysicsCollisionAPI" in schemas or "PhysicsMeshCollisionAPI" in schemas
        if is_collision or read_approximation(stage, prim) is not None:
            if prim.IsA(UsdGeom.Mesh):
                collision_prims.append(prim)
            else:
                non_mesh_collision.append(path)

        for schema in schemas:
            if schema in _BODY_WORK_SCHEMAS:
                body_work.append(f"{path} [{schema}]")
            if any(schema.startswith(p) for p in _NEWTON_SCHEMA_PREFIXES + _MUJOCO_SCHEMA_PREFIXES):
                foreign_runtime.append(f"{path} [{schema}]")

    collider_paths = {str(p.GetPath()) for p in collision_prims}
    result.colliders = sorted(collider_paths)

    if require_colliders and not collision_prims:
        result.blockers.append(
            Blocker(
                code="NO_COLLIDERS",
                requirement="RB.COL.001",
                detail="No collider meshes found; cannot author runtime collision deltas.",
            )
        )

    if non_mesh_collision:
        result.blockers.append(
            Blocker(
                code="NON_MESH_COLLIDER",
                requirement="RB.COL.001",
                detail="Collision data sits on non-mesh prims; mesh deltas do not apply.",
                paths=sorted(non_mesh_collision),
            )
        )

    if result.rigid_bodies:
        orphan = [
            path
            for path in collider_paths
            if not any(Sdf.Path(path).HasPrefix(Sdf.Path(rb)) for rb in result.rigid_bodies)
        ]
        if orphan:
            result.blockers.append(
                Blocker(
                    code="COLLIDER_OUTSIDE_RIGID_BODY",
                    requirement="RB.COL.001",
                    detail="Collider meshes are not under any rigid body.",
                    paths=sorted(orphan),
                )
            )
        bodies_without = [
            rb
            for rb in result.rigid_bodies
            if not any(Sdf.Path(c).HasPrefix(Sdf.Path(rb)) for c in collider_paths)
        ]
        if bodies_without:
            result.blockers.append(
                Blocker(
                    code="RIGID_BODY_WITHOUT_COLLIDER",
                    requirement="RB.COL.001",
                    detail="Rigid bodies have no collider mesh; collider mapping is ambiguous.",
                    paths=sorted(bodies_without),
                )
            )
        ambiguous: list[str] = []
        for rb in result.rigid_bodies:
            rb_path = Sdf.Path(rb)
            meshes = [
                str(p.GetPath())
                for p in stage.Traverse()
                if p.IsA(UsdGeom.Mesh) and p.GetPath().HasPrefix(rb_path)
            ]
            if not meshes:
                continue
            marked = [m for m in meshes if m in collider_paths]
            if marked and len(marked) != len(meshes):
                ambiguous.append(f"{rb} ({len(marked)}/{len(meshes)} meshes are colliders)")
        if ambiguous:
            result.blockers.append(
                Blocker(
                    code="AMBIGUOUS_COLLIDER_SELECTION",
                    requirement="RB.COL.001",
                    detail="Some rigid bodies mix collider and non-collider meshes.",
                    paths=sorted(ambiguous),
                )
            )

    for prim in collision_prims:
        value = read_approximation(stage, prim)
        if value is not None:
            result.base_approximations[str(prim.GetPath())] = value

    if collision_prims:
        distinct = sorted(set(result.base_approximations.values()))
        annotated = len(result.base_approximations)
        if len(distinct) > 1:
            result.blockers.append(
                Blocker(
                    code="MIXED_BASE_APPROXIMATION",
                    requirement="RV.011",
                    detail=f"Colliders use mixed approximations ({', '.join(distinct)}).",
                    paths=[f"{p}={v}" for p, v in sorted(result.base_approximations.items())],
                )
            )
        elif annotated and annotated != len(collision_prims):
            result.blockers.append(
                Blocker(
                    code="PARTIAL_BASE_APPROXIMATION",
                    requirement="RV.011",
                    detail="Only some colliders author physics:approximation.",
                    paths=[f"{p}={v}" for p, v in sorted(result.base_approximations.items())],
                )
            )

    if body_work:
        result.blockers.append(
            Blocker(
                code="NEEDS_RUNTIME_BODY_WORK",
                requirement="FET_022_*",
                detail="Drives/mimics/actuators/scene APIs need handoff; adapters do not invent them.",
                paths=sorted(set(body_work)),
            )
        )

    if foreign_runtime:
        result.blockers.append(
            Blocker(
                code="FOREIGN_RUNTIME_ON_BASE",
                requirement="RV.011",
                detail="Newton/MuJoCo schemas already exist on the base.",
                paths=sorted(set(foreign_runtime)),
            )
        )

    if refuse_existing_variants:
        existing = [name for name in RUNTIME_VARIANT_SETS if name in root.GetVariantSets().GetNames()]
        if existing:
            result.blockers.append(
                Blocker(
                    code="EXISTING_VARIANT_SET",
                    requirement="RV.010",
                    detail="Runtime variant sets already exist; refusing to overwrite.",
                    paths=existing,
                )
            )

    if refuse_existing_payloads and asset_root is not None:
        existing_payloads = []
        for runtime in RUNTIME_VARIANT_SETS:
            path = payload_path(asset_root, runtime, prefer_existing=True)
            if path.is_file():
                existing_payloads.append(path.name)
        if existing_payloads:
            result.blockers.append(
                Blocker(
                    code="EXISTING_PAYLOAD",
                    requirement="RV.002",
                    detail="Runtime payload layers already exist; refusing to overwrite.",
                    paths=existing_payloads,
                )
            )

    # Silence unused layer binding for clarity of future root-layer checks.
    _ = layer
    return result


def preflight_minimal(stage: Usd.Stage) -> PreflightResult:
    """Fail-closed checks for FET_001_STANDARD@0.1.0 -> 1.0.1."""
    result = PreflightResult()
    root = stage.GetDefaultPrim()
    if not root:
        result.blockers.append(
            Blocker(
                code="NO_DEFAULT_PRIM",
                requirement="HI.001",
                detail="Stage has no defaultPrim.",
            )
        )
        return result

    result.default_prim_path = str(root.GetPath())
    result.default_prim_name = root.GetName()

    if not root.IsA(UsdGeom.Xformable):
        result.blockers.append(
            Blocker(
                code="ROOT_NOT_XFORMABLE",
                requirement="HI.001",
                detail="defaultPrim is not xformable.",
                paths=[result.default_prim_path],
            )
        )

    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        result.blockers.append(
            Blocker(
                code="UP_AXIS_REORIENTATION_REQUIRED",
                requirement="UN.006",
                detail=(
                    "Changing upAxis metadata alone would not reorient content; "
                    "a DCC-authored Z-up conversion is required."
                ),
            )
        )

    non_identity_ops: list[str] = []
    for op in UsdGeom.Xformable(root).GetOrderedXformOps():
        value = op.Get(Usd.TimeCode.Default())
        op_type = op.GetOpType()
        if op_type == UsdGeom.XformOp.TypeTranslate and value != Gf.Vec3d(0):
            non_identity_ops.append(f"{op.GetName()}={value}")
        elif op_type in (
            UsdGeom.XformOp.TypeRotateX,
            UsdGeom.XformOp.TypeRotateY,
            UsdGeom.XformOp.TypeRotateZ,
        ) and value not in (0, 0.0):
            non_identity_ops.append(f"{op.GetName()}={value}")
        elif op_type in (
            UsdGeom.XformOp.TypeRotateXYZ,
            UsdGeom.XformOp.TypeRotateXZY,
            UsdGeom.XformOp.TypeRotateYXZ,
            UsdGeom.XformOp.TypeRotateYZX,
            UsdGeom.XformOp.TypeRotateZXY,
            UsdGeom.XformOp.TypeRotateZYX,
        ) and value != Gf.Vec3f(0):
            non_identity_ops.append(f"{op.GetName()}={value}")
        elif op_type == UsdGeom.XformOp.TypeScale and value not in (Gf.Vec3f(1), Gf.Vec3d(1)):
            non_identity_ops.append(f"{op.GetName()}={value}")
        elif op_type == UsdGeom.XformOp.TypeTransform and value != Gf.Matrix4d(1):
            non_identity_ops.append(f"{op.GetName()} is non-identity")
    if non_identity_ops:
        result.blockers.append(
            Blocker(
                code="AMBIGUOUS_ASSET_ORIGIN",
                requirement="VG.025",
                detail=(
                    "defaultPrim has non-identity transforms; the adapter cannot infer "
                    "the intended placement pivot."
                ),
                paths=non_identity_ops,
            )
        )

    # Match HI.001's exception for the Omniverse-generated /Render settings
    # scope. It is ignorable only when it contains no asset Xforms, geometry,
    # or materials.
    def ignorable_render_root(prim: Usd.Prim) -> bool:
        if prim.GetName() != "Render" or prim == root:
            return False
        for child in Usd.PrimRange(prim):
            if child == prim:
                continue
            if child.IsA(UsdGeom.Xform) or child.IsA(UsdGeom.Gprim) or child.IsA(UsdShade.Material):
                return False
        return True

    outside = [
        str(prim.GetPath())
        for prim in stage.GetPseudoRoot().GetChildren()
        if prim != root and not ignorable_render_root(prim)
    ]
    if outside:
        result.blockers.append(
            Blocker(
                code="AMBIGUOUS_ROOT_HIERARCHY",
                requirement="HI.003",
                detail="Prims exist outside defaultPrim; hierarchy is ambiguous.",
                paths=sorted(outside)[:50],
            )
        )

    non_mesh_visual: list[str] = []
    bad_normals: list[str] = []
    missing_normals: list[str] = []
    for prim in stage.Traverse():
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            continue
        purpose = imageable.ComputePurpose()
        if purpose not in (UsdGeom.Tokens.default_, UsdGeom.Tokens.render):
            continue
        if any(prim.IsA(t) for t in _VISIBLE_NON_MESH):
            non_mesh_visual.append(str(prim.GetPath()))
            continue
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        normals = mesh.GetNormalsAttr()
        if not normals or not normals.HasAuthoredValueOpinion():
            # Fall back to primvars:normals
            pv = UsdGeom.PrimvarsAPI(prim).GetPrimvar("normals")
            if not pv or not pv.HasAuthoredValueOpinion():
                missing_normals.append(str(prim.GetPath()))
                continue
            values = pv.Get()
        else:
            values = normals.Get()
        if not values:
            missing_normals.append(str(prim.GetPath()))
            continue
        # Spot-check finite normals.
        for n in list(values)[:8]:
            if isinstance(n, (Gf.Vec3f, Gf.Vec3d)):
                comps = (float(n[0]), float(n[1]), float(n[2]))
                if not all(math.isfinite(c) for c in comps):
                    bad_normals.append(str(prim.GetPath()))
                    break
                length = (comps[0] ** 2 + comps[1] ** 2 + comps[2] ** 2) ** 0.5
                if length < 1e-8:
                    bad_normals.append(str(prim.GetPath()))
                    break

    if non_mesh_visual:
        result.blockers.append(
            Blocker(
                code="NON_MESH_VISIBLE_GEOMETRY",
                requirement="VG.MESH.001",
                detail="Visible non-mesh geometry cannot be upgraded without DCC conversion.",
                paths=sorted(non_mesh_visual),
            )
        )
    if missing_normals:
        result.blockers.append(
            Blocker(
                code="MISSING_NORMALS",
                requirement="VG.014",
                detail="Visible meshes are missing authored normals.",
                paths=sorted(missing_normals)[:50],
            )
        )
    if bad_normals:
        result.blockers.append(
            Blocker(
                code="INVALID_NORMALS",
                requirement="VG.014",
                detail="Visible meshes have invalid/zero normals.",
                paths=sorted(set(bad_normals))[:50],
            )
        )

    return result


def preflight_multibody_neutral(stage: Usd.Stage) -> PreflightResult:
    """Checks for FET_004_PHYSX peel / FET_004_STANDARD contract."""
    result = preflight_physics_topology(stage, require_colliders=False)
    if len(result.rigid_bodies) < 2:
        result.blockers.append(
            Blocker(
                code="NOT_MULTIBODY",
                requirement="RB.MB.001",
                detail="Fewer than two rigid bodies; FET_004 multibody peel is not applicable.",
                paths=result.rigid_bodies,
            )
        )
    if len(result.articulation_roots) > 1:
        result.blockers.append(
            Blocker(
                code="AMBIGUOUS_ARTICULATION_ROOT",
                requirement="JT.ART.002",
                detail="Multiple articulation roots; topology is ambiguous.",
                paths=result.articulation_roots,
            )
        )
    # Joint body0/body1 must resolve when joints exist.
    for joint_path in result.joints:
        joint = UsdPhysics.Joint(stage.GetPrimAtPath(joint_path))
        for rel_name in ("physics:body0", "physics:body1"):
            rel = joint.GetPrim().GetRelationship(rel_name)
            if not rel:
                continue
            targets = rel.GetTargets()
            if not targets:
                result.blockers.append(
                    Blocker(
                        code="JOINT_MISSING_BODY_TARGET",
                        requirement="JT.001",
                        detail=f"Joint {joint_path} has empty {rel_name}.",
                        paths=[joint_path],
                    )
                )
                continue
            for target in targets:
                if not stage.GetPrimAtPath(target):
                    result.blockers.append(
                        Blocker(
                            code="JOINT_DANGLING_BODY_TARGET",
                            requirement="JT.002",
                            detail=f"Joint {joint_path} {rel_name} targets missing prim {target}.",
                            paths=[joint_path, str(target)],
                        )
                    )
    return result


# ---------------------------------------------------------------------------
# Extract / peel PhysX opinions into physx payload
# ---------------------------------------------------------------------------


def _copy_attr_to_payload(src_attr: Sdf.AttributeSpec, dst_prim: Sdf.PrimSpec, name: str) -> None:
    if name in dst_prim.attributes:
        dst = dst_prim.attributes[name]
    else:
        dst = Sdf.AttributeSpec(dst_prim, name, src_attr.typeName)
    if src_attr.default is not None:
        dst.default = src_attr.default
    if src_attr.HasInfo("custom"):
        dst.SetInfo("custom", src_attr.GetInfo("custom"))
    if src_attr.HasInfo("variability"):
        dst.SetInfo("variability", src_attr.GetInfo("variability"))


def _merge_schemas_onto_payload(dst_prim: Sdf.PrimSpec, schemas: Iterable[str]) -> None:
    existing: list[str] = []
    if dst_prim.HasInfo("apiSchemas"):
        op = dst_prim.GetInfo("apiSchemas")
        for items in (op.explicitItems, op.prependedItems, op.appendedItems, op.addedItems):
            if items:
                existing.extend(str(i) for i in items)
    merged = list(dict.fromkeys(existing + [str(s) for s in schemas]))
    if merged:
        dst_prim.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=merged))


def extract_physx_opinions_to_payload(stage: Usd.Stage, *, include_joints: bool = True) -> MutationReport:
    """Move Physx*/approximation/mesh-collision opinions from root into physx.usda."""
    pre = preflight_physics_topology(stage, require_colliders=False)
    raise_if_blocked(pre)
    asset_root = asset_root_for_stage(stage)
    default_prim = stage.GetDefaultPrim()
    default_name = default_prim.GetName()
    default_path = default_prim.GetPath()
    payload = ensure_payload_layer(
        payload_path(asset_root, "PhysX", prefer_existing=True),
        default_name,
        doc="PhysX runtime overrides extracted from legacy PhysX-baked base",
    )
    root_layer = stage.GetRootLayer()
    moved_schemas: list[dict] = []
    moved_attrs: list[dict] = []

    with Usd.EditContext(stage, root_layer):
        for prim in stage.Traverse():
            prim_path = prim.GetPath()
            prim_spec = root_layer.GetPrimAtPath(prim_path)
            if prim_spec is None:
                continue

            schemas = authored_api_schemas(root_layer, prim_path)
            to_move = [s for s in schemas if _is_runtime_schema(s, "PhysX")]
            attr_names = [a.name for a in prim_spec.attributes if _is_runtime_attr(a.name, "PhysX")]

            if not include_joints and prim.IsA(UsdPhysics.Joint):
                # Rigid-body peel leaves joint PhysX for the multibody peel edge.
                continue

            if not to_move and not attr_names:
                continue

            if not prim_path.HasPrefix(default_path) and prim_path != default_path:
                raise UpgradeError(
                    [
                        Blocker(
                            code="PHYSX_OUTSIDE_DEFAULT_PRIM",
                            requirement="RV.011",
                            detail=f"PhysX opinions on {prim_path} are outside defaultPrim.",
                        )
                    ]
                )

            chain = () if prim_path == default_path else rel_chain(prim_path, default_path)
            dst_prim = ensure_over_chain(payload, default_name, chain)

            if to_move:
                _merge_schemas_onto_payload(dst_prim, to_move)
                for schema in to_move:
                    moved_schemas.append({"path": str(prim_path), "schema": schema})

            for name in attr_names:
                src_attr = prim_spec.attributes.get(name)
                if src_attr is None:
                    continue
                _copy_attr_to_payload(src_attr, dst_prim, name)
                moved_attrs.append({"path": str(prim_path), "attr": name, "value": str(src_attr.default)})
                prim_spec.RemoveProperty(src_attr)

            if to_move and prim_spec.HasInfo("apiSchemas"):
                op = prim_spec.GetInfo("apiSchemas")

                def keep(items):
                    if not items:
                        return []
                    return [i for i in items if not _is_runtime_schema(str(i), "PhysX")]

                kept_pre = keep(op.prependedItems)
                kept_exp = keep(op.explicitItems)
                kept_app = keep(op.appendedItems)
                if kept_exp:
                    prim_spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(kept_exp))
                elif kept_pre or kept_app:
                    prim_spec.SetInfo(
                        "apiSchemas",
                        Sdf.TokenListOp.Create(prependedItems=kept_pre, appendedItems=kept_app),
                    )
                else:
                    prim_spec.ClearInfo("apiSchemas")

    payload.Save()
    root_layer.Save()
    return MutationReport(
        name="extract_physx_opinions_to_payload",
        status="ok",
        detail="Extracted PhysX schemas/attrs to runnables/physics/physx payload.",
        artifacts={"schemas": moved_schemas, "attrs": moved_attrs, "payload": payload.realPath},
    )


def assert_neutral_base_clean(stage: Usd.Stage, *, allow_physx_joints: bool = False) -> None:
    """Neutral composition must not retain Physx*/Newton*/Mjc* schemas or attrs."""
    layer = stage.GetRootLayer()
    leaks: list[str] = []
    for prim in stage.Traverse():
        path = prim.GetPath()
        allow_this_prim = allow_physx_joints and prim.IsA(UsdPhysics.Joint)
        for schema in authored_api_schemas(layer, path):
            base = schema_base(schema)
            if not allow_this_prim and any(
                base.startswith(p)
                for p in _PHYSX_SCHEMA_PREFIXES + _NEWTON_SCHEMA_PREFIXES + _MUJOCO_SCHEMA_PREFIXES
            ):
                leaks.append(f"{path} schema={schema}")
        prim_spec = layer.GetPrimAtPath(path)
        if prim_spec is None:
            continue
        for attr in prim_spec.attributes:
            name = attr.name
            if not allow_this_prim and any(
                name.startswith(p) for p in ("physx", "Physx", "newton:", "mjc:")
            ):
                leaks.append(f"{path} attr={name}")
            if name == "physics:approximation":
                leaks.append(f"{path} attr=physics:approximation")
    if leaks:
        raise UpgradeError(
            [
                Blocker(
                    code="NEUTRAL_BASE_RUNTIME_LEAK",
                    requirement="RV.011",
                    detail="Neutral base still carries runtime schemas/attrs.",
                    paths=leaks[:50],
                )
            ]
        )


# ---------------------------------------------------------------------------
# Minimal upgrade
# ---------------------------------------------------------------------------


def apply_minimal_upgrade(stage: Usd.Stage) -> MutationReport:
    pre = preflight_minimal(stage)
    raise_if_blocked(pre)

    extents: list[str] = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Boundable):
            continue
        boundable = UsdGeom.Boundable(prim)
        extent = UsdGeom.Boundable.ComputeExtentFromPlugins(boundable, Usd.TimeCode.Default())
        if extent:
            boundable.CreateExtentAttr().Set(extent)
            extents.append(str(prim.GetPath()))

    stage.GetRootLayer().Save()
    return MutationReport(
        name="minimal_upgrade",
        status="ok",
        detail="Verified Z-up and authored extents where computable.",
        artifacts={"extents": extents, "upAxis": "Z"},
    )


# ---------------------------------------------------------------------------
# PhysX -> Standard peels
# ---------------------------------------------------------------------------


def apply_physx_to_standard_rigid_body(stage: Usd.Stage) -> MutationReport:
    pre = preflight_physics_topology(stage, require_colliders=True)
    # Mixed approximation is ok for peel (we preserve authored values); only refuse
    # topology ambiguity from preflight that is not approximation-policy.
    soft = {"MIXED_BASE_APPROXIMATION", "PARTIAL_BASE_APPROXIMATION", "UNEXPECTED_BASE_APPROXIMATION"}
    pre.blockers = [b for b in pre.blockers if b.code not in soft]
    # Peel should also refuse Newton/MuJoCo already on base.
    raise_if_blocked(pre)
    report = extract_physx_opinions_to_payload(stage, include_joints=False)
    # The following FET_004 peel owns joint-specific PhysX opinions.
    assert_neutral_base_clean(stage, allow_physx_joints=True)
    report.name = "physx_to_standard_rigid_body"
    return report


def apply_physx_to_standard_multibody(stage: Usd.Stage) -> MutationReport:
    pre = preflight_multibody_neutral(stage)
    # Approximation policy is handled by rigid-body peel / runtime deltas.
    pre.blockers = [
        b
        for b in pre.blockers
        if b.code not in {"MIXED_BASE_APPROXIMATION", "PARTIAL_BASE_APPROXIMATION", "NO_COLLIDERS"}
    ]
    raise_if_blocked(pre)
    report = extract_physx_opinions_to_payload(stage, include_joints=True)
    assert_neutral_base_clean(stage)
    report.name = "physx_to_standard_multibody"
    return report


# ---------------------------------------------------------------------------
# FET_000 scaffolding
# ---------------------------------------------------------------------------


def _update_variant_metadata(stage: Usd.Stage, runtime: str, default_prim_path: str) -> None:
    layer = stage.GetRootLayer()
    cld = dict(layer.customLayerData or {})
    sm = dict(cld.get("SimReady_Metadata") or {})
    variants = dict(sm.get("Variants") or {})
    physics = dict(variants.get("Physics") or {})
    physics[runtime] = {
        "prim": default_prim_path,
        "variantSetName": runtime,
        "activateOption": "Enabled",
    }
    variants["Physics"] = physics
    sm["Variants"] = variants
    cld["SimReady_Metadata"] = sm
    layer.customLayerData = cld


def ensure_runtime_variant_set(prim: Usd.Prim, runtime: str, payload_rel: str) -> None:
    vsets = prim.GetVariantSets()
    if runtime not in vsets.GetNames():
        vsets.AddVariantSet(runtime)
    vset = vsets.GetVariantSet(runtime)
    for opt in ("Disabled", "Enabled"):
        if opt not in vset.GetVariantNames():
            vset.AddVariant(opt)

    # Author Enabled with pure payload prepend only.
    vset.SetVariantSelection("Enabled")
    with vset.GetVariantEditContext():
        payloads = prim.GetPayloads()
        # Clear only within this variant edit target.
        payloads.ClearPayloads()
        payloads.AddPayload(payload_rel)

    # Default selection Disabled; Disabled variant remains empty.
    vset.SetVariantSelection("Disabled")


def apply_runtime_scaffold(stage: Usd.Stage, runtime: str) -> MutationReport:
    if runtime not in RUNTIME_VARIANT_SETS:
        raise ValueError(runtime)
    asset_root = asset_root_for_stage(stage)
    root = stage.GetDefaultPrim()
    if not root:
        raise UpgradeError(
            [
                Blocker(
                    code="NO_DEFAULT_PRIM",
                    requirement="RV.001",
                    detail="Stage has no defaultPrim.",
                )
            ]
        )

    if runtime in root.GetVariantSets().GetNames():
        # Idempotent only if Disabled empty + Enabled already points at expected payload.
        raise UpgradeError(
            [
                Blocker(
                    code="EXISTING_VARIANT_SET",
                    requirement="RV.010",
                    detail=f"Variant set {runtime} already exists; refusing to clobber.",
                    paths=[runtime],
                )
            ]
        )

    path = payload_path(asset_root, runtime, prefer_existing=True)
    ensure_payload_layer(
        path,
        root.GetName(),
        doc=f"{runtime} runtime overrides",
    )
    rel = f"./runnables/physics/{path.name}"
    ensure_runtime_variant_set(root, runtime, rel)
    _update_variant_metadata(stage, runtime, str(root.GetPath()))
    stage.GetRootLayer().Save()
    return MutationReport(
        name=f"scaffold_{runtime.lower()}",
        status="ok",
        detail=f"Authored {runtime} variant set + payload scaffolding.",
        artifacts={"payload": str(path), "payload_rel": rel},
    )


# ---------------------------------------------------------------------------
# FET_003 runtime deltas (write into payloads)
# ---------------------------------------------------------------------------


def _collider_chains(stage: Usd.Stage, pre: PreflightResult) -> list[tuple[str, ...]]:
    default_path = Sdf.Path(pre.default_prim_path)
    return [rel_chain(Sdf.Path(p), default_path) for p in pre.colliders]


def _material_chains(stage: Usd.Stage, pre: PreflightResult) -> list[tuple[str, ...]]:
    default_path = Sdf.Path(pre.default_prim_path)
    return [rel_chain(Sdf.Path(p), default_path) for p in pre.physics_materials]


def _author_leaf_schemas_attrs(
    layer: Sdf.Layer,
    default_name: str,
    chain: tuple[str, ...],
    schemas: list[str],
    attrs: dict[str, object],
) -> None:
    prim = ensure_over_chain(layer, default_name, chain)
    _merge_schemas_onto_payload(prim, schemas)
    for name, value in attrs.items():
        if name in prim.attributes:
            attr = prim.attributes[name]
        else:
            if isinstance(value, str):
                type_name = Sdf.ValueTypeNames.Token
            elif isinstance(value, float):
                type_name = Sdf.ValueTypeNames.Float
            elif isinstance(value, int):
                type_name = Sdf.ValueTypeNames.Int
            else:
                type_name = Sdf.ValueTypeNames.Token
            attr = Sdf.AttributeSpec(prim, name, type_name)
        attr.default = value


def apply_standard_to_physx_rigid_body(stage: Usd.Stage) -> MutationReport:
    pre = preflight_physics_topology(stage, require_colliders=True)
    # After peel, approximations should be gone from base; refuse mixed leftover policy.
    raise_if_blocked(pre)
    asset_root = asset_root_for_stage(stage)
    path = payload_path(asset_root, "PhysX", prefer_existing=True)
    layer = ensure_payload_layer(path, pre.default_prim_name, doc="PhysX rigid-body overrides")
    for chain in _collider_chains(stage, pre):
        _author_leaf_schemas_attrs(
            layer,
            pre.default_prim_name,
            chain,
            ["PhysxCollisionAPI", "PhysxSDFMeshCollisionAPI", "PhysicsMeshCollisionAPI"],
            {"physics:approximation": PHYSX_DELTA_APPROXIMATION},
        )
    layer.Save()
    return MutationReport(
        name="standard_to_physx_rigid_body",
        status="ok",
        detail="Authored PhysX SDF mesh-collision delta into physx payload.",
        artifacts={"payload": str(path), "colliders": pre.colliders},
    )


def apply_standard_to_newton_rigid_body(stage: Usd.Stage) -> MutationReport:
    pre = preflight_physics_topology(stage, require_colliders=True)
    raise_if_blocked(pre)
    asset_root = asset_root_for_stage(stage)
    path = payload_path(asset_root, "Newton", prefer_existing=True)
    layer = ensure_payload_layer(path, pre.default_prim_name, doc="Newton rigid-body overrides")
    for chain in _collider_chains(stage, pre):
        _author_leaf_schemas_attrs(
            layer,
            pre.default_prim_name,
            chain,
            ["NewtonCollisionAPI", "PhysicsMeshCollisionAPI", "NewtonMeshCollisionAPI"],
            {"newton:contactGap": 0.0},
        )
    for chain in _material_chains(stage, pre):
        _author_leaf_schemas_attrs(
            layer,
            pre.default_prim_name,
            chain,
            ["NewtonMaterialAPI"],
            {
                "newton:torsionalFriction": 0.005,
                "newton:rollingFriction": 0.0001,
            },
        )
    # NEWTON.MAS.001 validates NewtonMassAPI when present; it does not require
    # the API on every rigid body. Apply it only where a neutral MassAPI is
    # already authored, and never invent a mass source or reject a valid
    # inherited/collider mass arrangement.
    default_path = Sdf.Path(pre.default_prim_path)
    for rb in pre.rigid_bodies:
        prim = stage.GetPrimAtPath(rb)
        schemas = all_schemas(stage, prim)
        if "PhysicsMassAPI" not in schemas and not prim.HasAPI(UsdPhysics.MassAPI):
            continue
        chain = rel_chain(Sdf.Path(rb), default_path)
        _author_leaf_schemas_attrs(layer, pre.default_prim_name, chain, ["NewtonMassAPI"], {})
    layer.Save()
    return MutationReport(
        name="standard_to_newton_rigid_body",
        status="ok",
        detail="Authored Newton collider/material/mass-API delta into newton payload.",
        artifacts={"payload": str(path), "colliders": pre.colliders, "materials": pre.physics_materials},
    )


def apply_standard_to_mujoco_rigid_body(stage: Usd.Stage) -> MutationReport:
    pre = preflight_physics_topology(stage, require_colliders=True)
    raise_if_blocked(pre)
    asset_root = asset_root_for_stage(stage)
    path = payload_path(asset_root, "MuJoCo", prefer_existing=True)
    layer = ensure_payload_layer(path, pre.default_prim_name, doc="MuJoCo rigid-body overrides")
    for chain in _collider_chains(stage, pre):
        _author_leaf_schemas_attrs(
            layer,
            pre.default_prim_name,
            chain,
            ["MjcCollisionAPI", "PhysicsMeshCollisionAPI", "MjcMeshCollisionAPI"],
            {
                "physics:approximation": MUJOCO_DELTA_APPROXIMATION,
                "mjc:group": 0,
                "mjc:inertia": "convex",
                "mjc:maxhullvert": -1,
            },
        )
    layer.Save()
    return MutationReport(
        name="standard_to_mujoco_rigid_body",
        status="ok",
        detail="Authored MuJoCo convexHull mesh-collision delta into mujoco payload.",
        artifacts={"payload": str(path), "colliders": pre.colliders},
    )


# ---------------------------------------------------------------------------
# FET_004 runtime edges
# ---------------------------------------------------------------------------


def apply_standard_to_physx_multibody(stage: Usd.Stage) -> MutationReport:
    """Preserve/restore PhysX joint opinions in physx payload; do not create joints."""
    pre = preflight_multibody_neutral(stage)
    # Soften foreign/approx; hard-fail topology.
    pre.blockers = [
        b
        for b in pre.blockers
        if b.code
        not in {
            "MIXED_BASE_APPROXIMATION",
            "PARTIAL_BASE_APPROXIMATION",
            "FOREIGN_RUNTIME_ON_BASE",
            "NO_COLLIDERS",
        }
    ]
    raise_if_blocked(pre)
    # Joint PhysX should already live in physx.usda from peel; ensure payload exists.
    asset_root = asset_root_for_stage(stage)
    path = payload_path(asset_root, "PhysX", prefer_existing=True)
    ensure_payload_layer(path, pre.default_prim_name, doc="PhysX multibody overrides")
    assert_neutral_base_clean(stage)
    return MutationReport(
        name="standard_to_physx_multibody",
        status="ok",
        detail="Validated multibody topology; PhysX joint opinions remain in physx payload.",
        artifacts={"payload": str(path), "joints": pre.joints, "rigid_bodies": pre.rigid_bodies},
    )


def apply_standard_to_newton_multibody(stage: Usd.Stage) -> MutationReport:
    pre = preflight_multibody_neutral(stage)
    pre.blockers = [
        b
        for b in pre.blockers
        if b.code
        not in {
            "MIXED_BASE_APPROXIMATION",
            "PARTIAL_BASE_APPROXIMATION",
            "NO_COLLIDERS",
            "FOREIGN_RUNTIME_ON_BASE",
        }
    ]
    raise_if_blocked(pre)
    return MutationReport(
        name="standard_to_newton_multibody",
        status="ok",
        detail="Validate-only Newton multibody edge; joint topology stays neutral.",
        artifacts={"joints": pre.joints, "rigid_bodies": pre.rigid_bodies},
    )


def apply_standard_to_mujoco_multibody(stage: Usd.Stage) -> MutationReport:
    pre = preflight_multibody_neutral(stage)
    pre.blockers = [
        b
        for b in pre.blockers
        if b.code
        not in {
            "MIXED_BASE_APPROXIMATION",
            "PARTIAL_BASE_APPROXIMATION",
            "NO_COLLIDERS",
            "FOREIGN_RUNTIME_ON_BASE",
        }
    ]
    raise_if_blocked(pre)
    return MutationReport(
        name="standard_to_mujoco_multibody",
        status="ok",
        detail="Validate-only MuJoCo multibody edge; joint topology stays neutral.",
        artifacts={"joints": pre.joints, "rigid_bodies": pre.rigid_bodies},
    )


# ---------------------------------------------------------------------------
# Isolation inspection + metadata stamp
# ---------------------------------------------------------------------------


def inspect_neutral_runtime_isolation(stage: Usd.Stage) -> MutationReport:
    """Explicit composition checks beyond optional CLI feature selection."""
    root = stage.GetDefaultPrim()
    if not root:
        raise UpgradeError(
            [Blocker(code="NO_DEFAULT_PRIM", requirement="RV.011", detail="No defaultPrim.")]
        )
    assert_neutral_base_clean(stage)

    issues: list[str] = []
    vsets = root.GetVariantSets()
    present = [name for name in RUNTIME_VARIANT_SETS if name in vsets.GetNames()]

    # Neutral: all disabled.
    for name in present:
        vsets.GetVariantSet(name).SetVariantSelection("Disabled")
    assert_neutral_base_clean(stage)

    def composed_runtime_leaks(enabled: str) -> list[str]:
        leaks: list[str] = []
        for name in present:
            vsets.GetVariantSet(name).SetVariantSelection("Enabled" if name == enabled else "Disabled")
        # Force recompose by reading schemas through composed prims.
        foreign_prefixes = {
            "PhysX": _NEWTON_SCHEMA_PREFIXES + _MUJOCO_SCHEMA_PREFIXES,
            "Newton": _PHYSX_SCHEMA_PREFIXES + _MUJOCO_SCHEMA_PREFIXES,
            "MuJoCo": _PHYSX_SCHEMA_PREFIXES + _NEWTON_SCHEMA_PREFIXES,
        }[enabled]
        for prim in stage.Traverse():
            for schema in prim.GetAppliedSchemas():
                base = schema_base(str(schema))
                if any(base.startswith(p) for p in foreign_prefixes):
                    leaks.append(f"{enabled}:{prim.GetPath()} schema={schema}")
            for attr in prim.GetAttributes():
                name = attr.GetName()
                if enabled != "PhysX" and name.startswith("physx"):
                    leaks.append(f"{enabled}:{prim.GetPath()} attr={name}")
                if enabled != "Newton" and name.startswith("newton:"):
                    leaks.append(f"{enabled}:{prim.GetPath()} attr={name}")
                if enabled != "MuJoCo" and name.startswith("mjc:"):
                    leaks.append(f"{enabled}:{prim.GetPath()} attr={name}")
                if enabled == "Newton" and name == "physics:approximation":
                    value = attr.Get()
                    if value is not None and str(value) == "sdf":
                        leaks.append(f"{enabled}:{prim.GetPath()} physics:approximation=sdf")
        return leaks

    for runtime in present:
        issues.extend(composed_runtime_leaks(runtime))

    # Restore disabled defaults.
    for name in present:
        vsets.GetVariantSet(name).SetVariantSelection("Disabled")
    stage.GetRootLayer().Save()

    if issues:
        raise UpgradeError(
            [
                Blocker(
                    code="RUNTIME_ISOLATION_FAILURE",
                    requirement="RV.011",
                    detail="Composed runtime selections leak foreign schemas/attrs.",
                    paths=issues[:50],
                )
            ]
        )
    return MutationReport(
        name="inspect_isolation",
        status="ok",
        detail="Neutral and per-runtime compositions look isolated.",
        artifacts={"variant_sets": present},
    )


def stamp_target_profile(
    stage: Usd.Stage,
    profile: str,
    version: str,
    selected_optional_features: list[str],
) -> MutationReport:
    layer = stage.GetRootLayer()
    cld = dict(layer.customLayerData or {})
    sm = dict(cld.get("SimReady_Metadata") or {})
    validation = dict(sm.get("validation") or {})
    validation["profile"] = profile
    validation["profile_version"] = version
    validation["selected_optional_features"] = ",".join(selected_optional_features)
    sm["validation"] = validation
    cld["SimReady_Metadata"] = sm
    layer.customLayerData = cld
    layer.Save()
    return MutationReport(
        name="stamp_profile",
        status="ok",
        detail=f"Stamped {profile}@{version}.",
        artifacts={"selected_optional_features": selected_optional_features},
    )


# Adapters only mutate USD layers / create USD sidecars. Non-USD payload
# (textures, glb, mdl, …) is shared via hardlink/symlink so staging stays cheap.
_USD_COPY_SUFFIXES = {".usd", ".usda", ".usdc", ".usdz"}


def _make_writable(path: Path) -> None:
    """Mark a real path writable. Never call on a symlink (would mutate the target)."""
    if path.is_symlink():
        return
    path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _link_or_copy(src: Path, dst: Path) -> str:
    """Share ``src`` at ``dst`` without duplicating bytes when the FS allows it.

    Preference order:
      1. hardlink (same filesystem; looks like a normal file)
      2. symlink (cross-device fallback)
      3. full copy2 (last resort)

    Returns ``"link"``, ``"symlink"``, or ``"copy"``.
    """
    try:
        os.link(src, dst)
        return "link"
    except OSError as exc:
        # EXDEV: cross-device. EPERM/EACCES: some FS / mount flags disallow links.
        if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.ENOSYS):
            raise
    try:
        os.symlink(src, dst)
        return "symlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def copy_package_transactional(source: Path, dest: Path) -> None:
    """Stage a mutable working copy of ``source`` at ``dest``.

    USD files (``.usd`` / ``.usda`` / ``.usdc`` / ``.usdz``) are real-copied and
    made writable so adapters can ``Save()`` / ``CreateNew`` without touching the
    source package. Everything else is hardlinked when possible (symlink, then
    copy, as fallbacks) so large textures/meshes are not duplicated.

    Never chmod a hardlink/symlink: that would flip the source file's mode.
    """
    source = source.resolve()
    dest = dest.resolve()
    if dest.exists():
        raise UpgradeError(
            [
                Blocker(
                    code="OUTPUT_EXISTS",
                    requirement="runner",
                    detail=f"Refusing to overwrite existing output {dest}.",
                )
            ]
        )

    dest.mkdir(parents=True)
    _make_writable(dest)

    for src_path in source.rglob("*"):
        rel = src_path.relative_to(source)
        dst_path = dest / rel
        src_lstat = src_path.lstat()

        if stat.S_ISDIR(src_lstat.st_mode):
            dst_path.mkdir(parents=True, exist_ok=True)
            _make_writable(dst_path)
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = src_path.suffix.lower()
        is_symlink = stat.S_ISLNK(src_lstat.st_mode)

        # Preserve non-USD symlinks as symlinks (same relative/absolute target).
        if is_symlink and suffix not in _USD_COPY_SUFFIXES:
            os.symlink(os.readlink(src_path), dst_path)
            continue

        if suffix in _USD_COPY_SUFFIXES:
            # Real copy so Save()/CreateNew cannot mutate the source inode.
            shutil.copy2(src_path, dst_path, follow_symlinks=True)
            _make_writable(dst_path)
            continue

        # Non-USD payload: share bytes with the source when possible.
        real_src = src_path.resolve() if is_symlink else src_path
        kind = _link_or_copy(real_src, dst_path)
        if kind == "copy":
            _make_writable(dst_path)


def blockers_to_dicts(blockers: list[Blocker]) -> list[dict]:
    return [
        {"code": b.code, "requirement": b.requirement, "detail": b.detail, "paths": b.paths}
        for b in blockers
    ]


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
