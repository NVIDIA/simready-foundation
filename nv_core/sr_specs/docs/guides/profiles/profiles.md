# Profiles Documentation Guide

## Foundations 2 model

A profile is a named, versioned selection contract over runtime-tested
features and static capabilities. Capability IDs and selectors begin with
`CAP`. A profile does not own an asset and an asset does not declare one
exclusive profile. Producers and consumers may validate the same asset against
any number of profiles.

Profiles may contain:

- feature selectors over dotted feature IDs;
- capability selectors over capability IDs;
- required and optional selectors in both groups; and
- wildcard selectors over feature name/runtime/version or capability name.

Each profile remains in its own TOML file under the owning tier's `profiles/`
directory. Existing profile versions are immutable.

## Profile TOML

Each selector entry names its selector and, optionally, `optional = true`:

```toml
[Robotics-Prop]
"4.0.0" = {features = [
    {selector = "FET001.*.*"},
    {selector = "FET004.*.*", optional = true},
    {selector = "FET004.PhysX.*", optional = true},
], capabilities = [
    {selector = "CAP000_Core.*.*"},
    {selector = "CAP007_NonVisualMaterials.*.*", optional = true},
]}
```

Feature identity already includes its version, so Foundations 2 entries do not
contain a separate `version` field.

## Selector behavior

The example above uses explicit runtime and version segments for compatibility
with `simready-validate` 2026.10.0rc1. The Foundation reference resolver also
accepts the shorthand described below. For commands and custom profiles used
with that validator release, follow the compatibility forms in the next section.

Feature selectors have one to three dotted segments. A bare name or family
selects every runtime and version. Two-segment selectors match either a runtime
or a neutral version; three-segment selectors select runtime and version
explicitly. For example, `FET004.0-*` selects neutral versions beginning `0-`,
`FET004.PhysX` selects every PhysX version, and `FET004.*` selects both.
Version tokens remain opaque, including leading zeroes.

| Selector | Expansion |
|---|---|
| `FET004.*` | All runtimes and versions in FET family 004. |
| `FET004.PhysX.*` | All PhysX versions in FET family 004. |
| `FET004_Multibody.PhysX.2-0-4` | One exact feature. |
| `CAP024.*` | All runtimes and versions in CAP family 024. |
| `CAP024_BaseArticulation.PhysX.*` | All PhysX versions of that capability. |
| `CAP007_NonVisualMaterials.0-2-0` | One exact capability. |

Capability selectors work exactly like feature selectors, with a `CAP` prefix
instead of `FET`: one to three dotted segments, the same runtime-or-neutral-version
shorthand, and shell-style `*` usable within a segment. A capability ID is
`<name>[.<runtime>].<version>` like a feature ID, and a runtime-neutral
capability omits the runtime segment.

Resolution rules are deterministic:

1. Expand against the complete catalog from all installed tiers.
2. Sort matches by exact ID.
3. Deduplicate matches.
4. If required and optional selectors select the same item, it is required.
5. A required selector matching nothing is an error.
6. An optional selector matching nothing is allowed.
7. Capabilities referenced by resolved features are included automatically and
   inherit feature optionality; required wins over any optional path.

Wildcard profiles intentionally follow the installed catalog. Adding a new
matching feature can therefore change their resolved bundle without editing
the profile. Use an exact ID when reproducibility is more important than
automatic adoption, and record the resolved bundle in validation evidence.

(validate-rc1-selectors)=

## Validate 2026.10.0rc1 compatibility

`simready-validate` 2026.10.0rc1 requires a version or wildcard segment in each
selector. Its two-segment form is `<name>.<version>`; the special
`<name>.*` form selects all runtimes and versions. Use three segments when
selecting a specific runtime. Use these forms when authoring a custom profile
for that release:

| Intended selection | Compatible selector |
|---|---|
| All runtimes and versions of the Core capability | `CAP000_Core.*.*` |
| Neutral Core versions beginning with `0` | `CAP000_Core.0*` |
| All PhysX versions of the multibody feature | `FET004.PhysX.*` |
| All runtimes and versions of feature family 004 | `FET004.*.*` |
| All versions and runtimes of non-visual materials | `CAP007_NonVisualMaterials.*.*` |
| One neutral Core version | `CAP000_Core.0-2-0` |

Bare names such as `FET004`, name-only patterns such as
`CAP007_NonVisualMaterials*`, and runtime shorthand such as
`CAP000_Core.OpenUSD` are accepted by the Foundation reference resolver but
rejected or interpreted differently by Validate rc1. A rejected required
selector can cause the profile to be skipped and validation to produce no
result. Inspect profile registration messages before interpreting that outcome
as an asset failure.

