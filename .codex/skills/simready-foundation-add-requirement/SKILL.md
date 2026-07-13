---
name: simready-foundation-add-requirement
description: "Use for adding atomic SimReady requirements with stable IDs, docs, examples, indexes, and validator follow-up."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - requirement
    - specification
---


# SimReady Add Requirement

## Purpose
Use this skill to add one new atomic, testable requirement to an existing SimReady capability. A requirement is the smallest stable contract that features can include and validators can report.

If no existing capability fits, use `simready-foundation-add-capability` first. If the requirement changes behavior for an existing rule, use `simready-foundation-update-requirement`.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/features_expansion_workflow.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- target capability `capability-*.md`, `requirements.md`, existing `requirements/*.md`, and `validation.py`

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `capability_path` | Existing capability folder under `nv_core/sr_specs/docs/capabilities/`. |
| `requirement_slug` | Kebab-case filename without `.md`. |
| `requirement_code` | Stable code such as `RB.011` or `NVM.006`; must not already exist. |
| `summary` | One-sentence rule statement. |
| `description` | Precise asset condition being checked. |
| `compatibility` | OpenUSD, PhysX, Isaac Sim, MDL, or other relevant compatibility tier. |
| `tags` | Essential, correctness, portability, performance, or another existing tag. |
| `examples` | Valid and invalid USDA or structured examples. |
| `validator_plan` | Existing validator, new validator needed, manual-only, or runtime-only. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the target capability exists and the requirement code is unused across `nv_core/sr_specs/docs`.
2. Create `requirements/<requirement_slug>.md` using the repository's requirement metadata table style: `Code`, `Validator`, `Compatibility`, and `Tags`.
3. Include `Summary`, `Description`, `Why`, `Examples`, `How to comply`, and relevant USD or runtime references.
4. Add valid and invalid examples that show the smallest meaningful pass/fail distinction.
5. Add the requirement filename to the capability `requirements.md` toctree or requirements table.
6. If the capability overview lists requirements directly, update `capability-<slug>.md` too.
7. If an objective rule can be implemented now, hand off to `simready-foundation-add-validator`.
8. If an existing or new feature should include this requirement, hand off to `simready-foundation-add-feature` or `simready-foundation-update-feature`.
9. Validate consistency:
   - requirement code is unique
   - requirement file is reachable from the capability index
   - examples align with the described rule
   - validator status is stated honestly

## Examples

Example request:

```text
Add a new atomic requirement for factory connection point direction metadata.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Requirements must be atomic. Split compound rules into separate requirement IDs.
- Do not create a requirement just to mirror a feature name; define the concrete asset rule.
- Prefer native USD concepts before custom metadata.
- Any new custom USD property or attribute named by the requirement must follow `naming_conventions.md` namespace rules.
- Use warnings or manual review for subjective guidance; reserve failures for objective contract violations.
- Do not list a requirement in a feature until its intended validation status is clear.

## Limitations

- Do not mutate published feature or profile versions in place.
- Do not invent requirement IDs or validator behavior when the contract is ambiguous; record the question.
- Do not skip index, manifest, validation, or downstream follow-up notes.

## Troubleshooting

- Error: the new concept overlaps an existing artifact. Solution: update the existing capability, requirement, feature, profile, or adapter instead.
- Error: names or IDs conflict. Solution: re-check naming conventions and nearby indexes before editing further.
- Error: validation strategy is unclear. Solution: document deferred validation and the exact follow-up skill.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `requirement_code` | New requirement ID. |
| `requirement_doc` | Markdown path. |
| `capability` | Capability folder updated. |
| `index_updates` | Requirement index/overview files updated. |
| `validator_plan` | New validator, existing validator, manual review, or runtime test. |
| `feature_followup` | Feature(s) that should include the requirement. |
| `validation` | Checks run and remaining gaps. |
