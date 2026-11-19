---
name: simready-foundation-conform-fet-000-newton
description: "Use for repairing exact CAP000_Core.Newton SimReady conformance: the Newton physics runtime variant scaffolding (Newton variant set, runnables/physics/newton payload, and SimReady variant metadata). Use when a profile, validation report, or user request names CAP000_Core.Newton; default to `CAP000_Core.Newton.0-1-0`. Foundations 1 ID: FET_000_NEWTON."
license: Apache-2.0
metadata:
  author: "Shaad Boochoon <sboochoon@nvidia.com>"
  tags:
    - simready
    - conformance
    - newton
    - core
---

# SimReady Conform CAP000_Core.Newton

## Scope

Repair the exact selected `CAP000_Core.Newton` capability, defaulting to
`CAP000_Core.Newton.0-1-0` only when the user/profile/report does not pin a
version. It adds Newton runtime-variant scaffolding to the neutral
`CAP000_Core.0-1-0` dependency. It does not authorize collider,
material, mass, actuator, joint or scene tuning.

Work on the requested staged output unless in-place repair is explicit.
A profile listing optional PhysX/MuJoCo capabilities does not authorize adding
or repairing them. Preserve their data and report blocking sibling/base
isolation defects for a separately scoped repair. Do not migrate runtime
physics or clear neutral properties automatically to make this gate pass.

## Source of Truth

Read the selected manifest and capability page in the Newton tier:

- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP000_Core.Newton.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_newton/simready/foundation/tier_newton/capabilities/CAP000_Core.Newton.md`

The dependency and validators remain Core-owned:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP000_Core.0-1-0.json`
- Under `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/requirements/`:
  `newton-variant-set.md` (RV.004), `newton-runtime-payload.md` (RV.005),
  `newton-variant-metadata.md` (RV.006),
  `runtime-variant-section-purity.md` (RV.010), and
  `runtime-physics-isolation.md` (RV.011).
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/core/runtime_variants/runtime-physics-isolation-matrix.md`

These paths are checkout-relative. In installed workflows resolve the owning
tier's catalog/requirements through its descriptor. The published site merges
tiers into logical documentation roots; a cross-tier link need not exist
relative to the raw Newton package. Resolve its actual owner instead of
inventing a local catalog or skipping the rule.

## Workflow

1. Confirm the actual input, requested staging destination and exact selected
   capability/profile versions. Read the source-of-truth requirements before
   editing; samples do not establish conformance.
2. Check the neutral Core dependency. If a required repair exceeds the requested
   scope, preserve the evidence and report the blocker instead of changing
   unrelated physics.
3. On the actual stage default prim, expose a `Newton` variant set with
   `Disabled` and `Enabled`, authoring `Disabled` as its default (RV.004).
   Keep `Disabled` empty. Keep `Enabled` limited to its single `prepend payload`
   arc, with no inline properties, children or other arcs (RV.010).
4. Anchor the payload to `./runnables/physics/newton.usd` or `.usda` inside
   the asset root, matching the actual default prim (RV.005). Preserve existing
   intended Newton payload contents. If creating a scaffold without supplied
   body data, do not invent collision schemas, geometry or physical values;
   that scaffold is not proof of Newton rigid-body/runtime readiness.
5. Merge only the Newton descriptor under root-layer
   `customLayerData.SimReady_Metadata.Variants.Physics.Newton` (RV.006):
   `prim` is the actual default-prim path, `variantSetName = "Newton"`,
   `activateOption = "Enabled"`. Preserve sibling metadata.
6. Check composed isolation through the real validator (RV.011), including
   neutral and already-declared runtime selections. Foreign-runtime data and
   `physics:approximation = "sdf"` under Newton are failures; a neutral
   approximation token is a nonfatal leak, not permission to clear source
   properties. Shared RV.010/RV.011 checks can remain blocked by an untouched
   sibling defect even when the requested Newton edits are correct.
7. Report exact edits, official verification and the first remaining blocker.
   Hand body/collider/material work to the matching
   `FET003_RigidBody.Newton`/`FET004_Multibody.Newton` scope, and actuation to
   `FET022_DrivenJoints.Newton`, only with the required asset-repair authority.

The payload/default-prim names above follow the contract; substitute the
asset's actual prim hierarchy. Do not copy another asset's topology or tuning.

## Official Verification

Use the actual `simready-validate` CLI/API, not a reimplemented or direct-checker
harness. Inspect the approved interpreter/executable, installed help, Validate
version/origin and both tier identities first. Core supplies the RV validators
and neutral dependency; Newton supplies this capability manifest. In a
built-wheel check, resolve both through installed descriptors without source
path overlays, and retain wheel/source/installed provenance.

If provisioning or a local build is separately authorized, the repository's
`repo.bat build_tiers` / `./repo.sh build_tiers` publishes workspace wheels to
`nv_core/tiers/_build/dist/`, not a per-tier output directory. Use its reported
exact artifacts. Follow the matching Validate/Evaluate installation guidance;
this conformance skill does not authorize creating environments, installing
packages or changing framework code.

For an existing suitable environment, use the requested registered profile and
version and a fresh JSON output. Replace all placeholders before execution:

```text
simready-validate --profile PROFILE_ID --version PROFILE_VERSION --output NEW_REPORT_JSON STAGED_ASSET
```

Inspect the exact capability/version and its dependency results, not just the
profile exit code: Newton may be optional in that profile. Missing results,
checker ERRORs and empty coverage are not PASS. Retain command, exit status,
fresh evidence, asset revision and catalog/checker provenance; keep other
failures visible. Omit stamping unless requested. If official validation cannot
execute, label any inspection as inspection-only and report the missing
environment/target evidence.

This capability declares no runtime test. Any separately requested
physics acceptance must use the real discovered Evaluate procedures for the
matching feature/runtime; scaffold validation or a look-alike test cannot
substitute for that coverage.

## Report Fields

Record `feature` (exact capability ID), `input`, `output`,
`requirements_repaired`, `requirements_blocked`, `validation` (actual
command/evidence or explicit inspection-only limitation), `status`, and
`next_step`. No available asset or unexecuted gate is a certified PASS.
