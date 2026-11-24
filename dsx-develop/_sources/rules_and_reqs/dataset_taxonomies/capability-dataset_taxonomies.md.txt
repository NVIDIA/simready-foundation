# Dataset Taxonomies

```{note}
**Proof-of-concept.** This capability demonstrates the pattern — using non-NVIDIA taxonomies as
toggleable features with closed-vocabulary validators, and how to add your own — rather than serving
as an authoritative implementation. Some details (e.g. filtering out editor scaffolding / non-content
geometry) are intentionally simple and should be hardened by the SimReady team before these checks are
treated as canonical.
```

## Overview

This capability provides closed-vocabulary validators for several **open dataset taxonomies** —
public label spaces used widely in computer vision. Each one checks that the values authored on a
`SemanticsLabelsAPI:<taxonomy>` instance are real members of that taxonomy.

It exists to demonstrate that SimReady semantic labeling is **not** tied to NVIDIA's Wikidata Q-code
taxonomy: you can label assets with COCO, Cityscapes, ADE20K, PASCAL VOC, SUN RGB-D, or ImageNet-1K
classes — or follow the same recipe to add your own. See
[Adding a custom taxonomy](../../guides/adding_a_custom_taxonomy.md).

## Relationship to Semantic Labels

This capability builds on the vendor-neutral [Semantic Labels](../semantic_labels/capability-semantic_labels.md)
capability:

- **SL.001** (Semantic Labels) asks "is the geometry labeled *at all*?" — taxonomy-agnostic.
- These requirements ask "is the label a valid class in *this* taxonomy?" — closed-vocabulary.

Each taxonomy is identified by its own `SemanticsLabelsAPI` instance name (its slug). Because
`SemanticsLabelsAPI` is a "Multiple Apply" schema, an asset can carry several taxonomies at once
(e.g. `wikidata_qcode` and `coco`) without conflict.

## Taxonomy

| Requirement | Instance (slug) | Taxonomy | Classes |
|---|---|---|---|
| COCO.001 | `coco` | COCO (instances) | 80 |
| CITY.001 | `cityscapes` | Cityscapes (fine) | 35 |
| ADE.001 | `ade20k` | ADE20K | 150 |
| VOC.001 | `pascal_voc` | PASCAL VOC | 20 |
| SUN.001 | `sunrgbd` | SUN RGB-D | 10 |
| IN1K.001 | `imagenet_1k` | ImageNet-1K | 1000 |

Each taxonomy's vocabulary is stored as a single JSON data file under `taxonomies/<slug>.json` and
loaded by `taxonomy_data.py`. Matching is case-insensitive and tolerant of spacing and of display
names / aliases; a value that matches only after normalization passes with a warning suggesting the
canonical class name.

## Example assets

Because `SemanticsLabelsAPI` is a "Multiple Apply" schema, each asset carries only the taxonomies
whose vocabulary actually contains it — a common object appears in several, a domain-specific one in
few or none. Every asset keeps its vendor-neutral Wikidata Q-code regardless. A few of the bundled
sample assets illustrate the range:

| Asset | Semantic label instances | Why |
|---|---|---|
| Alcohol bottle | `wikidata_qcode` + `coco` + `pascal_voc` + `imagenet_1k` | A common object present in many taxonomies |
| Apple | `wikidata_qcode` + `coco` + `imagenet_1k` | Present in the object taxonomies |
| Workbench | `wikidata_qcode` + `ade20k` + `sunrgbd` | Scene / indoor-furniture taxonomies, not COCO |
| Sledgehammer | `wikidata_qcode` + `imagenet_1k` | Only ImageNet-1K lists it among these |
| Dish wand | `wikidata_qcode` | Not in any of these open taxonomies — Wikidata only |

The takeaway: you add a taxonomy label only where that taxonomy has a matching class, so not every
asset needs every taxonomy.

## Schema / OpenUSD Specification

Semantic labels use the [`SemanticsLabelsAPI` schema](https://openusd.org/release/api/usd_semantics_overview.html)
(OpenUSD 24.11+).

## USDA Sample

```usd
def Xform "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:coco"]
)
{
    token[] semantics:labels:coco = ["car"]
}
```

### Requirements

<!-- DATASET_TAXONOMIES_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- DATASET_TAXONOMIES_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements
requirements/coco-labels
requirements/cityscapes-labels
requirements/ade20k-labels
requirements/pascal-voc-labels
requirements/sunrgbd-labels
requirements/imagenet-labels
```
