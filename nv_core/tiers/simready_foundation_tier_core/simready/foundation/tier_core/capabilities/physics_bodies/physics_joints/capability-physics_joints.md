# Physics Joints

**Capability:** Joints (JT)

```{include} /capabilities/_includes/badges/physics_joints.md
```

## Overview

This capability enables creation of articulated mechanical systems with constrained motion, simulation of mechanical assemblies like robots and modeling of mechanical joints with specific degrees of freedom.

Joints are fixed attachments that can represent the way a drawer is attached to a cabinet, a wheel to a car, or links of a robot to each other. A joint constrains the movement of rigid bodies and can be created between two rigid bodies or between one rigid body and world.

Mathematically, jointed assemblies can be modeled either in maximal (world space) or reduced (relative to other bodies) coordinates. An extension to the joint system based on reduced coordinates is provided with **Articulations**.

```{toctree}
:maxdepth: 1

Requirements <requirements>
Creators <creators>
```
