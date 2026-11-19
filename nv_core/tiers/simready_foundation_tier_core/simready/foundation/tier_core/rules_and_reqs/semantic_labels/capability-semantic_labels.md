# Semantic Labels

## Overview

This capability provides requirements for semantic label attributes. These semantics may be used to provide ground truth for ML training by verifying perception system identification and classification of objects 

![Semantic Labels AOV view](images/Robotic_Arm_SemanticLabels.png)

## Summary

- **Geometry is semantically labeled**
- **Semantic labels can be inherited from ancestral prims as well as bound materials**
- **NVIDIA uses the QCode taxonomy for its Omniverse Asset libraries. Assets intended to be used alongside NVIDIA assets should use the same taxonomy.**

## Granularity

**Every renderable mesh must resolve a semantic label** — this is the requirement, [SL.001](requirements/semantic-label-capability.md). Because labels are inherited, a single label on a common ancestor (typically the asset's `defaultPrim` / root) satisfies it for all descendant geometry, so **one label per asset is the minimum** — as long as every renderable prim sits under a labeled ancestor, carries its own label, or is labeled through its bound material. Any renderable geometry outside a labeled subtree must be labeled separately.

In practice, label the asset as a whole first ("car," "pedestrian," "forklift"). Additional labels on parts within the asset (e.g. "tire," "windshield," "hubcap") are optional and increase the usefulness of the semantic labels for ML training.

## Taxonomy

A taxonomy is identified by the `SemanticsLabelsAPI` instance name (for example, `SemanticsLabelsAPI:class`). This capability is taxonomy-agnostic: any instance name is valid, and thanks to the OpenUSD `SemanticsLabelsAPI` "Multiple Apply" schema design, multiple taxonomies can coexist on the same prim without conflict.

NVIDIA's Omniverse Asset libraries use the Wikidata Q-code taxonomy (instance name `wikidata_qcode`). Assets intended for use alongside NVIDIA assets should use the same taxonomy; its formatting and validity rules are an NVIDIA-specific requirement — see [Semantic Label QCode Valid (SL.QCODE.001)](requirements/semantic-label-qcode-valid.md).

## Schema / OpenUSD Specification

Semantic Labels are defined with the [`SemanticsLabelsAPI` schema](https://openusd.org/release/api/usd_semantics_overview.html). Available in OpenUSD 24.11 and later.

## USDA Sample

The instance name (here `class`) identifies the taxonomy; any taxonomy may be used.

```usd
def Xform "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:class"]
)
{
    token[] semantics:labels:class = ["car"]
}
```

### Requirements

<!-- SEMANTIC_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- SEMANTIC_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements
requirements/semantic-label-capability
requirements/semantic-label-deprecated-schema
requirements/semantic-label-qcode-valid
requirements/semantic-label-schema
requirements/semantic-label-time
requirements/semantic-label-material
```
