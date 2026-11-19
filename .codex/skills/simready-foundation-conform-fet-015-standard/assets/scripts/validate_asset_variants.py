#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Run the AssetVariants gate (AV.001-AV.010) against a staged asset.

This is the narrow validation gate shared by the asset-variation conform skills
(FET013-FET016). It runs the registered ``AV.*`` rule checkers from the installed
``simready-foundation-tier-core`` and reports PASS/FAIL per requirement. With
``--diagnose`` it also prints, for every declared variation set, the composed
visual and collision envelope of each option (to locate an AV.005/006/007
envelope drift) and the asset's collider/mass inventory (to decide whether
FET015/FET016 apply and to satisfy AV.009).

The AV gate is DRIVEN by discovery metadata: with no
``customLayerData.SimReady_Metadata.Variants`` declared, every checker passes
vacuously. The script flags that case so a vacuous pass is never mistaken for
conformance.

Run it with the Python environment that has the SimReady tier installed, e.g.::

    python validate_asset_variants.py staged/asset.usda --diagnose --report av-report.json

Exit code is 0 when every requirement passes, 1 otherwise (or on a load error).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# AV requirement id -> checker class name in the asset_variants validation module.
CHECKERS = [
    ("AV.001", "VariationDiscoveryMetadataChecker"),
    ("AV.002", "VariationVariantSetChecker"),
    ("AV.003", "VariationOptionComposabilityChecker"),
    ("AV.004", "VariationSectionPurityChecker"),
    ("AV.005", "VisualEnvelopeInvariantChecker"),
    ("AV.006", "CollisionEnvelopeInvariantChecker"),
    ("AV.007", "ImpactClassHonestyChecker"),
    ("AV.008", "ConditionalPresenceChecker"),
    ("AV.009", "AuthoredPhysicalPropertiesChecker"),
    ("AV.010", "VariationStabilityChecker"),
]


