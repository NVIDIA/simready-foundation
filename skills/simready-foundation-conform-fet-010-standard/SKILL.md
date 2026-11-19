---
name: simready-foundation-conform-fet-010-standard
description: "Use for repairing exact FET010_DisplayColor SimReady conformance for display colour (`primvars:displayColor`) on renderable geometry. Use when a profile, validation report, or user request names FET010_DisplayColor, DISP.001 or DISP.002; default to `FET010_DisplayColor.0-1-0` unless a profile or report pins another version. Foundations 1 ID: FET_010_STANDARD."
license: Apache-2.0
metadata:
  author: "Jens Jebens <jjebens@nvidia.com>"
  tags:
    - simready
    - conformance
    - display-color
---

# SimReady Conform FET010_DisplayColor

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

Use this exact feature skill when the selected profile, validation report, or user request
names `FET010_DisplayColor`. It authors or repairs `primvars:displayColor` on renderable
geometry without touching the shaded surfaces, which are the sibling contracts
`FET006_Materials` (UsdPreviewSurface), `FET006_Materials.MDL` and `FET006_Materials.Openpbr`.

Default to `FET010_DisplayColor.0-1-0` when the user asks for this feature without a
version. Use another version only when the profile, validation report, or user explicitly
pins it. If the report names a different contract, switch to that contract's matching skill before editing.

Display colour is the appearance layer available to a consumer that does not evaluate
materials, so it is repaired independently of them and can be repaired on an asset that has
no material at all. What it cannot do is invent one: the colour is derived from a bound
material, and geometry with nothing to derive from is reported rather than given a guess.

## Source of Truth

Before changing an asset or package, read:

- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET010_DisplayColor.0-1-0.json`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features/FET010_DisplayColor.md`
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/visualization/display_color/requirements/display-color-coverage.md` (DISP.001)
- `nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/visualization/display_color/requirements/display-color-values.md` (DISP.002)

Treat the JSON manifest as authoritative for requirement IDs. Use the feature markdown for
contract details, requirement links, samples and runtime tests. The Display Color capability
and its feature manifest land with the capability change; if they are not on the branch you
are working from, read them from the branch that introduces them before editing an asset.

## Feature Versions

| Version | Dependencies | Requirements |
|---|---|---|
| `FET010_DisplayColor.0-1-0` | None | `DISP.001`, `DISP.002`, `DISP.003` |

`DISP.003` covers `primvars:displayOpacity`, which is optional and which this skill does not
author. An asset that carries no display opacity satisfies it.

## Bundled script

`assets/scripts/author_display_color.py` authors a constant `primvars:displayColor` on every
renderable Gprim, derived from the material bound to that Gprim.

```bash
# report DISP.001, DISP.002 and DISP.003 conformance, change nothing
python author_display_color.py <path> --verify

# show what would change
python author_display_color.py <path> --dry-run

# author, sampling base colour maps
python author_display_color.py <path>

# author from material constants only, never opening a texture
python author_display_color.py <path> --no-textures

