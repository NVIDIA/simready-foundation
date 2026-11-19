# Foundations 2 Layout Migration

The verified inventory, identifier-consumer table and deferred follow-ups below
describe the pre-Evaluate Foundations 1 migration checkout. Their Benchmark
names, flat suite paths and collision examples are historical evidence for that
transformation, not the current runtime package layout. Use
[Evaluate](evaluate/evaluate.md) for current commands, providers and installation.
`migrate_foundations2_catalog.py` retains its explicit Foundations 1 reader;
its `FET_` pattern is not a coverage validator for current dotted Foundations 2 IDs.

Instructions for transforming a Foundations 1 shaped repository into a
Foundations 2 shaped one, retiring the transitional `foundations2/` directory
level and making the Foundations 2 catalog the in-repo source of truth.

This page exists to tell the *next* run what to do. It is not a record of
previous runs: there are no completion markers here, and anything learned while
executing gets written back as guidance rather than as history. The
transformation is re-applied repeatedly against a moving `main`, so instructions
that drift into past tense stop being usable exactly when they are needed.

This plan supersedes the *layout* half of
[Foundations 2 Catalog Migration](foundations2-catalog-migration.md), which
describes the current dual-tree arrangement. Read that page first for what the
generated projection is; read this page for how the trees collapse into one.

## Goal and constraints

The generated projection currently sits beside the published Foundations 1
content, one level down in `foundations2/`. That arrangement was scaffolding. It
has two costs: a directory named after a migration epoch will not age well, and
the same contract is expressed twice per tier, so the two representations can
drift.

More importantly, the projection is *generated from* Foundations 1, so
Foundations 1 is still the source of truth. Nobody can author a Foundations 2
contract natively until that inverts. Collapsing the trees is what makes
Foundations 2 authorable.

Three constraints shape the work:

- **Consumer compatibility is not the same as repo layout.** `simready.validate`
  must keep reading Foundations 1 shaped tiers, because published wheels and
  third-party tiers exist in the wild. The repo does not need to keep both trees
  for that to be true.
- **`simready-explorer` must ship its Foundations 1 fallback before ship.**
  Otherwise an already-installed validator cannot read a migrated tier. Note the
  dependency runs the other way early on: the transformer has to exist first,
  because developing and testing that fallback means flipping a real repo
  between the two layouts.
- **The transformer stays a repeatable generator until ship.** `main` adds
  Foundations 1 content continuously, so the transformation is re-run, not
  applied once. It becomes one-shot only at ship.
- **This migration rearranges existing content; it does not author new content.**
  Gaps it happens to expose — a missing conform skill, a thin requirement page,
  an absent profile guide — get recorded and handled separately. Renaming and
  relocating what exists is already a large enough change to review on its own,
  and mixing authoring into it makes the diff unreadable.

## Target layout

Per tier, under each tier's package root in `simready/foundation/<package>/`:

```text
rules_and_reqs/     # requirement SOURCE tree: domain docs, requirement
                    # markdown, validators (renamed from capabilities/)
features/           # FET contracts: runtime-tested. JSON + sibling markdown
capabilities/       # CAP contracts: static, no runtime tests. JSON + markdown
profiles/           # profile TOML + profile markdown
```

`foundations2/` ceases to exist.

Package directory names are not uniform — `tier_core` and `tier_template` carry
a `tier_` prefix while the sensors tier is plain `sensors` — so never discover
tiers by directory name. The transformer keys on the `_tier.py` descriptor
instead, and any script or instruction added here must do the same. A
name-based glob silently skips a whole tier.

### Why `capabilities/` has to be renamed

"Capability" currently means three different things:

1. the `rules_and_reqs/` source tree (domain docs, requirement markdown and
   validators, grouped by domain: `core`, `hierarchy`, `physics_bodies`,
   `packaging`, …);
2. a Foundations 2 `CAP` contract, meaning a feature without runtime tests;
3. `usd_validation_nvidia.CapabilityRegistry`, the registry unit that *both* FET
   and CAP contracts register into.

Senses 1 and 2 are not the same concept under two names. `CAP000_Core.0-1-0`
lists `NP.002`–`NP.008`, `SR.001` and `HI.010` — requirements drawn from several
different domains of the source tree. A CAP contract is a cross-domain bundle; a
source-tree folder is one domain. So CAP JSON cannot simply move into the
existing `capabilities/` tree.

`rules_and_reqs/` is chosen because the runtime contract already uses that
vocabulary: the tier descriptor field is `rules_and_requirements_path` and the
entry point is `rules_package`. Nothing except the directory name calls that tree
"capabilities". `requirements/` is unavailable — that name is taken by the
generated requirement-enum package.

### Naming rules

A contract's markdown sits next to its JSON and shares the name minus the
version segment, which is how `features/` already works:

```text
features/FET004_Multibody.PhysX.md            # one page, all versions
features/FET004_Multibody.PhysX.0-1-0.json
features/FET004_Multibody.PhysX.0-2-0.json
features/FET004_Multibody.PhysX.0-3-0.json
features/FET004_Multibody.PhysX.0-4-0.json

capabilities/CAP000_Core.md
capabilities/CAP000_Core.0-1-0.json
```

Contract markdown is renamed because its *identifier* changes, not to satisfy a
filename style rule. There is no strict case convention for markdown filenames
in this repo: source-tree directories are snake_case, while most requirement and
profile pages are kebab-case. Both stay as they are.

Profile markdown therefore carries over **unchanged**, and because `profiles/`
keeps its name those pages do not even move. Profiles are also **not** required
to pair 1:1 with a TOML — some TOMLs deliberately hold several profiles each, so
a profile page may document one profile out of an aggregate file.

## The transformer

