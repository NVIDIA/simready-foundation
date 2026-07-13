---
name: simready-foundation-add-validator
description: "Use for adding executable SimReady validators that report requirement IDs with focused pass/fail coverage."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - validator
    - validation
---


# SimReady Add Validator

## Purpose
Use this skill to implement objective validation for one or more requirement IDs. Validators should report failures against the exact requirement code documented in the capability.

If the rule already exists but is wrong or incomplete, use `simready-foundation-update-validator`.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/features/features.md`
- `nv_core/sr_specs/docs/guides/features_expansion_workflow.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- target requirement markdown
- target capability `validation.py`
- nearby checker classes in the same capability
- feature manifests that include the requirement

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `requirement_codes` | Requirement IDs this validator enforces. |
| `validation_module` | Target capability `validation.py`. |
| `rule_name` | Clear checker class/function name. |
| `asset_scope` | Stage, prim, property, relationship, material, physics, or runtime evidence. |
| `failure_message` | Actionable message that names the failed condition. |
| `test_assets` | Existing or minimal pass/fail assets, if available. |

## Instructions

Use this checklist when changing the repository:

1. Confirm requirement docs exist and the intended check is objective.
2. Inspect existing validators in the capability and reuse local helper patterns.
3. Add a checker class or function in `validation.py` with the correct registration decorators/imports used by the capability.
4. Register every requirement ID the checker enforces and pass the matching requirement when reporting each failure.
5. Keep failure messages specific, deterministic, and actionable.
6. Handle missing default prims, invalid paths, unloaded/abstract prims, variants, and composed stages consistently with neighboring validators.
7. Add focused pass/fail tests or sample validation instructions where the repo has a test pattern.
8. Update requirement docs only if implementation clarifies edge cases.
9. Validate consistency:
   - validator imports successfully where possible
   - requirement IDs match documented codes
   - failure messages match docs
   - feature manifests include only registered requirements when executable validation is expected

## Examples

Example request:

```text
Add a validator for a SimReady factory connection point requirement.
```

Expected result summary:

```text
changed_files: new docs, manifests, indexes, or validation scaffolding
validation: focused static checks and any relevant docs/build checks
remaining_gaps: requirement, validator, adapter, profile, or runtime-test follow-up
```

## Policies

- Do not validate subjective guidance as a hard failure unless the requirement defines objective criteria.
- Prefer one clear checker per rule family over tangled mega-checkers.
- Avoid changing unrelated validators while adding a new one.
- Use warnings only when the validation framework supports them and the requirement is advisory.
- If local Omniverse/OAV packages are unavailable, document the narrowed validation you could run.

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
| `requirement_codes` | Requirements validated. |
| `validation_module` | File changed. |
| `checker` | Class/function added. |
| `docs_aligned` | Requirement docs checked or updated. |
| `tests` | Tests/assets run or planned. |
| `feature_impact` | Features that now have executable coverage. |
| `validation` | Import/test result and remaining gaps. |
