---
name: simready-foundation-conform-fet-033-standard
description: "Use for repairing exact FET_033_STANDARD Metadata conformance (thumbnail and nested provenance metadata). Use when a profile, validation report, or user request names FET_033_STANDARD; default to version `0.3.0` unless a profile or report pins another version."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - standard
---

# SimReady Conform FET_033_STANDARD

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET_033_STANDARD`. It repairs or stages Metadata conformance (thumbnail and nested provenance metadata) without drifting into another runtime contract.

Default to `FET_033_STANDARD@0.3.0` when the user asks for this feature without a version. Use an older version only when the profile, validation report, or user explicitly pins it. If the report names a different `FET_###_RUNTIME` feature, switch to that feature's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_033_STANDARD-0.3.0.json` (latest)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_033_STANDARD-0.2.0.json` (preserved)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_033_STANDARD-0.1.0.json` (preserved)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET_033_STANDARD.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/sim_ready/requirements/thumbnail-exist.md` (`SR.002`)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/core/sim_ready/requirements/nested-simready-metadata.md` (`SR.003`)

Treat the selected JSON manifest as authoritative for dependencies and requirement IDs. Use the feature markdown for human-readable contract details, requirement links, samples, benchmarks, and adapters.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `0.1.0` | FET_031_STANDARD@0.1.0 | `SR.002` |
| `0.2.0` | FET_031_STANDARD@0.1.0 | `SR.002`, `SR.003` |
| `0.3.0` | FET_031_STANDARD@0.1.0 | `SR.002`, `SR.003` (stricter provenance fields) |

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET_033_STANDARD` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Create or use a staged output location unless the user explicitly asks for in-place edits.
5. Repair only the requirements listed by the selected `FET_033_STANDARD` manifest and its dependencies.
6. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
7. Summarize the selected `FET_033_STANDARD` version, changed files, validation evidence, and the first remaining blocker or next exact feature gate.

## Feature Guidance

- Repair only the requirements listed by the selected `FET_033_STANDARD` manifest and its dependencies.
- For `SR.002`, ensure a representative PNG thumbnail exists at `.thumbs/256x256/<asset_filename>.png` next to the root asset.
- For `SR.003` (version `0.2.0+`), author required non-empty string provenance fields inside root-layer `customLayerData.SimReady_Metadata`: `author`, `asset_name`, `asset_type`, `asset_license`, `category`, `source_file`, and `usd_date_generated`.
- For `SR.003` at version `0.3.0+`, also author these required asset-descriptive fields inside the same `customLayerData.SimReady_Metadata` dictionary:
  - `qcode` (string): Wikidata Q-Code for the asset's general category, a capital `Q` followed by one or more digits (for example `Q42177`).
  - `rigid_body_count` (int): non-negative count of rigid bodies in the asset.
  - `asset_extents` (float3): asset bounding-box size in meters as XYZ, with non-negative components.
  - `mass` (float): asset mass in kilograms, strictly positive.
- Do not author `SR.003` `0.3.0+` descriptive fields with placeholder or fabricated physical values. Derive `rigid_body_count`, `asset_extents`, and `mass` from the actual asset (rigid-body prims, computed bounds, and authored mass); if a value cannot be derived, report it as a blocker instead of guessing.

## How to Generate Metadata

The `SR.003` requirement is declarative (it checks the end state), so use the
bundled helper to populate the nested `SimReady_Metadata` dictionary. The helper
only derives what the stage can prove and never fabricates values.

Helper script: `assets/scripts/extract_simready_metadata.py` (run with a USD-core
Python; the same interpreter used to run SimReady validation works).

- Derived deterministically from the stage:
  - `asset_extents` (float3, meters) from the default prim's world bounding box,
    converted with the stage `metersPerUnit`.
  - `rigid_body_count` (int) by counting prims with `UsdPhysicsRigidBodyAPI`.
  - `mass` (kg) by summing authored `physics:mass` on prims with
    `UsdPhysicsMassAPI`; reported as `null` (needs input) when none is authored.
  - `qcode` (Wikidata Q-Code) from the default (root) prim's authored Wikidata
    semantics. Both encodings are read: the newer `UsdSemantics`
    `semantics:labels:<taxonomy>` token array (taxonomy name containing `qcode`)
    and the legacy multi-apply `semantic:<instance>:params:semanticData` with a
    `wikidata_qcode` type. Reported under `needs_input` when the root prim has no
    Q-Code semantic. Pass `--set qcode=<Qxxxx>` to override or supply one.
- Not derivable here (must be supplied, never invented): `author`,
  `asset_name`, `asset_type`, `asset_license`, `category`, `source_file`,
  `usd_date_generated`. Pass them with repeated `--set KEY=VALUE`.

Typical usage:

```bash
# 1) Inspect what can be derived (no writes):
python assets/scripts/extract_simready_metadata.py <asset.usd> --dry-run

