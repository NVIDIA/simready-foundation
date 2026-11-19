---
name: simready-foundation-validate-foundation-change
description: "Audit Foundations 2 CAP-prefixed capabilities, runtime-tested dotted features, wildcard/optional profiles, multi-profile behavior, adapters, tests, docs, and skills."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags: [simready, validation, audit]
---

# SimReady Validate Foundation Change

## Purpose

Audit consistency after requirement, capability, feature, profile, adapter,
runtime-test, tier, or skill changes.

## Checks

1. Requirements/capabilities: unique requirement IDs, docs/index alignment,
   validators registered, and every capability catalog ID begins with `CAP`.
2. Features: two-segment neutral or three-segment runtime ID; identity only in `id`; exact
   dependencies exist; requirements exist; graphs/docs agree; published IDs
   preserved. A dotted ID's version segment is the published semantic version
   with dots replaced by hyphens (`0.4.0` becomes `0-4-0`), never a bare
   integer. Published Foundations 1 manifests keep dotted semantic versions in
   their filenames and `version` fields; do not reintroduce the reverted
   bare-integer version experiment.
3. Feature/runtime boundary: runtime FETs have non-empty tests, additional
   requirements, and adapters; testless source FETs have tested derivatives;
   every other static-only contract is a CAP capability.
4. Profiles: TOML parses; feature and capability selectors resolve against the
   complete installed catalog; required selectors match; wildcard breadth is
   intentional; optionality is machine-readable for FETs and capabilities;
   old versions are unchanged.
5. Resolution: sort/dedup is deterministic and required wins over optional on
   overlap.
6. Multi-profile behavior: the same asset can be planned/validated against
   several profiles independently; evidence retains each profile/version and
   resolved bundle; no exclusive asset profile stamp is required.
7. Adapters: exact dotted endpoints exist; no wildcard endpoint; each required
   runtime-tested difference has a direct path or blocker.
8. Runtime tests: feature mapping uses exact dotted IDs and evidence is not
   hand-edited. Tier-owned tests live under
   `nv_core/tiers/<tier>/<test-package>/`, where `<test-package>` is the
   importable package named by that tier descriptor's `runtime_tests_path`, and
   ship in the tier wheel; the retired `nv_core/runtime_tests` and
   `nv_core/testing_tools` trees are not recreated. Independent test-only wheels
   register under `simready.evaluate.tests`, and unpublished development packs
   stay discoverable through `--tests-path`. Do not add the removed
   `requirement` decorator keyword.
9. Skills/docs: add/update/conform guidance uses the same contract.
10. Compatibility: published Foundations 1 manifests/profiles/adapters are not
    silently rewritten; aliases are clearly non-authoritative.

Run JSON/TOML parsing, `test_foundations_contracts.py`, targeted validator
tests, docs checks, and runtime validation when the required tools exist.
Unavailable runtime evidence is a gap, not a pass.

## Summary

Report surfaces/files checked, commands, findings by severity, wildcard
resolution changes, blocked checks, recommended targeted repair, and overall
status.
