# Semantic Labels

## Overview

This capability provides requirements for semantic label attributes. These semantics may be used to provide ground truth for ML training by verifying perception system identification and classification of objects 

![Semantic Labels AOV view](images/Robotic_Arm_SemanticLabels.png)

## Summary

- **Geometry is semantically labeled**
- **Semantic labels can be inherited from ancestral prims as well as bound materials**
- **NVIDIA uses the QCode taxonomy for its Omniverse Asset libraries. Assets intended to be used alongside NVIDIA assets should use the same taxonomy.**

## Granularity

**At least one semantic label** should be provided per asset, to identify it as a "car," "pedestrian," "forklift," etc. Additional semantic labels on parts within the asset (e.g. "tire," "windshield," "hubcap," etc.) increases the usefulness of the semantic labels for ML training.

## Taxonomy

### Wikidata Taxonomy

NVIDIA chose to utilize [**Wikidata**](https://wikidata.org) for Omniverse Asset libraries - an open-source taxonomy database with over 115 million searchable items including objects, brands, and locations.

### Different/Multiple Taxonomies

While NVIDIA utilizes Wikidata Q-codes as the primary taxonomy, developers may implement alternative taxonomies that better fit their specific use cases. Thanks to the OpenUSD `SemanticsLabelsAPI`'s "Multiple Apply" schema design, multiple taxonomies can coexist on the same object without conflict, allowing for flexible and comprehensive semantic labeling.

## Schema / OpenUSD Specification

Semantic Labels are defined with the [`SemanticLabelsAPI` schema](https://openusd.org/dev/api/usd_semantics_overview.html). Available in OpenUSD 24.11 and later.

## USDA Sample

```usd
def XForm "Vehicle" (
    prepend apiSchemas = ["SemanticsLabelsAPI:wikidata_qcode"]
)
{
    token[] semantics:labels:wikidata_qcode = ["Q42889"]
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
requirements/semantic-label-schema
requirements/semantic-label-qcode-valid
requirements/semantic-label-time
```
