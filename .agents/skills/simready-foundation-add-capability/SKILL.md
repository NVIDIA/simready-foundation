---
name: simready-foundation-add-capability
description: "Add SimReady capability docs, requirement indexes, validation stubs, and registrations for new requirement families."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - capability
    - specification
---


# SimReady Add Capability

## Purpose

Use this skill when a new requirement does not fit an existing capability. A capability groups related requirements and their validators under `nv_core/sr_specs/docs/capabilities/`.

After creating the capability, use `simready-foundation-add-requirement` for each requirement and `simready-foundation-add-validator` for executable checks.

## Prerequisites

Before editing, read:

- `AGENTS.md`
- `nv_core/sr_specs/docs/guides/guides.md`
- `nv_core/sr_specs/docs/guides/naming_conventions.md`
- `nv_core/sr_specs/docs/guides/features_expansion_workflow.md`
- existing neighboring capability folders
- `nv_core/sr_specs/docs/capabilities/capabilities.md`
- `nv_core/sr_specs/docs/capabilities/__init__.py`

No network access, API key, or external service is required for the authoring pass.

## Inputs

Collect or infer:

| Input | Requirement |
|---|---|
| `capability_group` | Existing top-level group such as `physics_bodies`, `visualization`, or a new group if justified. |
| `capability_slug` | Snake_case folder name. |
| `display_name` | Human-readable capability name. |
| `scope` | What requirement family belongs here. |
| `requirement_prefix` | Requirement code prefix, if new. |
| `initial_requirements` | Optional first requirement docs to add. |
| `validator_scope` | Whether validation is objective, manual, runtime, or deferred. |

## Instructions

Use this checklist when changing the repository:

1. Confirm no existing capability already covers the scope.
2. Choose names using the naming guide:
   - group folder: `snake_case`
   - folder: `snake_case`
   - overview: `capability-<folder_name>.md`
   - requirement docs: kebab-case
3. Create the capability folder in the appropriate group; if the group is new, add the group landing page too.
4. Add `capability-<slug>.md` with purpose, scope, requirement table, related capabilities, and validation notes.
5. Add `requirements.md` with `{requirements-table}` and a toctree for requirement docs.
6. Add an empty or initial `requirements/` folder content only for real requirements.
7. Add `validation.py` with imports and placeholder structure only when validators are planned; otherwise document deferred validation in the capability overview.
8. Update parent group toctrees, group landing pages, and global capability indexes, including `capabilities.md` when needed.
9. Update `capabilities/__init__.py` imports when a new validation module must be registered.
10. Validate consistency:
    - folder and overview names match
    - requirements index builds conceptually
    - validator registration path is documented
    - no duplicate requirement prefix or capability slug exists

## Examples

Example request:

```text
Add a SimReady capability for factory connection points, with requirement index registration and a validation plan.
```

Expected result summary:

```text
capability_path: nv_core/sr_specs/docs/capabilities/<group>/<capability_slug>
overview_doc: capability-<capability_slug>.md
requirements_index: requirements.md
validation_module: validation.py or deferred
next_step: add concrete requirements with simready-foundation-add-requirement
```

## Policies

- Prefer adding requirements to an existing capability when the domain already exists.
- Do not create a capability as a thin wrapper for one feature unless the requirement family is truly distinct.
- Keep capability docs about requirement families, not profile workflows.
- Make validation status explicit; incomplete validators are acceptable only when called out.

## Limitations

- Do not create new feature or profile versions from this skill; hand off to the relevant add/update feature or profile skill.
- Do not invent requirement IDs when the capability scope is still ambiguous; record the naming question instead.
- Do not add executable validators unless the objective checks and registration path are clear.

## Troubleshooting

- Error: an existing capability already owns the scope. Solution: update that capability instead of creating a parallel one.
- Error: the validator registration path is unclear. Solution: document deferred validation in the overview and list the exact follow-up.
- Error: indexes and folder names disagree. Solution: re-check the naming guide, then align folder, overview, requirements index, and imports.

## Resources

- `assets/openai.yaml` preserves optional UI metadata for clients that read skill display hints. It is not required for the authoring workflow.

## Summary Format

Report:

| Field | Meaning |
|---|---|
| `capability_path` | New capability folder. |
| `overview_doc` | Capability overview path. |
| `requirements_index` | Requirements index path. |
| `validation_module` | Validator path or deferred. |
| `initial_requirements` | Requirement IDs added, if any. |
| `indexes_changed` | Global/group index files changed. |
| `next_step` | Add requirements, validators, features, or review. |
