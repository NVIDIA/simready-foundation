---
name: simready-foundation-conform-fet-009-standard
description: "Use for repairing FET009_MaterialCoverage failures, where preview_surface_renders, openpbr_renders or mdl_renders measures rendered material coverage below min_material_coverage. Binds the uncovered geometry to the asset's own materials (VM.MAT.001) on staged output, then reruns the static gate and the coverage tests in Kit."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - materials
---

# Conform Material Coverage

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

Targets `FET009_MaterialCoverage.0-1-0`. A failing coverage test means part of the asset's
silhouette renders without one of the asset's own materials. Read the feature page, the
`VM.MAT.001` requirement page and the failing test's page first. Preserve source assets and
reports.

1. Read the failing test's metrics and captures: `<context>_surface_coverage`,
   `<context>_surface_uncovered_pixels`, `<context>_surface_contexts_present`, the appearance
   frame and the probe frames. A skipped `openpbr_renders` or `mdl_renders` is
   N/A only when `assessment_applicability.status` is `not_applicable` with
   `reason_code=no_resolved_surface_for_context`. This proves the complete resolved
   material inventory lacks that context's surface. A skip without this marker is
   no verdict: inspect its reason and resolve unavailable sources or test inventory
   before drawing an asset conclusion.
2. Run the narrowest validation gate that covers `VM.MAT.001`
   (`FET009_MaterialCoverage.0-1-0`) on the source asset. It names the renderable Gprims
   and `GeomSubset`s that resolve no material at the `full` purpose.
3. Where a renderable Gprim has `materialBind` `GeomSubset` children, `VM.MAT.001` checks only
   the subsets. Find each such Gprim that resolves no material itself and whose subsets leave
   faces out: those faces render with whatever the enclosing scene binds, and only the coverage
   test reports them. If neither this step nor the gate names a prim, stop and report the
   metrics and frames: the static check and the measurement disagree, and a binding edit would
   be a guess.
4. Copy the asset and its dependencies into the requested output directory.
5. Bind each named prim to one of the asset's existing materials through `material:binding`
   or `material:binding:full`. For a Gprim from step 3, bind the Gprim itself, or make the
   `materialBind` subsets a partition of its faces. Choose the material from the appearance
   frame, neighbouring geometry or the author's stated intent, and ask when none of them
   identifies it. Do not author new materials, collection-based bindings or a binding strength.
6. Save the staged layers and rerun the `VM.MAT.001` gate. When runtime evidence is
   requested, run the three render tests FET009 lists (`preview_surface_renders`,
   `openpbr_renders`, `mdl_renders`) through `simready-evaluate` in Kit or Isaac Sim
   with `--features FET009_MaterialCoverage.0-1-0`, and preserve the metrics and captures.
   Report runtime unavailability honestly: the static gate alone does not establish coverage.

A missing UsdPreviewSurface, OpenPBR or MDL surface is a `FET006_Materials` repair; use the
matching `simready-foundation-conform-fet-006-*` skill.
