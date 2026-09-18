# Semantic Labels Workflow

End to end guide for applying and validating Semantic Labels.

You will learn what the label spec asks for, assign labels either from
Python or from inside Blender, check the result with `simready-validate`, and
then confirm with `simready-benchmark` that those labels reach the
renderer. It is the reference pipeline for
[Semantic Labels](../../capabilities/semantic_labels/capability-semantic_labels.md).

All commands run from the **repository root** unless stated otherwise.

## What you end up with

| Stage | Tool | Outcome |
|---|---|---|
| Learn | this guide | You know how many labels the asset needs and where they go. |
| Baseline | `simready-validate` | The unlabeled asset fails `SL.001`, and the report names the prims it looked at. |
| Conform | Python or Blender | `SemanticsLabelsAPI` applied, with real values. |
| Validate | `simready-validate` | The semantic-labels feature drops off the failing list. |
| Verify | `simready-benchmark` | The segmentation render shows the object while labels are present, and nothing once they are stripped. |

Validation tells you the labels are well-formed. Only the benchmark tells you
the renderer honors them: a single label on the root prim should produce
segmentation coverage across the whole asset, and that coverage should vanish
when you remove the label.

## Prerequisites

| Requirement | Minimum | Needed for |
|---|---|---|
| Python | 3.12 | All paths |
| Git LFS | Installed and initialised (`git lfs install`) | Sample assets |
| `simready-validate` | see [SimReady Validation Workflow](../validate_workflow.md) | Validation |
| `simready-benchmark[kit]` | see [Running Tests](../benchmark/running.md) | Runtime verification |
| [SimReady Blender add-on](https://github.com/NVIDIA/simready-blender-add-on) | Blender 5.2, Windows 10/11 | Blender path only |
| NVIDIA Isaac Sim | 6.0 or later | Runtime verification |

```{note}
Isaac Sim 6.0 reads `SemanticsLabelsAPI` natively. Earlier versions do not
resolve this schema in the segmentation pass.
```

## 1. The label contract

### One label is the minimum

Labels are inherited. A single `SemanticsLabelsAPI` label on a common ancestor,
usually the asset's `defaultPrim`, satisfies the requirement for every mesh
beneath it. One label per asset is the floor.

Start by labeling the asset as a whole: `toaster`, `forklift`, `pedestrian`.
Labels on the parts inside it, such as `handle`, `lever` or `heating element`,
are optional, and give a perception model more to tell apart. Any renderable
geometry sitting outside a labeled subtree will need its own label.

The requirement is evaluated over the `defaultPrim` and everything beneath it.
Prims outside that subtree are not checked.

### The taxonomy is the instance name

`SemanticsLabelsAPI` is a *multiple-apply* schema. A multiple-apply schema can
be applied several times over, and each application is given a name to tell it
apart from the others.
That name is called the **instance name**, and you can see it in two places: it
follows a colon in `apiSchemas`, and it becomes the last part of the attribute
name.

Here the instance name is `class`:

```usd
def Xform "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["car"]
}
```

For semantic labels, the instance name is how you say which taxonomy a label
belongs to. Any name is valid, because the capability is taxonomy-agnostic, and
because each one is a separate application several taxonomies can sit on the
same prim without conflicting:

```usd
def Xform "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class", "SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:class = ["car"]
    token[] semantics:labels:wikidata_qcode = ["Q1420"]   # Q1420 = motor car
}
```

NVIDIA's Omniverse asset libraries use the Wikidata Q-code taxonomy, under the
instance name `wikidata_qcode`, so assets meant to ship alongside them should
use it too.

```{important}
The instance name and the value are two different things. Writing the taxonomy
name into the value is the most common authoring error. See
[Common mistakes](#common-mistakes).
```

### What gets checked

| Code | Requirement | Applies when |
|---|---|---|
| [`SL.001`](../../capabilities/semantic_labels/requirements/semantic-label-capability.md) | Every renderable prim resolves a label, whether from itself, an ancestor, its bound material, or `GeomSubset` membership. | Always |
| [`SL.002`](../../capabilities/semantic_labels/requirements/semantic-label-deprecated-schema.md) | A deprecated `SemanticsAPI` label has been migrated to `SemanticsLabelsAPI`. | Only on prims that still carry legacy labels |
| [`SL.003`](../../capabilities/semantic_labels/requirements/semantic-label-schema.md) | Labels use the `SemanticsLabelsAPI` schema. | Always |
| [`SL.TIME.001`](../../capabilities/semantic_labels/requirements/semantic-label-time.md) | Labels have no time samples. | RTX perception pipelines |
| [`SL.MAT.001`](../../capabilities/semantic_labels/requirements/semantic-label-material.md) | Each `Material` prim has a non-empty `SemanticsLabelsAPI:material` label. | NVIDIA convention |
| [`SL.QCODE.001`](../../capabilities/semantic_labels/requirements/semantic-label-qcode-valid.md) | Wikidata Q-codes are well-formed: `Q` followed by digits. | Opt-in, Wikidata only |

Applying the schema without authoring a value does not satisfy `SL.001`: an
empty label counts as no label.

These rules are split across three features, so you only take on the ones that
apply to your work:

| Feature | Holds | Select it when |
|---|---|---|
| `FET_011_STANDARD` 0.2.0 | `SL.001`, `SL.002`, `SL.003` | Always. Any taxonomy, any runtime. |
| `FET_011_RTX` 0.1.0 | `SL.TIME.001`, `SL.MAT.001` | You are targeting the NVIDIA RTX perception pipeline. Depends on `FET_011_STANDARD` 0.2.0. |
| `FET_046_STANDARD` 0.1.0 | `SL.QCODE.001` | You are labeling with Wikidata Q-codes. Depends on `FET_011_STANDARD` 0.2.0. |

`FET_011_STANDARD` 0.2.0 is selected by `Prop-Robotics-Neutral` and
`Prop-Robotics-Physx` at 2.3.0, and by `Prop-Robotics-Isaac`,
`Robot-Body-Neutral`, `Robot-Body-Runnable` and `Robot-Body-Isaac` at 1.2.0.
`Prop-Robotics-Physx` 2.3.0 also selects `FET_011_RTX` 0.1.0.

## 2. Establish a baseline

Start from an asset with no labels at all, so you can see the failure before you
fix it.

```bash
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles --profile Prop-Robotics-Neutral --version 2.3.0 ASSET
```

```{note}
The capability validators import `numpy`, which `simready-validate` does not
install itself. If this first run stops with
`ModuleNotFoundError: No module named 'numpy'`, add it to the same environment
and run again.
```

The line to look for:

```text
Asset: toaster.usda
  [FAILED] Prop-Robotics-Neutral v2.3.0
           FET_011_STANDARD: failing requirements: ['com.nvidia.simready.SL.001']
```

Requirement codes appear fully qualified in the report, so `SL.001` shows up as
`com.nvidia.simready.SL.001`. Other features may fail on the same asset for
reasons that have nothing to do with labels; this guide only follows the
`FET_011_STANDARD` line.

The validator looks for a label on the prim itself, its ancestors, its bound
material, and its `GeomSubset`s. Those are also the places where a fix can go.

## 3. Assign labels in Python

The Python route needs `usd-core` and nothing else. No Kit, no Isaac Sim. This
is how a data-augmentation vendor would label a batch of assets.

```python
from pxr import Usd, UsdSemantics

stage = Usd.Stage.Open("asset.usda")
prim = stage.GetDefaultPrim()

labels = UsdSemantics.LabelsAPI.Apply(prim, "class")
labels.CreateLabelsAttr(["toaster"])

stage.GetRootLayer().Save()
```

Which gives you:

```usd
def Xform "Toaster" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["toaster"]
}
```

That is one label on the `defaultPrim`, exactly what the contract asks for. Run
the validation command from step 2 again and the semantic-labels feature will
drop off the failing list.

### Labeling subcomponents

The root label satisfies the requirement. Labels on the parts inside an asset
give a model more to work with: something learning to grasp a toaster benefits
from knowing which mesh is the lever and which is the slot.

Parts continue to inherit the root label, so a labeled part ends up with both.
Walk the imageable prims and label the ones you have names for:

```python
from pxr import Usd, UsdGeom, UsdSemantics

stage = Usd.Stage.Open("toaster.usda")

PART_LABELS = {
    "Lever": "lever",
    "Slot": "slot",
    "Handle": "handle",
}

for prim in stage.Traverse():
    if not prim.IsA(UsdGeom.Imageable):
        continue
    label = PART_LABELS.get(prim.GetName())
    if label:
        UsdSemantics.LabelsAPI.Apply(prim, "class").CreateLabelsAttr([label])

stage.GetRootLayer().Save()
```

Label the things a consumer would want to tell apart. Giving every mesh
its own label is rarely what you want, since a mesh that exists for modeling
convenience has no semantic meaning and only adds noise to a segmentation mask.

**When one mesh holds several parts.** `SL.001` will also resolve a label
through `GeomSubset` membership, so a single mesh divided into subsets can hold
a label per region without being split into separate prims. This comes up often
with CAD conversions, where geometry tends to arrive as one mesh per material
rather than one mesh per part.

### Checking what a prim resolves to

`UsdSemantics.LabelsQuery` tells you what a prim resolves to, using only
`usd-core`, without a validator run:

```python
from pxr import Usd, UsdSemantics

stage = Usd.Stage.Open("toaster.usda")
query = UsdSemantics.LabelsQuery("class", Usd.TimeCode.Default())

for path in ["/Toaster", "/Toaster/Lever", "/Toaster/Bracket"]:
    prim = stage.GetPrimAtPath(path)
    print(path, list(query.ComputeUniqueInheritedLabels(prim)))
```

```text
/Toaster ['toaster']
/Toaster/Lever ['lever', 'toaster']
/Toaster/Bracket ['toaster']
```

`Bracket` has no label of its own and still resolves to `toaster`, inherited
from the root. `Lever` resolves to two labels: the one you gave it and the one
it inherits.

### Labeling materials

Object labels answer *what is this*. Material labels answer *what is it made
of*. Because they answer different questions they use different taxonomy
instance names and live side by side on the same asset.

`SL.MAT.001` asks that every `Material` prim has a non-empty
`SemanticsLabelsAPI:material` label:

```python
from pxr import Usd, UsdShade, UsdSemantics

stage = Usd.Stage.Open("toaster.usda")

MATERIAL_LABELS = {
    "ChromeBody": "metal",
    "PlasticBase": "plastic",
}

for prim in stage.Traverse():
    if not prim.IsA(UsdShade.Material):
        continue
    label = MATERIAL_LABELS.get(prim.GetName())
    if label:
        UsdSemantics.LabelsAPI.Apply(prim, "material").CreateLabelsAttr([label])

stage.GetRootLayer().Save()
```

Both taxonomies then sit on the asset without conflicting:

```usd
def Xform "Toaster" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["toaster"]

    def Material "ChromeBody" (
        prepend apiSchemas = ["SemanticsLabelsAPI:material"]
    )
    {
        token[] semantics:labels:material = ["metal"]
    }
}
```

A prim can resolve its label through its bound material, so a material label
also satisfies `SL.001` for any geometry bound to that material. If some
geometry is awkward to reach directly, label the material it uses instead.

`SL.MAT.001` belongs to `FET_011_RTX`, so it only applies once you have
selected the NVIDIA conventions.

### Using Wikidata Q-codes

Everything so far has used free-text labels, which the contract allows. NVIDIA's
Omniverse asset libraries label with
[Wikidata](https://www.wikidata.org) Q-codes, under the instance name
`wikidata_qcode`. If your assets will sit alongside those libraries, use the same
taxonomy.

A Q-code is a stable identifier for one Wikidata item. `Q1420` is "motor car",
`Q89` is "apple". To find one, search wikidata.org for the term and read the
Q-code off the item's URL.

Four things a code gives you that a free-text string cannot:

- **It survives renaming.** The code stays the same even when the
  human-readable name is edited or the item is retitled.
- **It resolves in any language.** Every item comes with labels, descriptions
  and aliases in hundreds of languages, so one code serves consumers reading
  English, Japanese, German or Hindi. You maintain no translation table.
- **It sits in a hierarchy.** Items are linked by *instance of* and *subclass
  of*, so you can walk up from a leaf label to a broader category, from
  `aluminium` to `metal` to `chemical substance`. That lets you coarsen labels
  for training without re-annotating anything.
- **It disambiguates.** Each item has a short description and a list of
  aliases, which is how you confirm you mean the animal and not the car brand.

```usd
def Xform "Apple" (
    prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:wikidata_qcode = ["Q89"]   # Q89 = apple
}
```

**Always comment the code.** Nobody reading a diff can tell that `Q11426` means
"metal".

`SL.QCODE.001` only checks the format: `Q` followed by one or more digits. It
never contacts wikidata.org, since a USD validator should not depend on network
access. A well-formed code pointing at nothing real will still pass, so
checking that a code means what you think it means is your job.

This rule lives in `FET_046_STANDARD`, which you select only if you have
committed to the Wikidata taxonomy.

## 4. Assign labels in Blender

The [SimReady Blender add-on](https://github.com/NVIDIA/simready-blender-add-on)
(CORE Artist Tools) searches Wikidata and applies labels from inside Blender,
either to the asset as a whole or to individual objects. Its own reference
documents the panels and how to reach them:

- [SimReady Metadata](https://nvidia.github.io/simready-blender-add-on/Blender_CORE_Addon_reference.html#simready-metadata)
  for the asset-root label
- [Object Data > Wikidata Metadata](https://nvidia.github.io/simready-blender-add-on/Blender_CORE_Addon_reference.html#object-data-wikidata-metadata)
  for per-object labels

The add-on's exporter writes the `SemanticsLabelsAPI` schemas as it saves.

Labels applied to individual objects are re-authored from Blender's own data
during export, because Blender's USD exporter does not carry the string arrays
they are stored in. That happens inside the add-on; nothing is required of you.

To export from a script or headless, take the add-on's export path rather than
Blender's bare `wm.usd_export`, which does not run the hook and so writes no
semantics:

```python
from CORE_ArtistTools.addon.library.run_export_gui import simready_usd_hook_active

with simready_usd_hook_active():
    bpy.ops.wm.usd_export(filepath="asset.usd")
```

Both need add-on 2026.8.0 or later.

## 5. Validate

Run the same command as step 2, this time against the labeled asset:

```bash
simready-validate --rules-path nv_core/sr_specs/docs/capabilities --features-path nv_core/sr_specs/docs/features --profiles-path nv_core/sr_specs/docs/profiles --profile Prop-Robotics-Neutral --version 2.3.0 ASSET
```

`FET_011_STANDARD` drops off the failing list. Nothing replaces it in the output;
the feature stops being reported.

Add `--output results.json` if you want a machine-readable report, or
`--stamp-asset-validation` to record the outcome in the asset's
`customLayerData`. The
[SimReady Validation Workflow](../validate_workflow.md) covers both.

## 6. Verify at runtime

Two benchmarks work as a pair. The first renders the RTX semantic-segmentation
pass, an extra render output recording which object each pixel belongs to, and
measures how much of the frame carries a label. The second removes every
semantics schema from the asset and renders the same frame again, which should
come back empty.

```bash
simready-benchmark --assets ASSET --features FET_011
```

Measured on the sample toaster, Isaac Sim 6.0.1:

```text
semantic_labels_seg_labelled   PASS
  semantic_labels_on_coverage        0.280968

semantic_labels_seg_stripped   PASS
  semantic_labels_off_coverage       0.000022
  semantic_labels_stripped_prims     8
```

The toaster carries one label on its root prim, and 28% of the frame came back
segmented, which is the whole silhouette of the asset. Every mesh beneath that
root inherited the label, and you authored none of
them. Removing the labels from all 8 label sources dropped coverage to
0.002%, so nothing else in the scene was producing that segmentation.

```{note}
The two run as separate tests because Replicator's orchestrator can only be
stepped once per engine session, so a single test cannot render the same asset
twice. Both tests need Isaac Sim 6.0 or later.
```

```{note}
Do not try to verify labels by matching segmentation colors. The color assigned
to each object is not stable between runs, which is why these benchmarks measure
coverage instead.
```

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `SL.001` fails on an asset that visibly has labels | The schema is applied but no value was authored. | Author at least one value in `semantics:labels:<taxonomy>`. |
| `SL.001` fails on some meshes only | Renderable geometry sits outside the labeled subtree. | Label the outlying prims, or move the label up to a common ancestor. |
| Labels resolve to nonsense downstream | The taxonomy name was written into the value. | See below. |
| `SL.002` fails | A deprecated `SemanticsAPI` label has no modern equivalent. | Add the equivalent `SemanticsLabelsAPI` label. The validator offers this as a suggestion. |
| `SL.002` warns | Both schemas hold the same value. | Remove the deprecated schema and its `semantic:<instance>:params:*` attributes. |
| `SL.TIME.001` fails | Labels are time-sampled. | Author a static value. Time-varying labels are valid OpenUSD, but the RTX static-label pipeline does not read them. |
| Segmentation blank in the benchmark, though validation passed | Isaac Sim earlier than 6.0 does not read `SemanticsLabelsAPI`. | Run on 6.0 or later. |

### The instance-name-as-value mistake

This pattern turns up in some shipped content, and it is wrong:

```usd
# Wrong: the taxonomy name is sitting in the value slot
token[] semantics:labels:wikidata_qcode = ["wikidata_qcode"]
```

The instance name after the last colon already says which taxonomy this is. The
value is for what the thing *is*:

```usd
# Right
token[] semantics:labels:wikidata_qcode = ["Q89"]   # Q89 = apple
```

No validator will catch the wrong version, because `"wikidata_qcode"` is a
valid label string as far as `SL.001` is concerned. Only a human
reading the file, or a downstream consumer getting nonsense back, will spot it.

Current CORE Artist Tools writes the correct form, and its exporter migrates the
broken pattern wherever it finds it. Assets made with older tooling may still
have it, so check before you trust an inherited `.blend`.

## Where to go next

- [Semantic Labels capability](../../capabilities/semantic_labels/capability-semantic_labels.md) for the contract in full.
- [SimReady Validation Workflow](../validate_workflow.md) for validator setup, JSON reports and stamping.
- [SimReady Benchmark](../benchmark/benchmark.md) for the runtime test framework.
- [Profiles](../profiles/profiles.md) for which profiles select the semantic-labels feature.
