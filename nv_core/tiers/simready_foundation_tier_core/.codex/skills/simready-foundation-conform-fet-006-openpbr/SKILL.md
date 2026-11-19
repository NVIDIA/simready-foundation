---
name: simready-foundation-conform-fet-006-openpbr
description: "Use for repairing exact FET006_Materials.Openpbr SimReady conformance for OpenPBR (MaterialX) material conformance. Use when a profile, validation report, or user request names FET006_Materials.Openpbr; default to `FET006_Materials.Openpbr.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_006_OPENPBR."
license: Apache-2.0
metadata:
  author: "Jens Jebens <jjebens@nvidia.com>"
  tags:
    - simready
    - conformance
    - openpbr
---

# SimReady Conform FET006_Materials.Openpbr

## OpenUSD Competence

Running this conform skill is expert USD authoring. Reason from the OpenUSD /
Pixar USD spec rather than pattern-matching a validator message: composition
arcs and LIVRPS strength ordering, value resolution and list editing
(prepend, append, explicit, delete), the `def`/`over`/`class`
specifiers, native instancing and model hierarchy, stage units and up-axis,
and the `UsdGeom`, `UsdShade`, and `UsdPhysics` schemas. Make the exact native
edit on the correct prim, arc, and layer, derive values from the asset's real
geometry and composition, then reopen the composed stage to confirm the
opinion resolves as intended before claiming the gate passes. Never fabricate
data to satisfy a validator token. The repository-root `AGENTS.md`
"Master-Level OpenUSD Competence for Conform Work" section is the full
statement.

## Purpose

Use this exact feature skill when the selected profile, validation report, or user request names `FET006_Materials.Openpbr`. It adds or repairs the OpenPBR final surface on a material without touching the UsdPreviewSurface preview (`FET006_Materials`) or the MDL surface (`FET006_Materials.MDL`), which are sibling contracts.

Default to `FET006_Materials.Openpbr.0-1-0` when the user asks for this feature without a version. Use another version only when the profile, validation report, or user explicitly pins it. If the report names a different contract, switch to that contract's matching skill before editing.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.Openpbr.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.Openpbr.0-2-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET006_Materials.Openpbr.md`

Treat the JSON manifest as authoritative for requirement IDs. Use the feature markdown for contract details, requirement links, samples and runtime tests.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET006_Materials.Openpbr.0-1-0` | None | `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002`, `VM.MAT.001`, `VM.PBR.001`, `VM.PBR.002`, `VM.PBR.003`, `VM.TEX.001`, `VM.TEX.004` |
| `FET006_Materials.Openpbr.0-2-0` | None | `com.nvidia.usd.VM.BIND.001`, `VM.BIND.002`, `VM.PBR.001`, `VM.PBR.002`, `VM.PBR.003`, `VM.TEX.001`, `VM.TEX.004` |

## Bundled script

`assets/scripts/migrate_to_openpbr.py` authors the OpenPBR surface onto a material from
whatever it already has: a UsdPreviewSurface preview, an MDL final surface, or both. The
MDL models it reads are listed under **Which MDL models it reads**; a material built on
anything else is reported and left alone.

```bash
# report conformance, change nothing
python migrate_to_openpbr.py <path> --verify

# show what would change
python migrate_to_openpbr.py <path> --dry-run

# migrate, carrying textures across
python migrate_to_openpbr.py <path>

# migrate, flattening texture-driven channels to constants instead
python migrate_to_openpbr.py <path> --no-textures