# author into each Gprim's material:binding layer, which reaches instanced geometry
python author_display_color.py <path> --edit-target binding
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--verify` | off | Report `DISP.001`, `DISP.002` and `DISP.003`. Writes nothing. |
| `--dry-run` | off | Report what a run would author. Writes nothing. |
| `--textures` | **on** | Sample base colour maps over the bound faces. Naming it changes nothing; it is the default. |
| `--no-textures` | off | Derive from material constants only, never opening a texture. |
| `--edit-target stage` | **default** | Author on the composed stage. Geometry inside an instance is out of reach. |
| `--edit-target binding` | off | Author into the layer holding each Gprim's `material:binding`, which is where instanced geometry can be written at all. |

`--edit-target binding` is what a referenced or instanced asset needs. On the Audi A6
vehicle sample the default reaches 5 renderable Gprims and leaves 16 inside 9 prototypes
untouched; `binding` reaches all of them, authoring 15 opinions that 17 Gprims resolve,
because instances share one.

`<path>` is a USD file or a directory, which is searched for `simready_usd` assets. The
script needs USD Python (`pip install usd-core`). Sampling additionally needs `numpy` and
`Pillow`; without them the script says so and falls back to `--no-textures` behaviour, which
on this library authors almost nothing. See **What `--no-textures` actually gives you** below.

`--verify` and `--dry-run` are rejected together. `--verify` already changes nothing, so
`--dry-run` alongside it would guard a run that was never going to write; the script says
which flag to drop rather than accepting the pair and ignoring one.

It is safe to re-run. Every value is re-derived from scratch on each pass and the derivation
is deterministic, so a second run over an unchanged asset leaves the same colour on the same
prim. Sampling uses a fixed stratified point set rather than a random one for exactly this
reason: a random sequence would move every value slightly on every pass and rewrite all
fourteen sample assets each time. Re-running still rewrites the binary layer, so compare
flattened USD rather than file hashes when checking that a re-run changed nothing.

Exit codes, so a script driving this can tell a crash from a finding:

| Code | Meaning |
|---|---|
| `0` | clean |
| `1` | `--verify` found DISP.001, DISP.002 or DISP.003 problems |
| `2` | bad arguments, or no USD assets under the given paths |
| `3` | at least one asset could not be read or raised |

An asset that raises is reported as `ERROR` with its traceback on stderr, and the walk
carries on to the rest.

### What `--verify` checks

Whether a renderable Gprim resolves a display colour at all; whether the resolved value
carries the `color3f[]` that `UsdGeomGprim` declares, including the two ways a scalar gets
past a type check (authored on an enclosing `Xform`, or authored on the Gprim itself, where
the schema's own type name hides it); component range and finiteness; element count against
the declared interpolation and the prim's topology; and, on an indexed primvar, the index
count against topology and every index against the value array. Where a primvar carries only
time samples, the earliest authored sample is what gets checked, which is what DISP.002 says.

`primvars:displayOpacity` is checked on the same terms, so DISP.003 is reported even though
this skill never authors it. A preflight that says `ok` on an asset the capability validator
fails is worse than no preflight.

All of it is transcribed from the capability validator at
`nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/visualization/display_color/validation.py`,
which a standalone run cannot import: it needs `simready.foundation.tier_core.requirements`
and `usd_validation_nvidia`, and their absence is why this preflight exists. Each function in the script names the validator
method it mirrors. Change one, change the other.

### Derivation reference

How the primvar's layer is chosen (including instancing), where and with what
interpolation it is authored, what the colour is derived from, how a texture is
reduced to one area-weighted colour, what `--no-textures` yields, colour-space
handling, the clamp/refuse value rules, and the conflict cases the script leaves
alone are documented in `references/display-color-derivation.md`.

## Feature Adapter

The same derivation is declared as a feature adapter, so the move onto display colour has a
known code path that runs without a person driving it. See
`nv_core/sr_specs/docs/guides/feature_adapters/feature_adapters.md`.

| Adapter module | Adapter | Transition | Authors |
|---|---|---|---|
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_neutral_to_display_color` | `FET006_Materials.0-1-0` -> `FET010_DisplayColor.0-1-0` | Constant `primvars:displayColor` per renderable Gprim, derived from the UsdPreviewSurface `diffuseColor`. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_openpbr_to_display_color` | `FET006_Materials.Openpbr.0-1-0` -> `FET010_DisplayColor.0-1-0` | Constant `primvars:displayColor` per renderable Gprim, derived from the OpenPBR `base_color`. |
| `nv_core/cip_specs/asset_handler_modules/neutral_to_display_color` | `material_mdl_to_display_color` | `FET006_Materials.MDL.0-1-0` -> `FET010_DisplayColor.0-1-0` | Constant `primvars:displayColor` per renderable Gprim, derived from the OmniPBR or OmniGlass MDL base colour. |

- The adapter holds no derivation of its own. It calls `author_stage()` in the bundled script
  above, which is the single implementation of this derivation, so running the skill by hand and
  running the adapter produce the same value. Change the script, not the adapter, to change what
  is authored.
- All three transitions are the conformance case where an asset had no display colour and now
  has one. None is a version migration: `FET010_DisplayColor` has only `FET010_DisplayColor.0-1-0`. When a later
  version exists, add another decorated function pinning the two versions rather than editing
  these, which is what `neutral_to_physx` does for its `FET004_Multibody.0-2-0` -> `FET004_Multibody.RobotPhysX.0-3-0` path.
- Three input features are declared rather than one because the derivation resolves whichever
  surface a material carries, in the order OpenPBR, UsdPreviewSurface, MDL. On an asset that
  carries several the result is the same either way; declaring them separately keeps the adapter
  graph explicit about which contracts have a known path here.
- The adapter cannot conform geometry with no bound material, because the colour is derived
  rather than invented. Those Gprims are logged as skipped and left without a display colour, so
  the stage can still fail `DISP.001` after the adapter runs.
- Texture sampling needs `numpy` and `Pillow`, and the adapter's environment should have them.
  Without them the adapter does not fail, but on a texture-driven material it has only the
  constant the material authors beside its texture, and on these samples there is none — so it
  authors nothing, saves nothing, and `DISP.001` still fails afterwards. See **What
  `--no-textures` actually gives you** above.
### Running it

Two paths, and they author the same value because they call the same function.

**Without Kit**, call the derivation on an open stage. This needs `pxr`, plus `numpy` and
`Pillow` for texture sampling:

```python
from pxr import Usd
from author_display_color import author_stage

