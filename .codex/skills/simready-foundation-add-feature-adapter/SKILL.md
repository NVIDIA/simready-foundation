---
name: simready-foundation-add-feature-adapter
description: "Use for adding SimReady feature adapters between exact dotted runtime-tested feature IDs or resolved profile contracts."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, adapter, usd]
---

# SimReady Add Feature Adapter

## Purpose

Add a deterministic USD mutation path between exact Foundations 2 feature IDs
or between two resolved profile contracts. Adapter endpoints use complete
`<name>[.<runtime>].<version>` IDs. Profile wildcards are resolved before adapter
planning and never appear in adapter metadata.

## Prerequisites

Read `AGENTS.md`, the feature-adapter guide, exact source and target manifests,
affected profile versions, and neighboring adapters.

## Inputs

- Exact source and target dotted feature IDs.
- Resolved source/target profile plans, when profile-driven.
- Required USD mutations and test assets.
- Target asset-handler module.

## Workflow

1. Parse both exact feature IDs and compare their requirements.
2. Confirm the target manifest names the adapter and declares its
   additional requirements and runtime evidence.
3. Decide whether a mutation is necessary. Document a no-op when source content
   already satisfies the target.
4. Add adapter metadata with exact dotted source and target endpoints.
5. Implement deterministic `modify_stage(input_stage, output_stage)` behavior;
   preserve unrelated opinions and never mutate the source stage in place.
6. Use native USD schemas and existing local helpers.
7. Test source validation, mutation, target static validation, and target
   runtime tests. Check safe repeatability where practical.
8. Register/import the adapter and update feature and profile migration
   documentation.
9. For profile upgrades, require a direct path or documented blocker for every
   resolved feature difference.

## Policies

- Protect unrelated local work: before editing shared repository files (spec markdown, requirement/feature JSON, profile TOML, validators, skills, or docs), check `git status` for unrelated in-progress changes and scope edits to the requested task. Never revert, overwrite, discard, stash, or commit a user's uncommitted or unrelated changes; if a file you must edit already carries pending unrelated edits, surface it and confirm before proceeding.
- Keep secrets out of the repo and evidence: never write user-provided tokens, credentials, API keys, or other secrets into files, source, logs, validation or evaluation reports, commit messages, or bug/Jira/Confluence attachments, and do not echo them in full; read them from environment variables or an existing credential store and redact them from any output you preserve.
- Never put wildcards in adapter endpoints.
- Do not hide an invalid source asset or invent values requiring user intent.
- Preserve adapters for published dotted IDs; new contracts get new paths.
- Keep Foundations 1 adapters registered until their published consumers have
  migrated.

## Summary

Report the adapter path, exact source and target IDs, mutation, profile path,
tests/assets run, and remaining blockers.
