---
name: simready-foundation-update-validator
description: "Use for updating SimReady validators, failure messages, edge cases, and tests while preserving requirement semantics."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - validator
    - maintenance
---


# SimReady Update Validator

## Purpose
Use this skill when a validator exists but is stale, wrong, incomplete, too strict, too loose, or out of sync with requirement docs.

If changing validator behavior changes the contract, coordinate requirement and feature version updates instead of silently altering published validation semantics.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- target `validation.py`
- requirement docs for every registered requirement in the checker
- feature manifests and profiles that include those requirements
- existing tests or sample assets for the capability

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `checker` | Existing class/function to update. |
| `requirement_codes` | Requirement IDs affected. |
| `bug_or_gap` | False positive, false negative, crash, message issue, missing edge case, or docs drift. |
| `contract_impact` | Editorial/bug fix or changed pass/fail semantics. |
| `test_evidence` | Report, asset, stack trace, or expected behavior. |

## Instructions

Use this checklist when changing the repository:

1. Reproduce or inspect the reported validator behavior when possible.
2. Compare validator logic to requirement docs and feature manifest usage.
3. Classify the change:
   - Bug fix: implementation failed to match existing requirement.
   - Contract change: desired behavior differs from documented requirement.
4. For bug fixes, patch the validator and tests/samples.
5. For contract changes, update requirement docs and create new feature/profile versions before or alongside validator changes.
6. Keep failure messages stable unless they are unclear or wrong.
7. Preserve existing valid edge cases unless the requirement explicitly changes.
8. Validate:
   - focused pass/fail assets or tests
   - import/syntax checks where possible
   - affected feature/profile validation when tooling is available

## Examples

Example request:

```text
Update an existing SimReady validator after a requirement behavior change.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

## Policies

- Do not broaden a validator to cover undocumented requirements.
- Do not remove a failure without explaining why the requirement allows the case.
- Avoid changing registration IDs except to fix a clear mismatch with docs.
- If tooling is unavailable, report the exact environment gap and the narrower checks performed.

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
| `checker` | Validator changed. |
| `requirement_codes` | Requirements affected. |
| `contract_impact` | Bug fix or contract change. |
| `docs_changed` | Requirement docs updated or not needed. |
| `tests` | Tests/assets run. |
| `feature_profile_followup` | Versioning or profile updates needed. |
| `validation` | Remaining gaps. |