Choose the runtime scope explicitly when converting shorthand. For example,
`CAP000_Core.0*` selects neutral versions, while `CAP000_Core.*.*` also selects
Isaac, MuJoCo, Newton, and PhysX contracts present in the catalog. Prefer exact
IDs when preserving a fixed set of contracts. Verify the resolved IDs with the
installed validator; Foundation-only resolution does not prove rc1 acceptance.

## Optional features and capabilities

`optional = true` makes failures contributed only by that selector non-blocking.
Validation engines still execute and report those checks as optional evidence.
When a requirement is also selected through any required feature or capability,
required wins and its failure is blocking.

Optionality belongs to the profile selector, not to the feature or capability
definition.

## Validating against multiple profiles

Profile selection is caller-supplied. Do not stamp a singular `profile` and
`profile_version` into asset metadata as the validation authority.

At the Python layer, resolve all requested targets and run the validator once
per profile so evidence stays independent:

```python
from simready.foundation.contracts import ProfileTarget
from simready.foundation.validation import validate_profiles

results = validate_profiles(
    asset_path,
    targets=[
        ProfileTarget("Robotics-Prop", "5.0.0"),
        ProfileTarget("Robot-Body", "4.0.0"),
    ],
    profiles=profiles,
    features=features,
    capabilities=capabilities,
    validate_one=validate_one,
)
```

The helper builds a `ValidationPlan` for every target and accepts an injected
`validate_one` callback. This lets standalone validation, Kit, and other
runtimes share identical resolution and optionality behavior.

Conformance evidence may record several profile results for the same asset.
Each result must retain its own profile name, profile version, resolved feature
IDs, resolved capability IDs, and pass/fail outcome.

`Robotics-Prop@5.0.0` and `Robot-Body@4.0.0` can be requested together.
Newton checks are optional for the prop target and required for the robot
target, so the same asset can pass one target and fail the other.

### Chain stamping

The external validator's multi-profile API validates each target independently
and retains profile-keyed results in USD metadata and the JSON report. Initialize
the validator with the selected tiers, then pass a staged output path when
writing metadata:

```python
from simready.validate import ProfileTarget, validate_asset_against_profiles

results = validate_asset_against_profiles(
    asset_path,
    targets=[
        ProfileTarget("Robotics-Prop", "5.0.0"),
        ProfileTarget("Robot-Body", "4.0.0"),
    ],
    write_metadata=True,
    report_file_path="validation.json",
)
```

Each receipt and report preserves `Robotics-Prop@5.0.0` and `Robot-Body@4.0.0`
as separate entries under `profiles`, including when a target fails validation.
The Foundation orchestration helper above resolves targets and calls the
validator; the external validation library owns receipt persistence.

This API requires a validator release with multi-profile receipt support. Older
single-profile validators, including `simready-validate` 2026.8.0, replace the
profile identity and same-day stamp when another profile is stamped. Preserve
one report per `(asset, profile, version)` with those releases.

## Creating or updating a profile

1. Define the asset class and intended consumer/runtime.
2. Choose exact or wildcard feature selectors.
3. Add capability selectors for requirement-only contracts.
4. Mark conditional feature and capability selectors optional in TOML.
5. Resolve selectors against the complete installed tier catalog.
6. Inspect every match, especially broad wildcards.
7. Add a new profile version for any selector or optionality change.
8. Keep the previous version unchanged.
9. Update profile markdown and the shared profile index.
10. Document adapter paths for differences from related profiles.
11. Validate representative assets against this and other compatible profiles.

## Adapters

Feature adapters connect exact dotted runtime-tested feature IDs. Profile conversion
planning compares the resolved source and target bundles. Every required target
feature difference must have a direct adapter path or a documented blocker.

Capability-only differences may use a profile adapter when mutation is needed;
static capabilities that merely validate existing data require no adapter.

## Validation checklist

- TOML parses.
- Every required selector matches at least one catalog item.
- Every match is intentional.
- Optionality is stored in TOML for both features and capabilities.
- Capability selectors and definitions use the `CAP` prefix.
- Every runtime FET has tests/adapters, and every testless FET is the source of
  at least one tested derived FET.
- Exact selectors reference existing IDs.
- Profile docs show selectors and the resolved review bundle.
- Old profile versions are unchanged.
- Multi-profile validation preserves independent evidence.
- Adapter gaps are documented.