def _load_modules():
    try:
        from simready.foundation.tier_core.rules_and_reqs.core.asset_variants import (
            validation as av_validation,
        )
        from simready.foundation.tier_core import asset_variants as av
    except Exception as exc:  # noqa: BLE001 - surface a clear install hint
        print(
            "ERROR: could not import the AssetVariants validators from "
            "simready-foundation-tier-core.\n"
            "Install or upgrade the tier that ships FET013-FET016, e.g.:\n"
            "  pip install --upgrade simready-foundation-tier-core\n"
            f"Underlying import error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return av_validation, av


def _issue_messages(checker) -> list[str]:
    """Collect human-readable messages from a BaseRuleChecker run."""
    out = []
    for issue in checker.GetIssues():
        msg = getattr(issue, "message", None) or str(issue)
        out.append(msg)
    return out


def _fmt(vec):
    return None if vec is None else tuple(round(float(v), 5) for v in vec)


def run_gate(stage, av_validation, av):
    results = []
    for code, cls_name in CHECKERS:
        cls = getattr(av_validation, cls_name)
        checker = cls()
        checker.CheckStage(stage)
        messages = _issue_messages(checker)
        results.append({"requirement": code, "passed": not messages, "messages": messages})
    return results


def diagnose(stage, av):
    from pxr import Usd, UsdPhysics  # local import; only needed for --diagnose

    root_layer = stage.GetRootLayer()
    default_prim = stage.GetDefaultPrim()
    report = {"declared_sets": [], "collider_prims": [], "mass_prims": [], "notes": []}

    entries = list(av.iter_variation_entries(stage))
    if not entries:
        report["notes"].append(
            "No SimReady_Metadata.Variants declared: the AV gate passes vacuously. "
            "Declare each variation set before trusting a PASS."
        )

    tol = av.ENVELOPE_TOLERANCE_M
    baseline_vis = _fmt(av.envelope_size(av.visual_envelope(stage)))
    baseline_col = _fmt(av.envelope_size(av.collision_envelope(stage)))
    report["baseline_envelope"] = {"visual": baseline_vis, "collision": baseline_col, "tolerance_m": tol}

    present = set(default_prim.GetVariantSets().GetNames()) if default_prim and default_prim.IsValid() else set()
    for category, name, entry in entries:
        set_info = {
            "category": category,
            "variantSetName": name,
            "impactClass": entry.get("impactClass"),
            "default": entry.get("default"),
            "options": [],
            "present_on_default_prim": name in present,
        }
        if name in present:
            for option in av.option_names(default_prim, name):
                try:
                    composed = av.compose_with_selection(root_layer, {name: option})
                    vis = av.envelope_size(av.visual_envelope(composed))
                    col = av.envelope_size(av.collision_envelope(composed))
                except Exception as exc:  # noqa: BLE001
                    set_info["options"].append({"option": option, "error": str(exc)})
                    continue
                set_info["options"].append({
                    "option": option,
                    "visual": _fmt(vis),
                    "collision": _fmt(col),
                    "visual_within_tol": _axes_within(av, baseline_vis, _fmt(vis), tol),
                    "collision_within_tol": _axes_within(av, baseline_col, _fmt(col), tol),
                })
        report["declared_sets"].append(set_info)

    if default_prim and default_prim.IsValid():
        for prim in Usd.PrimRange(default_prim):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                report["collider_prims"].append(str(prim.GetPath()))
            if prim.HasAPI(UsdPhysics.MassAPI):
                report["mass_prims"].append(str(prim.GetPath()))
    if not report["collider_prims"] and not report["mass_prims"]:
        report["notes"].append(
            "No UsdPhysics CollisionAPI or MassAPI present: FET015 (Collision) is not "
            "applicable (no colliders to vary, no authored mass for AV.009)."
        )
    return report


def _axes_within(av, a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AV.001-AV.010 on a staged asset.")
    parser.add_argument("asset_path", type=Path)
    parser.add_argument("--diagnose", action="store_true", help="Also print per-option envelopes and collider/mass inventory.")
    parser.add_argument("--report", type=Path, help="Write the full JSON result here.")
    args = parser.parse_args()

    av_validation, av = _load_modules()
    from pxr import Usd

    stage = Usd.Stage.Open(str(args.asset_path))
    if stage is None:
        print(f"ERROR: failed to open stage: {args.asset_path}", file=sys.stderr)
        return 1

    results = run_gate(stage, av_validation, av)
    diagnostics = diagnose(stage, av) if args.diagnose else None

    default_prim = stage.GetDefaultPrim()
    payload = {
        "asset_path": str(args.asset_path),
        "default_prim": str(default_prim.GetPath()) if default_prim and default_prim.IsValid() else None,
        "results": results,
        "diagnostics": diagnostics,
        "status": "PASS" if all(r["passed"] for r in results) else "FAIL",
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # Human-readable console summary.
    print(f"Asset: {payload['asset_path']}")
    print(f"defaultPrim: {payload['default_prim']}")
    if diagnostics:
        for note in diagnostics.get("notes", []):
            print(f"  NOTE: {note}")
        base = diagnostics["baseline_envelope"]
        print(f"  baseline visual={base['visual']} collision={base['collision']} tol={base['tolerance_m']} m")
        for s in diagnostics["declared_sets"]:
            print(f"  [{s['category']}] {s['variantSetName']} ({s['impactClass']}) default={s['default']}")
            for opt in s["options"]:
                if "error" in opt:
                    print(f"      {opt['option']}: compose error: {opt['error']}")
                else:
                    flags = []
                    if not opt["visual_within_tol"]:
                        flags.append("VISUAL DRIFT")
                    if not opt["collision_within_tol"]:
                        flags.append("COLLISION DRIFT")
                    tag = ("  <- " + ", ".join(flags)) if flags else ""
                    print(f"      {opt['option']}: visual={opt['visual']} collision={opt['collision']}{tag}")
        print(f"  colliders={diagnostics['collider_prims'] or 'NONE'} mass={diagnostics['mass_prims'] or 'NONE'}")
    print("-" * 60)
    for r in results:
        if r["passed"]:
            print(f"  PASS {r['requirement']}")
        else:
            print(f"  FAIL {r['requirement']}:")
            for m in r["messages"]:
                print(f"        - {m}")
    print("-" * 60)
    print("RESULT:", payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