stage = Usd.Stage.Open("sm_asset.usd")
authored, skipped, conflicts, per_material, notes = author_stage(stage, sample_textures=True)
stage.Save()

print(authored, "Gprims authored,", skipped, "skipped,", conflicts, "conflicts")
for material, entry in per_material.items():
    count, weight, accumulated = entry
    colour = [c / weight for c in accumulated] if weight else [0.0, 0.0, 0.0]
    print(" ", material, colour, "across", count, "Gprim(s)")
```

`author_stage` opens nothing and saves nothing, so the caller controls both. Pass
`dry_run=True` for the same counts without authoring, and `sample_textures=False` for the
`--no-textures` derivation, which on this library authors almost nothing. The command line
above wraps this with file handling and is the easier route for a directory of assets.

`per_material` maps a material name to `[gprim_count, accumulated_weight, accumulated_colour]`,
where `accumulated_colour` is each contributing colour multiplied by that contribution's
world-space area and summed. Divide it by `accumulated_weight` to get the area-weighted colour,
as above. Read the third element directly and it is off by the material's total area, which can
land it anywhere — well below the real colour on a small asset, above `1.0` and outside the
legal `displayColor` range on one covering more than a square stage unit. The accumulator is
returned unnormalised on purpose, so a caller running a directory of assets can sum the entries
across all of them and divide once at the end, which is what the command line does.

**Inside the registry**, the adapter is resolved by feature rather than called by name. That
path lives in the `omni.cip.configurable` extension in the **simready-explorer** repository:
`loader.py` scans the adapter modules named by `adapter_modules_path` in
`nv_core/sr_specs/docs/config.json`, the `@feature_adapter` decorator registers each function,
and `pipeline.py` drives an asset from an input profile to an output profile, selecting
adapters with `FeatureAdapter.get_adapters_for_features()`. Use this when moving a whole asset
between profiles rather than applying one known derivation.

It needs a Kit environment. `omni.cip.configurable.feature_adapter` imports
`omni.asset_validator.core`, which is not on the Python package index, so the adapter module
cannot be imported outside Kit at all — which is why the standalone entry point above exists.

Note also that `workspace upgrade`, which the physics conform skills name as the way to run an
adapter, has no implementation in this repository (`AGENTS.md`).

## Workflow

1. Confirm the input exists and identify the exact selected feature/version from the profile
   TOML, validation report, or user request.
2. Load the selected `FET010_DisplayColor` manifest and the feature markdown before editing.
3. Load requirement docs linked from the feature markdown for every reported failing
   requirement.
4. Run the bundled script with `--verify` to establish the starting state. See **What
   `--verify` checks** above for what it covers and what its exit codes mean.
5. Create or use a staged output location unless the user explicitly asks for in-place edits.
6. Repair only the requirements listed by the selected manifest and its dependencies.
7. Rerun the same profile gate or the narrowest available feature/capability validation gate.
   If runtime evidence is required and unavailable, report that limitation instead of claiming
   a pass.
8. Summarize the selected version, changed files, validation evidence, and the first remaining
   blocker.

## Limits

- The script authors `primvars:displayColor` and nothing else. `primvars:displayOpacity`
  (DISP.003) is optional and is left alone, so an asset that carried none still carries none.
- Only meshes can be sampled. A Gprim with a material but no mesh topology, such as a Sphere
  or a Capsule, falls back to the material's constant and is reported as doing so.
- 16-bit and higher integer maps are read at 8 bits per channel, which is below the precision
  a mean over hundreds of thousands of texels would justify. Every map in the sample library
  is an 8-bit PNG.
- UV handling covers the forms these assets use: `st` at any interpolation, `UsdTransform2d`,
  MaterialX `uvtiling`/`uvoffset`, MDL `texture_scale`/`texture_translate`/`texture_rotate`,
  and `repeat`/`clamp` wrapping. Every one of them is identity on the current samples, so
  none of that is exercised by them. A material using a UV setup outside this set would
  sample the wrong region of its map.
- `--verify` reads authored scene description. It establishes DISP.001, DISP.002 and DISP.003,
  which are statically checkable. It says nothing about how the asset renders; that is the
  FET006 display colour evaluation's job and it needs Kit or Isaac Sim.
- `--verify` is a transcription of the capability validator, not that validator running. It
  can drift, and one difference is already deliberate: it walks `Usd.Stage.Traverse()` while
  the validator is handed prims by the asset validator engine, so the two can disagree about
  instance prototypes and unloaded payloads. Run the real validation gate before claiming a
  pass.
- The derivation approximates albedo. It does not claim to match what a path tracer produces
  for the same object, and DISP.002 sets no plausibility band against which such a claim could
  be checked.
