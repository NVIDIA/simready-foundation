# Assembly

Capabilities in this category define mechanical mate sites on standalone assets and realized pairings on assembly stages. A pairing is realized either by an authored fixed joint between two rigid bodies, or by composition when both parts have their own rigid bodies disabled beneath a single compound body that carries their combined mass.

Mating spans physics (enabled rigid-body ancestry, authored fixed joints, aggregate mass, payload) and composition (referenced child assets, a shared compound body), so it sits beside `physics_bodies/` rather than inside it. The implemented contract is mechanical mating, in two shapes: a gripper, tool, or sensor mounted on an arm as a detachable jointed pairing, and interlocking parts such as a pallet stack composed into a single physics actor.

The `simready:mate:realization` token on each connection names which shape it is, and that choice selects the governing feature: `compound` connections are specified entirely by `CAP027_Connections`, while `jointed` connections additionally require the authored joint specified by `CAP029_ConnectionJoint` and its runtime variants.

```{toctree}
:maxdepth: 1

Mates <mates/capability-mates>
Connections <connections/capability-connections>
```