# include materials defined outside this asset, such as a shared material library
python migrate_to_openpbr.py <path> --shared-materials migrate
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--verify` | off | Report `VM.PBR.001` / `VM.PBR.002` conformance and texture resolution. Writes nothing. |
| `--dry-run` | off | Report what a run would author. Writes nothing. |
| `--textures` | **on** | Wire MaterialX reader nodes for texture-driven inputs. Naming it changes nothing; it is the default. |
| `--no-textures` | off | Flatten texture-driven inputs to the constant beside the map instead of wiring readers. |
| `--variants selected` | **default** | Migrate only the variants the asset ships selected. |
| `--variants all` | off | Visit every variant of every variant set. What an asset whose materials are specialised per variant needs. |
| `--shared-materials skip` | **default** | A material defined outside this asset's directory is reported by the layer it lives in and left alone. |
| `--shared-materials migrate` | off | Author into that layer too. It is shared, so this changes every asset that references it. |

A material whose surface already matches what the run would author is reported as
unchanged and its layer is not rewritten, so a second pass over a library is quiet on
everything it has already done.

### Variants

A material specialised inside a variant is only on the stage while that variant is
selected. One pass sees one variant's worth, and the rest are invisible rather than
absent: the Audi A6 vehicle sample ships with `Midnight_Black` and `Metallic_Black_Rim`
chosen, and under `--variants selected` every other paint colour and rim finish migrates
as nothing at all.

`--variants all` visits each variant of each set in turn rather than each combination, so
ten paint colours and seven rim finishes are seventeen passes, not seventy. A material
shared across variants is authored on the first pass that reaches it and reported
unchanged by the rest, so the run converges: on the A6 the first pass authors 80 materials
and each variant pass after it authors the single material that variant specialises.

`<path>` is a USD file or a directory, which is searched for `simready_usd` assets.
The script needs USD Python (`pip install usd-core`).

Textures are carried across by default. `--textures` used to be the opt-in that wired them
and is still accepted, but it no longer changes anything: it names the default. `--no-textures`
is the opt-out that flattens texture-driven channels to constants, which is what a plain run
used to do. The constant is whatever the source carries beside the map, and the OpenPBR nodedef
default where the source carries none. `geometry_normal` is the exception: it has no constant
form, so a flattened run leaves it unauthored.

It is safe to re-run. The script owns one prim per material, `OpenPBR_Shader`, plus the reader
nodes named `OpenPBR_Shader_*` beside it, and rewrites all of them from scratch on each pass:
whatever the previous run authored is removed before the fresh derivation is written, so a
re-run leaves exactly what the current derivation produces and never duplicates a texture node.
That matters because these assets are binary and LFS-tracked, so they cannot be merged: when
someone else edits an asset, re-run the script rather than resolving a conflict.

Three consequences of that rewrite:

- Only the input names the script itself authors are removed, and only on `OpenPBR_Shader`,
  the `OpenPBR_Shader_*` nodes, and the interface inputs it exposes on the `Material` prim.
  An input someone added outside that set, and every other shader under the material, is left
  alone.
- On the `Material` prim the script also claims any input whose name ends `_texture_file`,
  because a packed map is exposed under the map's own name rather than a parameter name.
- The reader nodes are rebuilt each pass. A `--no-textures` run after a normal run drops the
  wiring, because the current derivation no longer produces it, and leaves each channel at
  the constant that derivation does produce.

Re-running rewrites the binary layer, so the file hash changes even when the scene description
does not. Compare flattened USD rather than file hashes when checking a re-run changed nothing.

### Mapping and model-semantics reference

The OpenPBR surface output, the materials the script refuses to touch, the full
input-mapping tables (UsdPreviewSurface, OmniPBR, OmniGlass), how it chooses the
layer to write, the per-model MDL semantics it reads, the texture-reader
topology, and the interface inputs it exposes on the `Material` prim are
documented in `references/openpbr-migration-details.md`.

## Feature Adapter

The same migration is declared as a feature adapter, so the move onto OpenPBR has a known code
path that runs without a person driving it. See
`nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_neutral_to_openpbr` | `FET006_Materials.0-1-0` -> `FET006_Materials.Openpbr.0-1-0` | OpenPBR surface on `outputs:mtlx:surface`, derived from the UsdPreviewSurface preview. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_mdl_to_openpbr` | `FET006_Materials.MDL.0-1-0` -> `FET006_Materials.Openpbr.0-1-0` | OpenPBR surface on `outputs:mtlx:surface`, derived from the OmniPBR or OmniGlass MDL surface. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_neutral_to_openpbr_0_2_0` | `FET006_Materials.0-3-0` -> `FET006_Materials.Openpbr.0-2-0` | Same as `material_neutral_to_openpbr`, for the versions that leave `VM.MAT.001` to `FET009_MaterialCoverage`. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_openpbr` | `material_mdl_to_openpbr_0_2_0` | `FET006_Materials.MDL.0-3-0` -> `FET006_Materials.Openpbr.0-2-0` | Same as `material_mdl_to_openpbr`, for the same versions. |

- The adapter holds no derivation of its own. It calls `migrate_stage()` in the bundled script
  above, which is the single implementation of this migration, so running the skill by hand and
  running the adapter author the same thing. Change the script, not the adapter, to change what
  is authored.
- Every transition is the conformance case where an asset had no OpenPBR surface and now has
  one. None is a version migration. Each pair of versions has its own decorated function, and a
  later version adds another rather than editing these, which is what `neutral_to_physx` does
  for its `FET004_Multibody.0-2-0` -> `FET004_Multibody.RobotPhysX.0-3-0` path.
