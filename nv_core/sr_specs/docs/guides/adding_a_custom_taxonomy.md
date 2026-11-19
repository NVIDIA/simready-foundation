# Adding a Custom Taxonomy

## At a glance

SimReady's semantic labeling is **taxonomy-agnostic**. NVIDIA's Omniverse libraries use the Wikidata
Q-code taxonomy (`SemanticsLabelsAPI:wikidata_qcode`), but you can label assets with any vocabulary —
COCO, Cityscapes, ADE20K, or one you define yourself. This guide shows how to add a brand-new
taxonomy as its own selectable SimReady capability with a closed-vocabulary validator, using the
bundled **COCO** taxonomy as the worked example:

- [Semantic Labels - COCO capability](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities/CAP040_CocoLabels.md)
- [COCO.001 requirement](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/dataset_taxonomies/requirements/coco-labels.md)
- [Open-Taxonomy-COCO example profile](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles/open-taxonomy-coco.md)

The recipe — five small, self-contained steps:

1. Pick an instance-name convention (the taxonomy slug).
2. Drop in a `taxonomies/<slug>.json` vocabulary file.
3. Add a `<SLUG>.001` requirement and subclass the membership checker.
4. Define a capability and wire an example profile.
5. Validate.

---

## Before you start

Create a taxonomy capability when a downstream consumer — for example, a synthetic-data or
ML-training pipeline — requires labels from an exact class vocabulary and you want a profile to
enforce that contract. The capability remains opt-in: assets and profiles that do not select it are
unaffected.

You do **not** need a new capability merely to author labels from a different vocabulary. The
vendor-neutral [SL.001](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/semantic_labels/requirements/semantic-label-capability.md)
accepts any non-empty `SemanticsLabelsAPI:<instance>` label. Add the capability only when
out-of-vocabulary values should fail validation.

Before implementing one, identify:

- an authoritative, redistributable source for the vocabulary and its version;
- a stable instance-name slug that will appear in authored USD;
- the canonical class names and any accepted display names or aliases; and
- an unused requirement code and capability ID.

The files linked above form the complete COCO reference implementation. The shared implementation
lives in the
[Dataset Taxonomies capability](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/dataset_taxonomies/capability-dataset_taxonomies.md).

## 0. Concepts

A **taxonomy** is identified by a `SemanticsLabelsAPI` instance name. Because `SemanticsLabelsAPI` is
a "Multiple Apply" schema, an asset can carry several taxonomies at once without conflict:

```usd
def Xform "Car" (
    prepend apiSchemas = ["SemanticsLabelsAPI:coco", "SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:coco = ["car"]
    token[] semantics:labels:wikidata_qcode = ["Q1420"]
}
```

The vendor-neutral [SL.001](../../../tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs/semantic_labels/requirements/semantic-label-capability.md)
requirement only asks "is there *a* label?". A taxonomy capability adds the next question: "is the
label a valid class in *this* taxonomy?" — a **closed-vocabulary** check.

## 1. Pick an instance-name convention

Choose a short, stable slug for your taxonomy and use it as the `SemanticsLabelsAPI` instance name and
as the data-file name. The bundled examples use the dataset slug: `coco`, `cityscapes`, `ade20k`,
`pascal_voc`, `sunrgbd`, `imagenet_1k`.

## 2. Add the vocabulary data file

Create `rules_and_reqs/dataset_taxonomies/taxonomies/<slug>.json`. Data lives in JSON (not in code) so
adding a taxonomy is "drop in a file". The loader (`taxonomy_data.py`) reads `name`, `display_name`,
and `aliases` from each entry:

```json
{
    "instance_name": "coco",
    "taxonomy_name": "COCO Instances",
    "taxonomy_version": "source-file-2026-05-15",
    "label_count": 80,
    "labels": [
        {"name": "person", "display_name": "Person", "aliases": ["human"]},
        {"name": "car", "display_name": "Car"}
    ]
}
```

Matching is lenient: case-insensitive, `_`/`-` treated as spaces, and display names / aliases accepted.
A value that matches only after normalization passes with a warning suggesting the canonical `name`.

## 3. Add a requirement and a checker

### 3a. Requirement markdown

Add `rules_and_reqs/dataset_taxonomies/requirements/<slug>-labels.md` with the requirement table the
codegen reads, and list it in `rules_and_reqs/dataset_taxonomies/requirements.md` and the capability's
toctree:

```markdown
# coco-labels

| Code     | COCO.001 |
|----------|-----------|
| Validator| {oav-validator-latest-link}`coco-001` |
| Compatibility | {compatibility}`core-usd` |
| Tags     | {tag}`usability` |
```

### 3b. Checker

Subclass `_TaxonomyMembershipChecker` in `rules_and_reqs/dataset_taxonomies/validation.py` — set the
slug and requirement; the shared base does scoping, parsing, and membership classification:

```python
@register_requirements(cap.DatasetTaxonomiesRequirements.COCO_001, override=True)
class CocoLabelsChecker(_TaxonomyMembershipChecker):
    SLUG = "coco"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.COCO_001
```

A brand-new requirement category (rather than reusing `dataset_taxonomies`) would also add the
`from .<category> import validation` line to `rules_and_reqs/__init__.py` and an entry in
`nv_core/sr_specs/docs/shared/rules_and_reqs/rules_and_reqs.md` — see [Naming Conventions](naming_conventions.md) for the folder
layout.

## 4. Define a capability and a profile

A taxonomy check is static and has no runtime tests, so it is a capability. Create
`capabilities/CAP0NN_<Name>Labels.0-1-0.json`, named after its ID; the COCO example is
`capabilities/CAP040_CocoLabels.0-1-0.json`:

```json
{
    "id": "CAP040_CocoLabels.0-1-0",
    "display_name": "Semantic Labels - COCO",
    "requirements": ["COCO.001"]
}
```

Add a capability markdown page beside it and a row in the shared capability index
(`nv_core/sr_specs/docs/shared/capabilities/capabilities.md`), then add an example profile to a TOML
file under `profiles/` (and a matching profile doc). Select `FET011_SemanticLabels` alongside
the taxonomy so that geometry must carry a label at all:

```toml
[Open-Taxonomy-COCO]
"0.1.0" = {features = [
    {selector = "FET011_SemanticLabels.0-2-0"},
], capabilities = [
    {selector = "CAP000_Core.0-1-0"},
    {selector = "CAP040_CocoLabels.0-1-0"},
]}
```

## 5. Validate

The `cap.*Requirements` enums are **code-generated** from the requirement markdown. `simready-validate`
generates them when it loads a rules directory, and the tier wheel build generates them for an
installed tier, so there is no separate codegen step.

Validate an asset against your profile from the repository root:

```bash
simready-validate \
  --rules-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/rules_and_reqs \
  --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/capabilities \
  --features-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/features \
  --profiles-path nv_core/tiers/simready_foundation_tier_core/simready/foundation/tier_core/profiles \
  --profile Open-Taxonomy-COCO --version 0.1.0 <asset>.usda
```

A value outside the taxonomy fails the requirement; a non-canonical spelling passes with a warning; a
canonical class name passes silently.
