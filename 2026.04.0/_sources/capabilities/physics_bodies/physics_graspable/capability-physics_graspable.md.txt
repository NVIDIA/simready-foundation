# Graspable Vectors

**Capability:** Graspable Vector (GSP)

<!-- SCORE_TAG: LIST_OF_REQUIREMENTS -->

```{include} /capabilities/_includes/badges/physics_graspable.md
```

## Overview

This capability enables the viability of an asset being graspable in physics simulations (by robotic grippers). The feature itself needs to be coupled with a runtime test that analyzes grasp vectors passed from the asset, and helps it define whether it helps these points to be grasped.

Grasp vectors can be configured or authored in Usd via basis curves (recommended) or mesh (not viewable in most runtimes).   

```{toctree}
:maxdepth: 1

Requirements <requirements>
Creators <creators>
```