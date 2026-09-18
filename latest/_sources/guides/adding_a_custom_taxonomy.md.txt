# Adding a Custom Taxonomy

## At a glance

SimReady's semantic labeling is **taxonomy-agnostic**. NVIDIA's Omniverse libraries use the Wikidata
Q-code taxonomy (`SemanticsLabelsAPI:wikidata_qcode`), but you can label assets with any vocabulary —
COCO, Cityscapes, ADE20K, or one you define yourself. This guide shows how to add a brand-new
taxonomy as its own toggleable SimReady feature with a closed-vocabulary validator, using the bundled
**COCO** taxonomy as the worked example:

- [Semantic Labels - COCO feature](../features/FET_040_STANDARD.md)
- [COCO.001 requirement](../capabilities/dataset_taxonomies/requirements/coco-labels.md)
- [Open-Taxonomy-COCO example profile](../profiles/open-taxonomy-coco.md)

The recipe — five small, self-contained steps:

1. Pick an instance-name convention (the taxonomy slug).
2. Drop in a `taxonomies/<slug>.json` vocabulary file.
3. Add a `<SLUG>.001` requirement and subclass the membership checker.
4. Define a feature and wire an example profile.
5. Re-run codegen and validate.

---

## Before you start

Create a taxonomy feature when a downstream consumer — for example, a synthetic-data or ML-training
pipeline — requires labels from an exact class vocabulary and you want a profile to enforce that
contract. The feature remains opt-in: assets and profiles that do not select it are unaffected.

You do **not** need a new feature merely to author labels from a different vocabulary. The
vendor-neutral [SL.001](../capabilities/semantic_labels/requirements/semantic-label-capability.md)
accepts any non-empty `SemanticsLabelsAPI:<instance>` label. Add the feature only when
out-of-vocabulary values should fail validation.

Before implementing one, identify:

- an authoritative, redistributable source for the vocabulary and its version;
- a stable instance-name slug that will appear in authored USD;
- the canonical class names and any accepted display names or aliases; and
- an unused requirement code and feature ID.

The files linked above form the complete COCO reference implementation. The shared implementation
lives in the
[Dataset Taxonomies capability](../capabilities/dataset_taxonomies/capability-dataset_taxonomies.md).

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

The vendor-neutral [SL.001](../capabilities/semantic_labels/requirements/semantic-label-capability.md)
requirement only asks "is there *a* label?". A taxonomy feature adds the next question: "is the label
a valid class in *this* taxonomy?" — a **closed-vocabulary** check.

## 1. Pick an instance-name convention

Choose a short, stable slug for your taxonomy and use it as the `SemanticsLabelsAPI` instance name and
as the data-file name. The bundled examples use the dataset slug: `coco`, `cityscapes`, `ade20k`,
`pascal_voc`, `sunrgbd`, `imagenet_1k`.

## 2. Add the vocabulary data file

Create `capabilities/dataset_taxonomies/taxonomies/<slug>.json`. Data lives in JSON (not in code) so
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

Add `capabilities/dataset_taxonomies/requirements/<slug>-labels.md` with the requirement table the
codegen reads, and list it in `capabilities/dataset_taxonomies/requirements.md` and the capability's
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

Subclass `_TaxonomyMembershipChecker` in `capabilities/dataset_taxonomies/validation.py` — set the
slug and requirement; the shared base does scoping, parsing, and membership classification:

```python
@register_requirements(cap.DatasetTaxonomiesRequirements.COCO_001, override=True)
class CocoLabelsChecker(_TaxonomyMembershipChecker):
    SLUG = "coco"
    REQUIREMENT = cap.DatasetTaxonomiesRequirements.COCO_001
```

A brand-new capability (rather than reusing `dataset_taxonomies`) would also add the
`from .<capability> import validation` line to `capabilities/__init__.py` and an entry in
`capabilities/capabilities.md` — see
[Adding a New Feature](features_expansion_workflow.md) Appendix A.

## 4. Define a feature and a profile

Feature JSON `features/FET_0NN_semantic_labels_<slug>_neutral-0.1.0-<slug>_labels.json`:

```json
{
    "id": "FET_040_STANDARD",
    "version": "0.1.0",
    "display_name": "Semantic Labels - COCO",
    "path": "features/FET_040_STANDARD.html",
    "requirements": ["COCO.001"]
}
```

Add a feature markdown and a row + toctree entry in `features/features.md`, then add an example
profile to a TOML file under `profiles/` (and a matching profile doc):

```toml
[Open-Taxonomy-COCO]
"0.1.0" = {features = [
    {"FET_000_STANDARD" = {version = "0.1.0"}},
    {"FET_040_STANDARD" = {version = "0.1.0"}},
]}
```

## 5. Re-run codegen and validate

The `cap.*Requirements` enums are **code-generated** from the requirement markdown, feature JSON, and
the profile TOML files. After adding a requirement you must regenerate them or the validator raises
`AttributeError` at load:

```bash
cd nv_core/sr_specs && ./codegen.sh
```

Then validate an asset against your profile:

```bash
simready-validate \
  --rules-path nv_core/sr_specs/docs/capabilities \
  --features-path nv_core/sr_specs/docs/features \
  --profiles-path nv_core/sr_specs/docs/profiles \
  --profile Open-Taxonomy-COCO --version 0.1.0 <asset>.usda
```

A value outside the taxonomy fails the requirement; a non-canonical spelling passes with a warning; a
canonical class name passes silently.