# 2) Stamp derived fields (incl. qcode from root-prim semantics) plus
#    caller-supplied strings into a staged copy:
python assets/scripts/extract_simready_metadata.py <asset.usd> \
    --output <staged/asset.usd> \
    --set author=<author> --set asset_name=<name> \
    --set asset_type=<type> --set asset_license=<license> \
    --set category=<category> --set source_file=<source> \
    --set usd_date_generated=<date>
    # add --set qcode=<Qxxxx> only to override the derived value or when the
    # asset carries no Wikidata Q-Code semantic.
```

The helper keeps existing metadata values unless `--overwrite` is passed, writes
a JSON/markdown report with `--report`/`--markdown-report`, and lists every field
still needing input under `needs_input`. Treat a `null` `mass` or a missing
`asset_extents` as a blocker to resolve (author `UsdPhysicsMassAPI` / fix
geometry, or supply the value) rather than stamping a fabricated number.

## Mass Plausibility Check (advisory)

Beyond presence/type validation, the helper reports whether the authored `mass`
is physically plausible for the object. This is advisory only: it emits warnings
and a verdict, never a hard failure, because plausible mass depends on what the
asset represents in the real world.

Every run includes a `mass_check` block with per-body and aggregate solid volume
(computed from mesh geometry), and the implied density `mass / volume`. Two
signals:

- **Deterministic (automatic):** an implied density outside the physically
  possible range (`1`–`23000` kg/m^3, i.e. lighter than any real solid or denser
  than osmium) is flagged as a likely mass or unit error (for example mass
  authored in grams, or a cm^3/m^3 mix-up). This needs no external knowledge.
- **Agentic (recommended for the real-world judgement):** decide a plausible mass
  range for the object from its type and dimensions — and, when available, a
  render or the source mesh — then pass it back so the report records the
  comparison and rationale:

```bash
python assets/scripts/extract_simready_metadata.py <asset.usd> --dry-run \
    --expected-mass-min <kg> --expected-mass-max <kg> \
    --mass-rationale "office chair, mostly plastic + steel base, ~5-10 kg"
```

The `verdict` is `plausible` (inside the range), `review` (outside but within
~100x), or `implausible` (>=100x off, almost certainly an authoring/unit error).
Because this is a real-world judgement, a vision-capable agent should set the
expected range from visual/mesh evidence; if the agent cannot make that
judgement, report it as manual review rather than asserting the mass is correct.
Do not change the authored `mass` to satisfy this check — surface a warning and
let a human or the asset author correct the source value.
- Do not add schemas, metadata, or runtime behavior for a sibling runtime feature.
- Report missing runtime/tooling evidence as a validation limitation instead of claiming a pass.

## Report Fields

| Field | Meaning |
|---|---|
| `feature` | Exact feature ID and version, for example `FET_033_STANDARD@0.3.0`. |
| `input` | Source asset, package root, or package definition inspected. |
| `output` | Staged output path, or `in-place` only when explicitly requested. |
| `requirements_repaired` | Requirement IDs repaired in this pass. |
| `validation` | Command or inspection used to verify this exact feature. |
| `status` | `passed`, `failed`, `skipped`, or `blocked`. |
| `next_step` | The next exact feature skill or user/runtime evidence needed. |
