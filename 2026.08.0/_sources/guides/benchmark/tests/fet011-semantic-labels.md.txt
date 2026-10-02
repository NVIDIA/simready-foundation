# FET011 Semantic Labels

Tests in this family verify that an asset's SimReady semantic labels drive the RTX
semantic-segmentation AOV at runtime — that the labels an author declares are the labels the
renderer segments.

## Overview

Two tests work as a pair. The first renders the segmentation AOV of the asset as authored and
measures how much of the frame carries a label. The second removes every semantics schema the
`SL.001` contract recognises and renders the same frame again, which should come back empty.

A populated buffer on its own proves nothing: scene content, a leftover label on a shared
material, or a stray label elsewhere would produce one too. Measuring the same frame with the
labels gone is what closes that gap, and it is why this is two tests rather than one.

They run in separate engine sessions because Replicator's orchestrator can be stepped only once
per session, so a single test cannot render the same asset twice.

Verified on Isaac Sim 6.0, whose Replicator reads `SemanticsLabelsAPI` natively: a label authored
on an object resolves to that object's child meshes, so no migration to the deprecated
`SemanticsAPI` schema is required.

## What a Passing Family Means

A reviewer, PM, OEM, or data-augmentation partner producing labeled content can trust that the
asset's `SemanticsLabelsAPI` labels are honored by the RTX segmentation pipeline — that the asset
yields usable per-object segmentation masks in synthetic-data generation.

This is the runtime counterpart to the offline validator. Label *format* correctness is checked by
`validation.py`; this family confirms the labels actually render.

## Tests

:::{list-table}
:header-rows: 1
:widths: 30 45 25

* - Test
  - What It Checks
  - Validates
* - [semantic_labels_seg_labelled](fet011/semantic-labels-seg.md)
  - Renders the segmentation AOV with the asset as authored and measures the fraction of the frame that resolves to a label. Passes at or above `on_coverage_min`.
  - FET_011_STANDARD, FET_011_RTX
* - [semantic_labels_seg_stripped](fet011/semantic-labels-seg.md)
  - Removes every semantics schema from the sources `SL.001` recognises, renders the same frame, and requires the buffer to come back effectively blank. Passes at or below `off_coverage_max`.
  - FET_011_STANDARD, FET_011_RTX
:::

## Relationship to the Feature

This family validates the runtime behavior described by
[FET011 Semantic Labels](../../../features/FET_011_STANDARD.md) and
[FET_011_RTX](../../../features/FET_011_RTX.md). Label authoring and format rules live in the
[Semantic Labels capability](../../../capabilities/semantic_labels/capability-semantic_labels.md).

```{toctree}
:maxdepth: 1
:hidden:

Segmentation AOV <fet011/semantic-labels-seg>
```
