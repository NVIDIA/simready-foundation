# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Network-equipment checks for the AIF-Entity and Networking profiles."""
import math

from pxr import Sdf, Usd
import usd_validation_nvidia
import simready.foundation.tier_aif.requirements as cap

from .. import _stage, equipment_classes


def _is_network(stage):
    spec = _stage.properties_prim_spec(stage)
    root = stage.GetDefaultPrim()
    authored = spec.attributes.get("aif:core:assetClass") if spec else None
    composed = root.GetAttribute("aif:core:assetClass") if root else None
    values = (authored.default if authored else None, composed.Get() if composed else None)
    return any(isinstance(value, str) and equipment_classes.normalize_03(value) == "network-equipment"
               for value in values)


def _attribute(stage, name, type_name, valid):
    """Require a typed value in Properties and in the composed interface."""
    spec = _stage.properties_prim_spec(stage)
    prim = stage.GetDefaultPrim()
    if not spec or not prim:
        return False
    authored = spec.attributes.get(name)
    composed = prim.GetAttribute(name)
    return bool(
        authored and authored.typeName == type_name
        and authored.default is not None and valid(authored.default)
        and composed and composed.GetTypeName() == type_name
        and composed.Get() is not None and valid(composed.Get())
    )


def _nonempty(value):
    return bool(value.strip())


def _positive(value):
    return math.isfinite(value) and value > 0


def _nonnegative(value):
    return math.isfinite(value) and value >= 0


@usd_validation_nvidia.register_rule("AIF-NetworkEquipment")
@usd_validation_nvidia.register_requirements(cap.NetworkEquipmentRequirements.NET_001, override=True)
class NetworkEquipmentMetadataChecker(usd_validation_nvidia.BaseRuleChecker):
    """Validate network class identity and inherited physical metadata types."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not _is_network(stage):
            return
        string = Sdf.ValueTypeNames.String
        specs = {
            "aif:core:assetClass": (string, lambda value: value == "network-equipment"),
            **{f"aif:core:{name}": (string, _nonempty)
               for name in ("manufacturer", "modelNumber", "assetVersion")},
            **{f"aif:core:{name}": (Sdf.ValueTypeNames.Float, _positive)
               for name in ("height", "width", "depth", "weight")},
            **{f"aif:core:{name}": (Sdf.ValueTypeNames.Float, _nonnegative)
               for name in ("installationClearance", "accessibilityRequirement")},
        }
        invalid = [name for name, (kind, valid) in specs.items()
                   if not _attribute(stage, name, kind, valid)]
        if invalid:
            self._AddFailedCheck(
                requirement=cap.NetworkEquipmentRequirements.NET_001,
                message="Network equipment has missing, mistyped or invalid metadata in its "
                        "Properties layer or composed default prim: " + ", ".join(invalid),
                at=stage,
            )
            return


@usd_validation_nvidia.register_rule("AIF-NetworkEquipment")
@usd_validation_nvidia.register_requirements(cap.NetworkEquipmentRequirements.NET_002, override=True)
class NetworkNodeConfigurationChecker(usd_validation_nvidia.BaseRuleChecker):
    """Require positive integer allocations and an optional opaque image string."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not _is_network(stage):
            return
        invalid = [f"aif:spec:{name}" for name in ("cpuAllocation", "memory_MB", "storage_GB")
                   if not _attribute(stage, f"aif:spec:{name}", Sdf.ValueTypeNames.Int,
                                     lambda value: value > 0)]
        name = "aif:spec:osImage"
        spec = _stage.properties_prim_spec(stage)
        prim = stage.GetDefaultPrim()
        if ((spec and name in spec.properties) or (prim and prim.GetProperty(name))):
            if not _attribute(stage, name, Sdf.ValueTypeNames.String, _nonempty):
                invalid.append(name)
        if invalid:
            self._AddFailedCheck(
                requirement=cap.NetworkEquipmentRequirements.NET_002,
                message="Network node configuration requires positive int CPU/memory_MB/storage_GB "
                        "allocations and a non-empty string osImage when authored: " + ", ".join(invalid),
                at=stage,
            )


@usd_validation_nvidia.register_rule("AIF-NetworkEquipment")
@usd_validation_nvidia.register_requirements(cap.NetworkEquipmentRequirements.NET_003, override=True)
class NetworkEquipmentPortsChecker(usd_validation_nvidia.BaseRuleChecker):
    """Require a network-domain port in the equipment's CP2 interface."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not _is_network(stage):
            return
        root = stage.GetDefaultPrim()
        scope = root.GetChild("ConnectionPoints") if root else None
        if scope and scope.GetTypeName() == "Scope":
            for port in scope.GetChildren():
                attr = port.GetAttribute("simready:connectionPoint:domain")
                if (port.GetTypeName() == "Xform" and attr
                        and attr.GetTypeName() == Sdf.ValueTypeNames.Token
                        and attr.Get() == "network"):
                    return
        self._AddFailedCheck(
            requirement=cap.NetworkEquipmentRequirements.NET_003,
            message="Network equipment requires at least one direct network-domain Xform port "
                    "under its default prim's ConnectionPoints Scope.",
            at=stage,
        )


@usd_validation_nvidia.register_rule("AIF-NetworkEquipment")
@usd_validation_nvidia.register_requirements(cap.NetworkEquipmentRequirements.NET_004, override=True)
class NetworkDeviceEligibilityChecker(usd_validation_nvidia.BaseRuleChecker):
    """Require the network equipment class for a dedicated Networking profile."""

    def CheckStage(self, stage: Usd.Stage) -> None:
        if not _attribute(stage, "aif:core:assetClass", Sdf.ValueTypeNames.String,
                          lambda value: value == "network-equipment"):
            self._AddFailedCheck(
                requirement=cap.NetworkEquipmentRequirements.NET_004,
                message="Networking requires aif:core:assetClass to be the string "
                        "'network-equipment' in both the Properties layer and composed default prim.",
                at=stage,
            )