- The adapter adds; it removes nothing. The preview and MDL surfaces are separate contracts an
  asset may hold at the same time, and both survive the run.
- A material carrying a hand-authored OpenPBR surface is left alone and logged as a conflict, so
  the stage can still fail `FET006_Materials.Openpbr` after the adapter runs. Resolve those by hand.
### Running it

Two paths, and they author the same thing because they call the same function.

**Without Kit**, call the migration on an open stage. This needs nothing but `pxr`:

```python
from pxr import Usd
from migrate_to_openpbr import migrate_stage

stage = Usd.Stage.Open("sm_asset.usd")
migrated, skipped, conflicts, wired, flattened, notes = migrate_stage(stage, wire_textures=True)
stage.Save()

print(f"{migrated} materials migrated, {wired} channels wired, {conflicts} conflicts")
for note in notes:
    print(note)
```

`migrate_stage` opens nothing and saves nothing, so the caller controls both. Pass
`dry_run=True` for the same counts without authoring. The command line above wraps this with
file handling and is the easier route for a directory of assets.

**Inside the registry**, the adapter is resolved by feature rather than called by name. That
path lives in the `omni.cip.configurable` extension in the **simready-explorer** repository:
`loader.py` scans the adapter modules named by `adapter_modules_path` in
`nv_core/sr_specs/docs/config.json`, the `@feature_adapter` decorator registers each function,
and `pipeline.py` drives an asset from an input profile to an output profile, selecting
adapters with `FeatureAdapter.get_adapters_for_features()`. Use this when moving a whole asset
between profiles rather than applying one known migration.

It needs a Kit environment. `omni.cip.configurable.feature_adapter` imports
`omni.asset_validator.core`, which is not on the Python package index, so the adapter module
cannot be imported outside Kit at all — which is why the standalone entry point above exists.

Note also that `workspace upgrade`, which the physics conform skills name as the way to run an
adapter, has no implementation in this repository (`AGENTS.md`).

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile TOML, validation report, or user request.
2. Load the selected `FET006_Materials.Openpbr` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing requirement.
4. Run the bundled script with `--verify` to establish the starting state. It reports the
   surface contract, the VM.PBR.002 ranges, and any texture the material names that does not
   resolve to a file on disk. All three are reported on every material, including one that has
   not been migrated yet, so a missing texture on an unmigrated asset is visible here. The
   texture check reads every asset-valued shader input, so it covers the MDL-named maps
   (`inputs:diffuse_texture`, `inputs:ORM_texture`, `inputs:normalmap_texture`) as well as the
   ones the migration authors, which is what makes it say anything about an unmigrated asset.
5. Create or use a staged output location unless the user explicitly asks for in-place edits.
6. Repair only the requirements listed by the selected manifest and its dependencies.
7. Re-run `--verify` after migrating. A texture the migration carried across is a texture the
   migrated asset now names, so the reader nodes have to resolve too.
8. Rerun the same profile gate or the narrowest available feature/capability validation gate. If runtime evidence is required and unavailable, report that limitation instead of claiming a pass.
9. Summarize the selected version, changed files, validation evidence, and the first remaining blocker.

## Limits

- The script authors the surface, its parameters, its textures and the normal map. It does not
  author coat or subsurface, which need per-asset judgement. Transmission is authored only for
  an OmniGlass source.
- Normal maps come across without the per-channel flip controls the reference library carries.
  The sample sources set `flip_tangent_u` and `flip_tangent_v` to false, so there is nothing to
  flip; a source that needs a flipped green channel would need it added.
- `--verify` checks that every texture a material names resolves to a file on disk, but not
  that the image is the right size or bit depth. VM.TEX.001's own check silently passes when
  PIL is absent, so a green result does not establish that texture sizes were checked.
- Nothing reports a source channel that did not come across. A map the script cannot map to an
  OpenPBR input is absent from the run output and from `--verify`, which only sees what was
  authored. Read the run's `texture:` lines against the source shader when that matters.
- VM.PBR.003 checks MaterialX graph structure against a resolved nodedef, so it needs a source
  of nodedefs, which `usd-core` alone is not. It does not need Kit: the validator falls back to
  the `MaterialX` Python package, so `pip install MaterialX>=1.39` is enough. `--verify` in this
  script resolves nothing either way. It reads the authored scene description, so run the
  validator for VM.PBR.003 rather than reading a green `--verify` as covering it.
