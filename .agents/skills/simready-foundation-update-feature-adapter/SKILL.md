---
name: simready-foundation-update-feature-adapter
description: "Use for updating SimReady adapters, exact dotted endpoint metadata, USD mutations, and tests."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, adapter, maintenance]
---

# SimReady Update Feature Adapter

## Purpose

Repair or extend an adapter whose USD mutation or endpoint metadata no longer
matches its exact source and target contracts.

## Prerequisites

Read `AGENTS.md`, the adapter guide, adapter implementation/tests, exact source
and target feature manifests, and affected profile versions.

## Workflow

1. Compare adapter endpoints with complete
   `<name>[.<runtime>].<version>` manifest IDs. Reject wildcard endpoints.
2. Reproduce or inspect the failed upgrade.
3. Resolve affected profile selectors before comparing source and target plans.
4. Add a new exact adapter path when a new published feature ID changes the
   contract; preserve existing published paths.
5. Patch mutation logic narrowly, preserving unrelated data and the input stage.
6. Keep the target's `adapters`, additional requirements, and runtime
   tests synchronized with the implementation.
7. Test source validation, mutation, target validation, runtime behavior, and
   repeatability where practical.
8. Update profile migration notes and confirm every resolved feature difference
   has a direct path or documented blocker.

## Policies

- Protect unrelated local work: before editing shared repository files (spec markdown, requirement/feature JSON, profile TOML, validators, skills, or docs), check `git status` for unrelated in-progress changes and scope edits to the requested task. Never revert, overwrite, discard, stash, or commit a user's uncommitted or unrelated changes; if a file you must edit already carries pending unrelated edits, surface it and confirm before proceeding.
- Keep secrets out of the repo and evidence: never write user-provided tokens, credentials, API keys, or other secrets into files, source, logs, validation or evaluation reports, commit messages, or bug/Jira/Confluence attachments, and do not echo them in full; read them from environment variables or an existing credential store and redact them from any output you preserve.
- Do not silently retarget an adapter to a different dotted ID.
- Do not broaden mutations beyond the exact endpoint contract.
- Keep legacy Foundations 1 adapters available while published profiles depend
  on them.
- If mutation requires user intent, report a blocked path rather than guessing.

## Summary

Report the adapter path, exact endpoint IDs, change type, USD mutation, tests,
profile impact, and remaining gaps.
