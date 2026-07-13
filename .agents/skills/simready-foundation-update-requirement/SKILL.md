---
name: simready-foundation-update-requirement
description: "Use for updating SimReady requirement docs, semantics, validator alignment, and profile impact notes."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - requirement
    - maintenance
---


# SimReady Update Requirement

## Purpose
Use this skill to revise an existing requirement. Requirement IDs are stable, so separate editorial clarification from contract changes before editing.

For behavior changes that affect validation or feature conformance, update dependent validators and create new feature/profile versions as needed.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/features_expansion_workflow.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- target requirement markdown
- capability `requirements.md`, `capability-*.md`, and `validation.py`
- feature JSON manifests that include the requirement code
- profile versions consuming those features

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `requirement_code` | Existing stable requirement ID. |
| `requirement_doc` | Markdown path to update. |
| `change_type` | Editorial, example clarification, compatibility/tag update, validator alignment, or contract change. |
| `reason` | What is wrong, incomplete, or stale. |
| `validator_change` | Whether `validation.py` must change. |
| `feature_impact` | Feature manifests that include this requirement. |

## Instructions

Use this checklist when changing the repository:

1. Locate the requirement code in docs, validators, feature JSON, and profile context.
2. Classify the change:
   - Editorial: spelling, broken links, clearer examples, non-contract wording.
   - Contract-impacting: changed pass/fail behavior, compatibility, required authored data, severity, or validator logic.
3. Preserve the requirement code unless the user explicitly requests deprecation and replacement.
4. Update the requirement markdown with clearer summary, description, examples, and compliance text.
5. Keep the requirement metadata table and standard sections aligned with `naming_conventions.md`: `Code`, `Validator`, `Compatibility`, `Tags`, `Summary`, `Description`, `Why`, `Examples`, and `How to comply`.
6. If validator behavior is stale or incomplete, hand off to `simready-foundation-update-validator`.
7. If the contract changed, hand off to `simready-foundation-update-feature` so dependent feature versions can be bumped. Do not silently change published feature behavior by docs alone.
8. Update capability index/overview only when title, slug, or requirement organization changes.
9. Validate consistency:
   - requirement code still matches validator registrations
   - examples match validator behavior
   - feature manifests still make sense
   - any required feature/profile version follow-up is documented

## Examples

Example request:

```text
Update an existing SimReady requirement to clarify validation criteria and examples.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

## Policies

- Do not repurpose a requirement code for a different concept.
- Do not make a validator stricter or looser without updating docs and feature-version impact.
- If the existing requirement is wrong but published, prefer adding a replacement requirement and new feature version over mutating semantics in place.
- Keep examples executable-looking and minimal.

## Limitations

- Do not silently change published contracts; add versions when behavior changes.
- Do not update docs without checking validator, manifest, profile, adapter, and runtime-test impact.
- Do not broaden a change beyond the selected requirement, capability, feature, profile, validator, or adapter.

## Troubleshooting

- Error: the requested change alters a published contract. Solution: create a new version and preserve the old artifact.
- Error: docs and machine-readable manifests diverge. Solution: make the JSON/TOML and markdown agree, then rerun focused checks.
- Error: downstream profile or adapter impact is unclear. Solution: list the affected artifacts before making broad edits.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `requirement_code` | Requirement changed. |
| `change_type` | Editorial or contract-impacting. |
| `docs_changed` | Requirement/capability docs changed. |
| `validator_followup` | Validator update needed or completed. |
| `feature_followup` | Feature version updates needed. |
| `profile_followup` | Profile version updates needed. |
| `validation` | Checks run and remaining gaps. |
