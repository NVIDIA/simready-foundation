---
name: simready-foundation-conform-fet-008-object-forward
description: Author explicit local Object Forward from a caller-provided vector or visual evidence, then validate the sole requirement AF.001 on staged output.
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - object-forward
---

# Conform Object Forward

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

Targets `FET008_ObjectForward.0-1-0`, which owns AF.001 directly.
Read the feature and AF.001 docs first. Preserve source assets and reports.

1. Copy the asset and required dependencies into the requested output directory.
2. Select the defaultPrim or explicitly requested component; inspect geometry,
   renders or viewport evidence to identify its semantic front. Record the
   rationale and mapping into prim-local coordinates. If neither the caller
   nor evidence identifies a front, ask for intent instead of guessing.
3. Supply a finite unit vector to
   `simready.foundation.tier_core.asset_frame.author_forward_direction` on the
   staged prim. Repair malformed existing properties explicitly against AF.001
   before calling; the helper intentionally rejects conflicting authored data.
4. Preserve native upAxis. Do not author a custom upDirection or replace GR.002.
   Components author their own facing; there is no namespace inheritance.
5. Save staged layers and rerun the narrow AF.001 gate. Preserve its report.
6. When runtime evidence is requested, run object_forward_contract and
   object_forward_camera_response through simready-evaluate in Kit/Isaac to
   query AF.001 data and measure FET008 camera consumption on the loaded stage. Preserve metrics/captures and report runtime unavailability honestly.
   Profile conformance requires the other gates too.

Automatic migration from an asset with no semantic front is not defined.