`nv_core/tiers/_tooling/migrate_foundations2_catalog.py` is the instrument. It
has two operations: generation, which is the default, and relocation, behind a
flag that is **off by default** so no routine `repo` task can destroy the
Foundations 1 tree.

### What it reads and writes

This decoupling is what makes the ordering in
[Order and revertability](#order-and-revertability) possible, so it is worth
stating precisely. Generation reads only:

- every Benchmark suite any tier ships, to classify which contracts are
  runtime-tested. A tier's suites are the top-level packages its
  `pyproject.toml` wheel target lists besides `simready`. Runtime tests are not
  confined to the core tier — the Newton and sensors tiers ship their own — and
  a contract whose tests sit in an unscanned suite projects as a `CAP`;
- each tier's `_tier.py`, used purely as a discovery marker;
- each tier's `features/*.json` and `profiles/*.toml`, the Foundations 1
  manifests.

It writes only into `foundations2/`. **It never reads or writes the requirement
source tree**, under either name, and the contracts it emits embed no
source-tree paths. Generation before the rename and generation after it produce
byte-identical output.

Consequently the whole transformation has exactly one ordering constraint: the
rename must precede relocation, because relocation refuses to run while a
`capabilities/` directory exists and pre-rename that directory is the source
tree.

### What relocation does

1. carries the feature markdown pages to their computed destinations, splitting
   FET pages from CAP pages and renaming both to the new stems;
2. leaves the profile markdown pages in place, unchanged;
3. replaces `features/*.json` and `profiles/*.toml` with the generated contracts;
4. writes CAP contracts into `capabilities/`;
5. moves `catalog-map.json` up to the tier package root, so provenance outlives
   the staging directory it was generated into;
6. repoints links between contract pages, which break because both the filename
   and the containing directory can change;
7. repoints references *into* the contract directories from files that do not
   move — profile pages, guides, benchmark suite docs, and the conform skills.
   This is the same rewrite as point 6 driven by the same catalog mapping, but
   it is easy to forget because most of those files sit outside the contract
   directories — guides and profile pages elsewhere in the docs tree, and the
   conform skills under each tier package's `skills/`, beside `features/` but
   not in it. Expect roughly 260 references across some 76 files, about half of
   them in the skills. The top-level `skills/` entries for conform skills are
   symlinks into the tier packages; the walk does not follow directory
   symlinks, so each skill is rewritten once, at its tier location;
8. regenerates the shared `features/` and `capabilities/` hub pages;
9. leaves `rules_and_reqs/` untouched;
10. refuses to run if any markdown page would be dropped or overwritten.

Point 10 matters: a silent drop here loses documentation with no error, which is
the same failure class as the generator's earlier missing-suite behaviour.

Points 6 and 7 share one subtlety worth stating plainly: a link's *directory*
component changes, not just its filename, whenever the target contract became a
capability. `features/FET_000_STANDARD.md` becomes
`capabilities/CAP000_Core.md`. A rewrite that only swaps stems produces
links that resolve to nothing.

Point 7 covers two reference shapes, and a rewrite built for one will silently
miss the other. Guides, profile pages and Benchmark docs use relative links
(`../features/…`, `../../../features/…`), while the conform skills cite full
repository paths. Matching only the trailing `features/<legacy id>.md` and
leaving whatever precedes it untouched handles both, and stays correct at any
depth because `features/` and `capabilities/` are siblings — a file that does
not move is equidistant from either.

Versioned manifest references (`features/FET_003_PHYSX-0.4.0.json`) are
repointed too, keyed on the legacy ID *and* version, since each published
version projects to its own contract file. Leaving them for ship was the earlier
plan, on the theory that the conform skills should change exactly once; that
theory is spent once point 7 rewrites their links, and a half-migrated skill
with live links and dead manifest paths is the state this guide warns against.

### Interface and refusal semantics

Relocation is a **second step, not part of generation**: it reads the staged
`catalog-map.json`, so it requires a prior generate run and fails without one.
Keeping the two separate is what lets them be reviewed separately.

It refuses, rather than proceeding, in four cases:

- a page documents a contract that the generator did not emit — relocating
  would silently drop it;
- two pages resolve to one destination;
- a page would overwrite an existing file;
- the tree is **already relocated**. This one is easy to overlook.
  `generate()` projects *from* the Foundations 1 manifests in `features/`, so
  once those are replaced there is nothing left to project and a second run
  would produce a hollow catalog. Re-running means reverting to the
  Foundations 1 layout first, never relocating twice. Detected by the presence
  of a `capabilities/` contract directory.

That last check is also what fires when the rename has not happened yet, since
the pre-rename source tree occupies the same path. Read the refusal as "the name
`capabilities/` is occupied", and check which of the two situations applies
before assuming a stale relocation.

Use `--relocate --dry-run` to print every move and deletion without performing
them. That is how the destructive step gets reviewed before it runs, and its
totals are a cheap sanity check against the inventory below.

The two non-destructive halves are also runnable on their own, against a tree
that has already been relocated:

| Flag | Effect | Safe to re-run? |
|---|---|---|
| `--relink` | repoint references in files that do not move | yes — a second run reports zero changes |
| `--write-hubs` | regenerate the two contract hub pages | yes — byte-identical output |
| `--relocate` | the destructive move | **no** — refuses; revert first |

Both read `catalog-map.json` from either its staged or its relocated location,
which is what makes them usable after the fact. That matters when a gap in
either one is discovered *after* the moves are committed: fixing it does not
require reverting the relocation.

### What is deterministic and what needs judgement

The structural work belongs in the script: computing destinations from
`catalog-map.json`, moving and renaming files, replacing JSON and TOML, and the
safety checks. Some of the work needs judgement and is better handled by an
agent following a skill.

| Work | Deterministic? |
|---|---|
| destinations, moves, renames, JSON/TOML replacement, refusal checks | yes — script |
| link *targets* between contract pages | yes — script |
| link *targets* into the contract directories from elsewhere | yes — script |
| link labels and prose naming Foundations 1 IDs and versions | no — per-page rewrite |
| the two hub toctrees | yes — regenerate from the catalog |
| rebinding adapters, tests and skills at ship | partly; the pre-underscore adapters are manual |

Two notes on that split, both of which are easy to get backwards.

Links *between* contract pages are fully mechanical, not a judgement call:
pages reference each other by bare filename because they used to share one
directory, and after the split both the filename and the relative prefix are
computable from the catalog. A link within one section stays bare; one across
sections gains a `../capabilities/` or `../features/` prefix. Anchors and `./`
forms must survive.

Links *into* the requirement source tree need no work at all. A page moving
from `features/` to `capabilities/` sits at the same depth, so `../rules_and_reqs/…`
still resolves, and docs-root-absolute forms are unaffected. The same is true
of the links from contract pages to profile pages, since profile pages neither
move nor get renamed.

What is left for the editorial pass is narrow but real: a rewritten link keeps
its old label, so a page will read ``[`FET_000_PHYSX`](CAP000_Core.PhysX.md)``
until prose is revised.

Keep the deterministic half re-runnable in one specific sense: runnable again
*after a revert*, not runnable twice against its own output. Anything requiring
judgement goes into the Foundations 1 source or a skill, never hand-patched into
the relocated output — see the invariant in
[Undoing steps 2 and 3](#undoing-steps-2-and-3).

## Preconditions

**Every feature family present in any tier needs a `FAMILY_NAMES` entry.** The
generator refuses to project a family it cannot name, and its error names the
family, the manifest that needs it, and the file to edit. It does not invent a
placeholder, because a placeholder would become a permanent contract ID and a
permanent filename.

So this is not a fixed checklist to tick once; it is a check that recurs
whenever `main` adds a feature family. Run the generator and let it tell you.
`FAMILY_NAMES` in `nv_core/tiers/_tooling/migrate_foundations2_catalog.py` is
the source of truth for names already chosen, and those must not be renamed
once explorer tests or published IDs reference them.

When naming a new family:

- Use the manifest's `display_name` in PascalCase as the default.
- Prefer what the family's requirements actually cover when the display name is
  broader. A family carrying only `LI.*` LiDAR requirements is `Lidar`, even if
  its display name says "RTX Sensors".
- Never embed the runtime in the family name. The runtime already occupies the
  middle dotted segment, so `RtxSensors.RTX` stutters.
- Keep families distinguishable by name and not only by number: family `101` is
  `RobotComposition` rather than reusing family `100`'s `IsaacComposition`.

A `FAMILY_NAMES` addition is durable tooling, not part of the transformation.
`main` never touches that table, so it carries no conflict surface — commit it
below the revertable pair and let it stay.

In particular, explorer's Foundations 1 fallback is **not** a precondition: the
transformer is what makes the fallback developable in the first place, because
testing the fallback means transforming the repo to Foundations 2, exercising
explorer against it, reverting, and exercising explorer against Foundations 1
again. A shipped fallback is a gate on [ship](#ship), not on starting.

## Verified inventory

Counts are from the current branch and will drift as `main` advances. Re-derive
them before executing, and treat a mismatch against the dry run as a signal to
investigate rather than a rounding difference. Derive them across *every*
discovered tier — currently AIF, core, Newton, sensors and template — not just
the tier you are looking at.

The dry run refuses until step 2 has freed `capabilities/`. To re-derive the
totals before then, call `_relocation_plan` on each package root, and
`_rewrite_outbound_contract_links` over `_outbound_markdown_files` for the
outbound count. All three only read.

### Contracts

94 contracts (45 FET, 49 CAP) from 64 distinct Foundations 1 IDs. The mapping is
clean: no legacy ID splits across FET and CAP, and no legacy ID maps to more
than one new name stem, so every markdown page has exactly one destination.

### Markdown

| Source | Count | Destination |
|---|---|---|
| `features/*.md` mapping to a FET contract | 27 | `features/`, renamed to the new stem |
| `features/*.md` mapping to a CAP contract | 37 | **`capabilities/`**, renamed to the new stem |
| `features/*.md` with no contract | 0 | — |
| `profiles/*.md` | 12 | stay in place, unchanged — not moves |

Most of today's "feature" pages describe contracts that are static capabilities
under Foundations 2. This is the single largest change in the collapse and the
least obvious from the directory names.

A current dry run reports 64 markdown moves, 108 contract moves, 94 deletions,
39 link rewrites between moved pages, and 259 outbound references repointed in
76 files.

### Files needing reference edits

Several dozen files across documentation, build and config, plus the identifier
consumers below. Notable hard couplings:

- `nv_core/tiers/_tooling/assemble_docs.py` — `SECTION_ROOTS` names exactly the
  sections the Sphinx build copies.
- `nv_core/sr_specs/docs/shared/features/features.md` — toctree names every
  Foundations 1 feature stem explicitly.
- `nv_core/sr_specs/docs/shared/profiles/profiles.md` — toctree names every
  profile stem explicitly.
- `nv_core/tiers/_tooling/build_hook.py` — runs requirement codegen over the
  source tree; follows the rename.
- Several `simready_benchmark_kit_suite/docs/fet*.md` pages link
  `../../../features/FET_00N_STANDARD.md`.

### Identifier consumers still on Foundations 1

| Surface | Count | Note |
|---|---|---|
| CIP feature adapters | 18 | all use split `input_feature_id`/`_version`; none use dotted IDs. 5 name pre-underscore endpoints (`FET001_BASE_NEUTRAL`, `FET004_BASE_NEUTRAL`, `FET004_ROBOT_PHYSX`, `FET100_BASE_ISAACSIM`) that appear in neither `catalog-map.json` nor any `legacy_identity`, so their rebinding must be done by hand |
| Runtime `@test` registrations | 50 | across the core, Newton and sensors suites; all Foundations 1 IDs with semver constraints |
| Conform skills | 45 | 39 in the core tier, 6 in the Newton tier; cite Foundations 1 IDs *and* paths into `features/` |
| Explorer adapter matching | 3 | `derive`'s direct pipeline, `omni.cip.configurable` and the `omni.simready.workspace_commands` upgrade pick adapters by comparing each adapter's `output_feature` with the target profile's feature IDs. Adapters declare split Foundations 1 IDs such as `FET_004_ROBOT_PHYSX`, while a Foundations 2 profile yields dotted IDs such as `FET004_Multibody.PhysX.0-4-0`, so nothing matches. Rebind the matching together with the CIP adapters themselves, keyed on the dotted ID, or on `legacy_identity` during the transition |
| Benchmark runtime routing | 1 | `simready_benchmark.core.runtime_routing.normalize_runtime` recognises only `physx`, `newton` and `mujoco`, and treats every other runtime as neutral. The projected robot variants carry the runtime segments `RobotPhysX`, `RobotNewton` and `RobotMuJoCo`, which Foundations 1 routed through the manifest's `runtime` field instead. Map those tokens to their physics runtime before any profile selects a robot variant; none does yet |
| `usd-profiles-nvidia` Sphinx extension | 1 | the docs build's specification parser. It reads the requirement tree from `capabilities/` and decodes everything under `features/` and `profiles/` strictly as Foundations 1 descriptors; from 1.22 a dotted contract aborts the build. A layout-aware shim in `docs/conf.py`, mirrored in `repo.toml`'s `sphinx_conf_py_extra`, bridges it until the package accepts its input directories as config values and skips files that are not its descriptors. Then raise the floor in `requirements-docs.txt` to that release and delete the shim |

Five of these fail quietly rather than loudly:

- Explorer's adapter matching finds no adapter for a Foundations 2 profile, so an
  upgrade runs no adapters and reports nothing wrong.
- Benchmark runtime routing treats a robot variant as neutral, so its tests fan
  out to every engine instead of running on the variant's physics runtime.

- `usd-profiles-nvidia` treats a missing requirement tree as empty. Without the
  shim, a build after step 2 stays green but publishes no capability JSONs under
  `config/`. Its `{requirements-table}` directive parses its own page, so the
  rendered tables do not reveal the loss.
- `test_benchmark_documentation.py` enforces `^FET_(\d{3})_` and rejects any
  Foundations 2 ID as non-canonical.
- `fet005_grasp/grasp_and_lift.py` gates on `asset_validated_features`
  containing `FET_003_PHYSX`; if the stamped set becomes dotted IDs it silently
  skips instead of failing.

## The transformation

Three steps, run in order: refresh the projection, rename the source tree,
relocate the contracts. Only the last two are reverted.

### Order and revertability

Two different kinds of work get confused with each other here, and keeping them
apart is the whole point of this section. Building or fixing the transformer,
adding a family name, developing explorer and shipping are *project* work: they
change tooling or ship software, and they have no layout state to undo. Only the
three steps below touch repo layout, and only two of those are revertable.

What decides revertability is not whether a step is independently verifiable —
it is **how much conflict surface it carries against `main`**. A step that keeps
churning files `main` also edits must revert before each merge, however
self-contained it looks in isolation.

- **Step 1, refresh the projection — additive, never reverted.** It writes only
  into `foundations2/`, a directory `main` never touches, so it carries no
  conflict surface and merges cleanly in place.
- **Step 2, rename the source tree — revertable.** It renames a tree of roughly
  430 files whose only purpose in renaming is to free the name `capabilities/`
  for CAP contracts, a payoff that arrives in step 3 and not before. Held across
  a merge it is pure cost: in one representative window `main` modified 34 files
  under `capabilities/`, added 16 and deleted 3, and every one of those would
  have become a rename/modify or rename/add interaction. Worse, the 16 additions
  land at the old path regardless, because a directory rename does not propagate
  to files the other side newly created, so the tree ends up split across both
  names.
- **Step 3, relocate the contracts — revertable.** It deletes the Foundations 1
  tree, which cannot survive a merge with a `main` that is still authoring into
  it.

Run step 1 **first**, before the rename, and commit any drift it produces on its
own. Generation does not depend on the rename — see
[What it reads and writes](#what-it-reads-and-writes) — so nothing forces it
into the middle, and putting it first leaves the two revertable commits at the
top of the history.

Keep them there. Every permanent commit — step 1 output, transformer fixes,
family names, test fixes, plan updates — belongs *below* the revertable pair,
so that undoing the transformation never discards permanent work. A permanent
change discovered after step 2 has landed is committed on its own and then
reordered beneath the pair; see
[Undoing steps 2 and 3](#undoing-steps-2-and-3).

### Working agreement

**Stage, do not commit.** Whoever executes a step — human or agent — runs
`git add` and stops there. The commits are made by the repository owner after
reviewing the staged diff. This matters more than usual here: two of the three
steps are mostly renames and deletions, where the diff *is* the review, and step
3 deliberately destroys the Foundations 1 tree in the working directory.

Where a step produces two logically separate changes, stage and hand off the
first, wait for it to be committed, then stage the second. Do not batch them
into one staged blob.

Pause for explicit confirmation before the first destructive relocation run.

**Keep this plan out of the execution commits, and keep it in future tense.**
Updates to this page belong in their own commit, never mixed into the commit
that performs a step. Record what an executor should *do*, not what a previous
run *did*. The reason is the revert loop: steps 2 and 3 revert and re-apply
repeatedly, so any note that rode in on an execution commit disappears exactly
when the next executor needs it.

### Step 1 — refresh the projection

Additive. Run the generator and commit whatever diff it produces, on its own.

A clean run with no diff is the normal case and means the staged catalog is
already current; there is nothing to commit and you proceed to step 2. A diff
means `main` added or changed Foundations 1 content since the last refresh, and
that belongs in its own commit before the revertable pair starts — not folded
into a later step, where it would be indistinguishable from relocation churn.

**Judge that with `git diff`, not `git status`.** Generation rewrites every
contract file whether or not its content changed, which updates mtimes, and in a
checkout configured to convert line endings that is enough for `git status` to
list files as modified when they are byte-identical to `HEAD`. `git diff
--quiet` exiting zero is the reliable answer; an empty `git diff --numstat` says
the same thing. Reading `git status` here invents drift that does not exist, and
the resulting "refresh" commit would be empty of real change.

If the generator refuses instead of running, it has found an unnamed feature
family; see [Preconditions](#preconditions).

**Treat a contract changing kind as a finding, not as drift.** A contract flips
between `FET` and `CAP` only when the generator's view of its runtime tests
changes, and the kind is part of a permanent identifier. Before committing a
flip, confirm the tests really appeared or disappeared, rather than moving to a
suite the generator does not scan, such as one in a newly added tier.

**Check a tier that `main` adds.** Its `_tier.py` must advertise
`capability_contracts_path`, `feature_contracts_path` and
`profile_contracts_path`, or the validate loader skips its contracts silently;
`_tooling/tests/test_tier_project_parity.py` fails when one is missing. If the
new tier ships a Benchmark suite, it must list that suite in its wheel
`packages`, which is where the generator looks.

### Step 2 — rename the source tree

Revertable. Revert it before merging `main` and re-apply it afterwards.

`capabilities/` → `rules_and_reqs/` in **every** tier. Discover them by the
`_tier.py` descriptor rather than by directory name, or the sensors tier will be
missed. Update `assemble_docs.py` section roots, `build_hook.py`, the Sphinx
index toctree entry, every `_tier.py` descriptor, and the badge includes path.
`nv_core/sr_specs/docs/config.json` needs nothing: it is an empty file, and no
longer declares the docs path roots. Nothing about Foundations 2 changes here, so this can be
validated on its own by building the docs and a tier wheel.

Doing this before any contract moves means `capabilities/` is free when step 3
needs it.

The rename also changes an importable package path in every tier, from
`simready.foundation.<package>.capabilities` to
`...<package>.rules_and_reqs`. Live-tree coupling to that path:

- `_tier.py` in each tier — the `rules_package` value;
- core tier tests that import validators absolutely: `test_ba002_registration.py`,
  `test_usdz_validation.py`, `test_undefined_prims_validation.py`,
  `test_texture_colorspace_suggestions.py` and
  `test_material_surface_presence.py`;
- the Newton tier's four validators, which import their shared helpers
  absolutely from `simready.foundation.tier_newton.capabilities._common`;
- three `conform-fet-000-{physx,newton,mujoco}` skills — a documented harness
  import.

`main` keeps adding sites, so re-derive the list rather than trusting it: search
for `foundation\.[a-z_]+\.capabilities`, then drop the
`foundations2/capabilities` hits. The other tiers' validators need no edits. They import
each other relatively (`from ..path_utils import …`) and reach their requirement
enums through each tier's `requirements` module, which this rename does not
touch.

Treat the new path as a breaking change for anything outside these two repos
that imports the old one.

Rename the docs section along with it: move the shared hub from
`docs/shared/capabilities/capabilities.md` to
`docs/shared/rules_and_reqs/rules_and_reqs.md`, retitle it "Rules and
Requirements", list `rules_and_reqs` in `SECTION_ROOTS` in `assemble_docs.py`,
and update the `index.md` toctree entry and its body link. Do this here rather
than deferring to step 3: `index.md` already describes "Capabilities" as
`CAP`-prefixed contracts, so leaving the source tree on that docs path collides
with the CAP contracts section as soon as step 3 creates it. Step 3 adds
`capabilities` back to `SECTION_ROOTS` for the contracts themselves.

#### Traps in the reference rewrite

The reference update is large — expect roughly 700 replacements across ~180
files — and a naive search for the word `capabilities` will both miss cases and
destroy others. Specifically:

- **Two docs-root-absolute forms are easy to miss** because they are neither
  relative links nor tier-qualified paths: Sphinx includes
  (`{include} /capabilities/_includes/badges/...`) and cross-links
  (`[kilograms-per-unit](/capabilities/core/units/...)`). Both appear
  throughout the requirement pages. Checking only for `../capabilities/`
  reports zero hits inside the tree and gives false confidence.
- **Never rewrite `foundations2/capabilities`.** That is the Foundations 2 CAP
  contract directory and it keeps its name. A blanket rewrite silently breaks
  `capability_contracts_path` in the `_tier.py` descriptors and the catalog
  paths in the contract tests. Guard it, for example with a negative lookbehind.
- **Exclude this guide and `foundations2-catalog-migration.md`** from any
  scripted rewrite. They name both directories on purpose, and a rewrite turns
  "from `…capabilities` to `…rules_and_reqs`" into "from X to X".
- **Exclude `_tooling/tests/test_migrate_foundations2_catalog.py`** as well. Its
  fixtures build Foundations 2 staging trees, so every `capabilities` and
  `../capabilities/` in it means the CAP contract section, not the source tree.
  The negative lookbehind on `foundations2/capabilities` will not save these:
  the section names are assembled from a loop variable and the links are written
  bare. A rewrite here goes unnoticed because the tests still pass — they assert
  against whatever the fixture wrote.
- **Leave the other meanings of the word alone:** the `capabilities` field on a
  profile or feature, `omni.generated_capabilities`, and `repo.toml`'s
  `project = "content-capabilities"`.
- **`build_hook.py` needs care.** `capabilities_root=` is the external
  `PythonGenerator` keyword argument and must keep its name; rename only the
  local variable, and check every use of that local so it does not become a
  `NameError` at build time.
- **Test fixtures encode the section name.** `test_assemble_docs.py` builds
  fixture trees named after the section and asserts on resulting docnames,
  including the shared hub filename, so it needs updating in step.
- **The spec-consistency scripts and their CI arguments fail quietly.** One of
  the scripts under `nv_core/sr_specs/tests/` that CI runs names the source tree
  in code: `validate_requirement_examples.py` (`CAPABILITIES` and
  `AIF_CAPABILITIES`). `.gitlab-ci.yml` also passes it one requirement directory
  per tier as arguments. Rewrite both; the other scripts need nothing (see the
  next bullet). Neither goes red when missed. A missing argument directory yields
  no requirement pages and the script exits zero having checked nothing, so
  confirm afterwards that `.gitlab-ci.yml` names no `capabilities/` path and
  that the script reports a non-zero block count. A missed constant is worse,
  because step 3 recreates `capabilities/` as the CAP contract directory and the
  stale path then resolves again, to the wrong content.
- **Leave `validate_sample_content.py` and `validate_feature_versions.py`
  alone.** Both resolve the requirement tree to whichever name the checkout
  has, in permanent code below the revertable pair. `validate_sample_content.py`
  has to, because it validates the MR's target branch and the branch under test
  in the same process, from the same default requirement paths, while the
  target branch is still on `capabilities/`; it also evicts both `capabilities`
  and `rules_and_reqs` modules between passes. `validate_feature_versions.py`
  does it through `_rules_dir()`. Do not "fix" their remaining `capabilities`
  strings by substitution: a script that names only `rules_and_reqs` finds no
  rules on the Foundations 1 side.

### Step 3 — relocate the contracts

Revertable, and destructive. Two handoffs, staged and committed separately,
because they review completely differently: a few hundred mechanical moves, then
a small set of subtle path edits. One combined staging is an unreviewable blob.

**Handoff A — the relocation.** Run `--relocate --dry-run` first and check the
totals against the inventory above, then run it for real.

This handoff deliberately leaves the tree non-functional: the tier descriptors
and the contract test still point at the staging directory that just
disappeared. Decide up front whether a red intermediate commit is acceptable;
if not, fold handoff B in before committing.

**Handoff B — rewiring.** Nothing here is optional; each item is something the
relocation invalidates:

1. every `_tier.py`: repoint `capability_contracts_path`,
   `feature_contracts_path` and `profile_contracts_path` from `foundations2/…`
   to the flattened directories. The legacy `features_path` and `profiles_path`
   then name the same directories; that is redundant but correct, because a
   Foundations 2 aware loader ignores the legacy pair whenever any
   `*_contracts_path` is present. Collapsing the six fields to three plus a
   dialect marker is a separate change.
2. `test_foundations_contracts.py`: its catalog roots glob for
   `tier_*/foundations2`, which now resolves to nothing — and the failure is an
   unhelpful `assert []` rather than a missing-path error. Fix both halves of
   that glob: `tier_*` misses the sensors tier, so key on the `_tier.py`
   descriptor. Pass the section directories straight through without filtering
   for existence; a tier publishing no contracts of one kind leaves an empty
   directory that git cannot track, and the loaders treat missing and empty
   alike so that loading does not depend on whether a checkout has generated
   the catalog.
3. `assemble_docs.py`: add `capabilities` back to `SECTION_ROOTS` and to the
   residual excludes, this time meaning CAP contracts. Check that
   `rules_and_reqs` is in the residual excludes too — step 2 adds it to
   `SECTION_ROOTS` and it is easy to miss the second list.
4. add the Capabilities entry to the `index.md` toctree, which resolves the
   mismatch step 2 left behind where the index described CAP contracts but
   linked the requirement hub. `profiles/profiles.md` needs no change — profile
   pages keep their names.

   The two contract hubs themselves are regenerated by the relocation rather
   than hand-written: `features/features.md` for the FET contracts and
   `capabilities/capabilities.md` for the CAP contracts, each carrying a
   Versions column because one page now covers every published version of its
   contract. Review that output instead of transcribing it, and use
   `--write-hubs` on its own if a hub needs refreshing later.

   Two traps sit behind that generation, which is why it is generated. A
   generator that emits only contract entries **silently drops the non-contract
   entries** an existing hub carried; the features hub has a `Feature dependency
   graph <feature-dependency-graph>` entry ahead of the contracts and draft
   feature cards after them, and losing either orphans those pages. Reading the
   existing toctree back and preserving every non-contract entry, split around
   the contracts, survives future additions in a way that hard-coding the known
   ones does not. Either way, diff the regenerated toctree against the previous
   one and account for every removed line.

   Second, the hub links each contract page at its tier location, written
   relative to the hub file the way every docs link is: a hub at
   `docs/shared/<section>/` links a guide as `../../guides/…` and a contract
   page through `../../../../tiers/<tier>/…`. `assemble_docs.py` repoints those
   links at the assembled layout. The toctree entries are Sphinx docnames, not
   links, so they name the logical page (`FET003_RigidBody`).
5. run the docs build. The toctrees and the new section are structurally
   checkable only by building.

#### What the CI checks rely on after relocation

Handoff B has no CI item, because the CI scripts need no edit at relocation. Four
of them read the contract directories, and each already reads both layouts, in
permanent code below the revertable pair. Three of those also compare the
relocated tree with something still on Foundations 1: the MR's target branch, or
the Foundations 1 IDs a document names. If one of these jobs goes red after
relocation, look first for a dependency below that has stopped holding, not for
a missing rewrite:

- `validate_profile_table.py` (`test-profile-table`) maps every Foundations 2
  selector, from `features` and `capabilities` alike, back to its Foundations 1
  ID through each tier's `catalog-map.json`, because the comparison table in
  `shared/profiles/profiles.md` names Foundations 1 IDs.
- `validate_sample_content.py` (`test-sample-content-validation`) passes each
  tier's `features/` and, once `rules_and_reqs/` exists, its `capabilities/` as
  feature paths, dropping whichever does not exist. A tier whose contracts all
  project to capabilities, as the sensors tier's do, has no `features/` for git
  to track, and `simready.validate` rejects a path that does not exist. It then
  translates both branches' feature summaries to Foundations 1 IDs through
  `catalog-map.json` before comparing them, folding a Foundations 1 ID's
  versions into one entry that passes only if every version passes.
- `validate_requirement_examples.py` (`test-spec-consistency`) passes the same
  contract directories, for the same reasons. The material and AIF requirements
  its examples exercise live in CAP contracts, so without `capabilities/` those
  examples report nothing.
- `validate_feature_versions.py` (`test-spec-consistency`) matches manifests by
  their dotted contract ID instead of by path. It reads
  `additional_requirements` where a contract has no `requirements`, loads
  `capabilities/` beside `features/`, and reports a released version that no
  manifest publishes any longer. `known_edits` records name the dotted
  contract ID.

The three that install `simready-validate` need a release that reads
Foundations 2 contracts, and `.gitlab-ci.yml` pins
`simready-validate>=2026.9.0.dev1` for each. Keep the specifier naming a
pre-release while the Foundations 2 support exists only as one: `uv` selects a
pre-release only when the specifier names one, so an unpinned
`--with simready-validate` resolves to the newest stable release. A validator
without Foundations 2 support fails on the first projected contract with
`Invalid version format: .`, because the contract carries no `version` field.

The Foundations 1 translation existed only to bridge a comparison with
Foundations 1. `validate_profile_table.py` and `validate_feature_versions.py`
have dropped it; `validate_sample_content.py` still folds its feature summaries
to Foundations 1 IDs through `catalog-map.json`.

#### Reading the docs build

**Assemble and build from the same operating system.** The staged output carries
an ownership marker naming its own resolved directory, so the assembler never
cleans a tree it did not create. A WSL run writes
`/mnt/d/…/_build/docs-src` into that marker; a Windows build resolves the same
directory as `D:\…\_build\docs-src`, the two strings do not match, and the build
dies on a mismatched-marker error that reads like corruption rather than a path
spelling difference. Deleting `_build/docs-src` and its manifest clears it — the
tree is generated and git-ignored. Running the assembler alone to sanity-check
section layout is useful, but do it from whichever environment will run the
build.

Warning volume alone is misleading — one broken assumption can produce
hundreds. Triage by asking *which* documents went missing:

- **Pages missing from sections this migration never touched** — a
  `rules_and_reqs/core/core` or an untouched profile page — mean tier
  **discovery** failed and a whole tier was skipped, not that the rename is
  wrong. The `updating environment: N added, … M removed` line is the tell: a
  large `removed` count with a small `added` count is a dropped tier.
  `tier_docs_module_root` needs exactly one module directory under
  `simready/foundation/`, so anything unexpected sitting beside a tier's
  modules can erase that tier's entire documentation.
- **Pages missing only from the renamed sections** point at the toctrees or the
  relocation itself.

Expect a small residue that this migration does not cause and should not chase:
`guides/multiphysics_solvers.md` links an anchor in
`guides/features/features.md` that the original Foundations 2 branch deleted
along with much of that guide, and two profile guides fence a selector fragment
as `toml`, which Pygments cannot lex and renders in relaxed mode anyway.

## Undoing steps 2 and 3

The repository owner undoes the revertable pair; an executor never does. With
every permanent commit below the pair, undoing is a reset to the last permanent
commit, which returns the branch to the additive dual-tree state that `main`
merges into. Step 1 output stays, because it sits below the line.

An executor's part is to keep that line clean: stage permanent work as its own
change so it can be reordered beneath the pair, and never mix it into a step's
staging.

Because the relocated layout is fully derived from the Foundations 1 tree plus
the script, undoing loses no authored content. That property is what makes the
loop safe, and it must be preserved: **do not hand-edit the relocated layout**.
Any authoring change goes into the Foundations 1 tree or the generator until
ship.

After undoing, check for an untracked, git-ignored `rules_and_reqs/` left on
disk, such as `__pycache__`. It looks like a present source tree while the
repository has no trace of it, which reads exactly like a merge that duplicated
the tree. If you clean, scope it to `nv_core/tiers`: a repo-wide
`git clean -xdf` also deletes `_build`, `_compiler`, `_repo`, `tools/repoman`,
`.worktrees`, and the generated `requirements/` packages an editable install
depends on.

## Milestones

### Develop and test `simready-explorer` both ways

This is why the transformer exists. Both explorer code paths get exercised
against a real repo rather than a hand-built approximation:

1. With the migrated layout in place, develop and test explorer's Foundations 2
   path.
2. Revert the rename and the relocation so the branch returns to the additive
   dual-tree state, which stays mergeable to `main`.
3. Re-run explorer against that Foundations 1 shaped repo to prove the fallback.

Alternating those is the only way to be confident the fallback is real rather
than assumed, and it is the reason a shipped fallback cannot be a precondition.

Explorer also needs its own committed Foundations 2 fixture tier, or a
pre-release tier wheel, so its CI does not resolve against a sibling Foundations
checkout whose layout flips between the migrated and reverted states. Derive
that fixture from a migrated tree, then keep it in the explorer repo. This is
the same failure mode as the hard-coded catalog path that used to sit in
`test_foundations2_registry_integration.py`, just with a moving target.

Re-run the transformation whenever explorer needs a refreshed layout. Because
the relocated layout is generated, "re-sync" means re-running the transformer,
not resolving merges.

Two parts are hand-applied and therefore have to be redone or cherry-picked each
cycle: step 2's rename, and step 3's handoff B. Everything else — the projection,
the moves, the reference rewrite and the hub pages — regenerates. Keep those two
as their own commits precisely so they can be reapplied without being
reconstructed from memory.

### Ship

Gates, all of which are consequences of the explorer work rather than inputs to
it:

- explorer's Foundations 2 support is released;
- explorer's Foundations 1 fallback is released, so an already-installed
  validator can still read a migrated tier;
- the transformer has run cleanly against current `main` content.

Then:

1. run the relocation for the last time;
2. rebind the 18 CIP adapters, 50 test registrations and 45 conform skills, and
   explorer's adapter matching along with the adapters;
3. relax `test_benchmark_documentation.py`'s ID regex;
4. map the robot runtime tokens in benchmark runtime routing;
5. retire `migrate_foundations2_catalog.py` to a historical tools location — it
   cannot regenerate anything once its Foundations 1 input is gone;
6. keep `catalog-map.json` as durable provenance.

On point 6: every generated contract already carries `legacy_identity`, so the
Foundations 1 ↔ Foundations 2 pair survives without the map. The map is still
worth keeping because it is the only place the `kind` classification and the
full mapping are stated together in one file, and because assets already stamped
with Foundations 1 IDs need that lookup.

## Open decisions

**O1 — conform skill directory names.** Skill folders are slugs derived from
Foundations 1 IDs (`simready-foundation-conform-fet-004-physx`). They can stay as
slugs, since the F2 contracts reference them as `skill:` strings, but decide
whether to rename for consistency at ship.

## Deferred follow-ups

Gaps this migration exposes but deliberately does not fix, per the scope
constraint. Each needs its own change.

- **Two apparently stale profile pages.** `robot-gripper-neutral.md` and
  `robot-gripper-isaac.md` describe profiles that no longer exist separately,
  while the consolidated `robot_gripper.toml` has no page at all. They are
  carried through the relocation unchanged; deleting or rewriting them is
  authoring, not rearranging.
- **Missing conform skills** for `FET_011_RTX`, `FET_012_STANDARD`,
  `FET_040`–`046` and `FET_101_ISAAC`. A runtime-tested contract's `adapters`
  entry names its skill regardless, so `FET012_GaussianSplat.0-1-0`
  points at a `simready-foundation-conform-fet-012-standard` that does not
  exist yet.
- **Kebab-case requirement pages.** Most markdown files under the source tree
  use hyphens where directories use underscores. Not worth the churn or the link
  cascade.
- **Stale exclude in `nv_core/sr_specs/repo.toml`,** pointing at
  `features/feature-template.md`, which now lives under `guides/`.
- **Doc paths that match neither naming scheme.** Two
  `simready_benchmark_kit_suite/articulation_phases/*.py` files and an
  `assemble_docs.py` docstring name `features/FET_022-driven_joints.md` and
  `features/FET_003-rigid_body_physics.md`. Those files do not exist under
  Foundations 1 either, so this predates the migration and no mechanical
  rewrite will catch them.
- **A conform skill citing the wrong contract entirely.**
  `simready-foundation-conform-fet-028-mujoco` lists
  `nv_core/sr_specs/docs/features/FET_022_MUJOCO-1.json` as a source of truth,
  which is broken three ways independently of this migration: that `docs/`
  directory does not exist, an FET_028 skill is naming FET_022, and version `1`
  was never published. The relocation's rewrite leaves it alone by design —
  nothing in the catalog matches it, and inventing a target would replace a
  visibly broken path with a plausible wrong one. Fixing it means deciding what
  the skill meant.
- **Two tiers ship the same Benchmark package name.** The core and sensors
  wheels both ship a top-level `simready_benchmark_kit_suite`, so installing
  both overwrites one with the other. The runtime-test references the sensors
  contracts record, `simready_benchmark_kit_suite:<test>`, also do not say
  which tier's copy they mean. The generator scans each tier's copy separately,
  so the projection is correct; the collision is a packaging problem for the
  sensors tier. Renaming that suite changes the references its contracts
  record, so regenerate afterwards.
- **No `known_edits` record accepts the deletion of a released version.**
  `validate_feature_versions.py` reports every deletion, and an intentional one
  needs a record shape of its own before it can merge.

  `FEATURES` is also hardcoded to the core tier, so the sensors, template and
  AIF tiers get no immutability checking and cannot have records written for
  them at all. That gap predates the migration and belongs to the validator's
  owner.

## A wrinkle in the conform skills

The 45 conform skills contain two kinds of reference, and the relocation
invalidates them at different times:

- markdown links into `features/`, which the outbound link rewrite in step 3
  fixes along with everything else;
- the "source of truth" **manifest paths** such as
  `features/FET_003_PHYSX-0.4.0.json`, which the relocation deletes and which
  ship rebinds.

Left alone, that means each skill spends the explorer milestone half-migrated:
correct links, dead manifest paths. That is strictly better than before and
harmless during the revert loop, since the skills are not executed by the
transformation. But if a reviewer would rather see skills change exactly once,
exclude each tier package's `skills/` from the step 3 outbound rewrite and do
the whole skill surface at ship instead. Either is defensible; decide once and be consistent,
because the alternative is a skill set that nobody can tell the state of.
