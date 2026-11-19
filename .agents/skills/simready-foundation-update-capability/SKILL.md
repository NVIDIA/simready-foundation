---
name: simready-foundation-update-capability
description: "Update a CAP-prefixed Foundations 2 static contract, docs, requirement indexes, validation registration, and feature references."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - capability
    - maintenance
---


# SimReady Update Capability

## Purpose
Use this skill to maintain an existing capability folder. This includes adding requirement entries, clarifying the capability overview, reorganizing requirement docs, and keeping validators and imports aligned.

Use `simready-foundation-add-capability` when the capability folder does not exist.

## Prerequisites
Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- target `capability-*.md`
- target `requirements.md`
- target `requirements/*.md`
- target `validation.py`
- feature manifests that reference requirements in this capability

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `capability_path` | Existing capability folder. |
| `change_type` | Add requirement, reorganize docs, update scope, validator registration, or cleanup. |
| `requirement_changes` | Requirement docs being added, moved, or updated. |
| `validator_changes` | Validation module updates needed. |
| `feature_impact` | Features affected by requirement changes. |

## Instructions

Use this checklist when changing the repository:

1. Confirm the capability folder and overview/index files exist.
2. Classify the change as documentation-only, requirement-index, validator, or contract-impacting.
3. Confirm the machine-readable capability ID begins with `CAP` and keep its
   requirements and exact CAP dependencies aligned with the docs.
4. Update `capability-<slug>.md` when scope, requirement list, related docs, or validation status changes.
5. Update `requirements.md` to include every requirement doc exactly once.
6. Add or move requirement docs with `simready-foundation-add-requirement` or `simready-foundation-update-requirement` guidance.
7. Update `validation.py` and `rules_and_reqs/__init__.py` only when executable validators or imports change.
8. If requirement semantics changed, hand off to the feature and profile update workflows.
9. Validate consistency:
   - every requirement doc is indexed
   - every indexed requirement file exists
   - validator registrations reference documented requirement IDs
   - features do not reference removed or renamed requirement IDs

## Examples

Example request:

```text
Update an existing SimReady Foundation capability to clarify its requirements and validation coverage.
```

Expected result summary:

```text
changed_files: updated docs, manifests, indexes, validators, or adapters
validation: focused checks for the changed contract
remaining_gaps: downstream feature, profile, adapter, or runtime-test follow-up
```

## Policies

- Protect unrelated local work: before editing shared repository files (spec markdown, requirement/feature JSON, profile TOML, validators, skills, or docs), check `git status` for unrelated in-progress changes and scope edits to the requested task. Never revert, overwrite, discard, stash, or commit a user's uncommitted or unrelated changes; if a file you must edit already carries pending unrelated edits, surface it and confirm before proceeding.
- Keep secrets out of the repo and evidence: never write user-provided tokens, credentials, API keys, or other secrets into files, source, logs, validation or evaluation reports, commit messages, or bug/Jira/Confluence attachments, and do not echo them in full; read them from environment variables or an existing credential store and redact them from any output you preserve.
- Avoid broad reorganization unless it removes real confusion.
- Preserve existing requirement codes and links whenever possible.
- Keep capability scope broad enough for related requirements but narrow enough to be meaningful.
- Record validation gaps honestly instead of implying coverage that does not exist.

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
| `capability_path` | Capability changed. |
| `docs_changed` | Overview/index/requirement docs changed. |
| `validators_changed` | Validation files changed. |
| `requirements_added` | New requirement IDs. |
| `requirements_moved` | Moved docs or none. |
| `feature_followup` | Feature version impacts. |
| `validation` | Checks run and remaining gaps. |
