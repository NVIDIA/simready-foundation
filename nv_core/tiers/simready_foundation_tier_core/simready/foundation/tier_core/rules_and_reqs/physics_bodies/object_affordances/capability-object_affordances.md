# Object Affordances

## Overview

The static contract is [CAP039_ObjectAffordances.0-1-0](../../../capabilities/CAP039_ObjectAffordances.md).

This capability defines object-side semantic taxonomies for the interactions a prop or component
offers and its current qualitative state. Assets author these values through the OpenUSD
`SemanticsLabelsAPI` "Multiple Apply" schema so that tools can discover objects by the interactions
they offer and query their declared state.

This capability defines vocabulary only. It does not define or validate functional affordance
behavior, including how an affordance is bound to a joint or driven joint, actuated by a controller,
or evaluated against a state threshold.

## Definitions

**Affordance** is a declared interaction that an object or component offers. It describes what a
consumer may attempt, independent of the object's current state or the mechanism that implements
the interaction. For example, a door remains `openable` whether it is currently open or closed.

**Affordance state** is the declared qualitative condition of the same interaction-bearing prim.
It describes the state relevant to an affordance, such as `open` or `closed`, and may change while
the affordance remains the same.

**Authoring an affordance asserts that the interaction is intended for an external agent.** Internal
mechanisms — drive trains, suspension, enclosed linkages — carry joints but are not labeled, and
their absence from this taxonomy is meaningful. This is what distinguishes a door handle from a
printer's internal hinge, and it is not expressible through joint types alone.

**The state channel is both authored and runtime.** The authored value is the prim's initial state.
Runtimes may update it. Consumers must not assume the authored value reflects current state once
simulation has begun. Requirements in this capability validate authored values.

Agent-side capability is out of scope. IEEE Std 1872.1-2024 covers agent capability and task
representation.

## Why this is needed

USD can represent joints, drives, and other physical mechanisms, but those structures do not
provide a common semantic query for the interactions an object offers, and they do not distinguish
an interaction surface intended for an agent from an internal mechanism. Without this metadata,
consumers must infer intent from prim names, hierarchy, or runtime-specific physics configuration.

Separating affordance from affordance state lets consumers answer two different questions:

- What interactions does this object offer, and how are they engaged?
- What qualitative state is the object currently declaring?

The shared taxonomy makes those queries independent of asset structure and physics runtime. It
also lets planning systems discover candidate interactions before a separate functional contract
evaluates whether a particular actor can perform them.

## Summary

- **Objects can be tagged with an affordance vocabulary** describing the interactions they offer,
  the motion used to engage them, and the shape of the resulting setting.
- **Objects can carry a qualitative state** drawn from a closed vocabulary, where each state value
  belongs to exactly one affordance.

## Taxonomy

The capability uses two `SemanticsLabelsAPI` taxonomy instances, reusing the same
taxonomy-agnostic, multiple-apply mechanism as
[Semantic Labels](../../semantic_labels/capability-semantic_labels.md):

| Instance | Attached to | Meaning |
| --- | --- | --- |
| `SemanticsLabelsAPI:affordance` | Object or component prims | Interactions the prim offers |
| `SemanticsLabelsAPI:affordance_state` | The same interaction-bearing prim | Current qualitative state |

`affordance_state` scopes the state value to the affordance taxonomy and distinguishes it from
other semantic state descriptors.

`SemanticsLabelsAPI:affordance` is the SimReady-controlled taxonomy. Assets that need additional or
simulator-specific values must author them in a separate instance, such as
`SemanticsLabelsAPI:affordance_company_a`. Multiple instances may coexist on the same prim.

### Affordance vocabulary

The vocabulary spans three axes. All values are case-sensitive and use the canonical lowercase
spelling shown.

| Axis | Affordance | Definition | State values |
| --- | --- | --- | --- |
| Actuation | `pressable` | Momentary mechanical actuator with travel; returns to rest; produces an effect | `pressed` / `unpressed` |
| Actuation | `touch_operable` | Contact actuates the control; no force or travel required | `touched` / `untouched` |
| Actuation | `rotatable` | Angular motion about an axis | — |
| Actuation | `slideable` | Linear translation | — |
| Outcome | `openable` | Affords transition between open and closed | `open` / `closed` |
| Outcome | `lockable` | Affords engaging a constraint that gates another affordance | `locked` / `unlocked` |
| Outcome | `accepts_insertion` | Affords receiving a mating part | `empty` / `occupied` |
| State topology | `toggleable` | Two discrete states persisting after release | `toggled_on` / `toggled_off` |
| State topology | `adjustable` | Affords setting a continuous value | — |

The three axes answer different questions: **actuation** describes what motion the agent applies,
**outcome** describes what the interaction accomplishes, and **state topology** describes what the
resulting setting looks like.

`rotatable` and `slideable` carry no state of their own; the state belongs to the outcome they
serve, so a sliding door's state is `open` or `closed`. `adjustable` resolves to a continuous value,
which cannot be expressed as a token and is addressed separately.

`pressed` and `touched` mean that the actuation threshold has been crossed, not that the actuator is
displaced or that contact occurred. A key can be one millimeter down and not pressed. Defined this
way, both values carry information that joint position and collision detection do not.

### Authoring rule

**Author every token that applies.** A sliding door is `["openable", "slideable"]`, not one or the
other. Because the vocabulary spans three axes, authoring a single token would leave a consumer
unable to tell whether the remaining axes are inapplicable or merely unauthored.

Each state value maps to exactly one affordance, so a flat state list is unambiguous without
keying: a door authored `["closed", "locked"]` is unambiguous because `closed` can only belong to
`openable` and `locked` only to `lockable`.

### Naming conventions

- Affordance tokens use the `-able` form.
- The `accepts_` form marks affordances requiring a third participant beyond the agent and the
  labeled prim. `accepts_insertion` involves the agent, the socket, and the mating part.
- State tokens carry their affordance root where a natural form exists, as in `toggled_on` and
  `locked`. Labels are routinely flattened into dataset dumps and training label files where the
  instance name is lost, and a bare `on` is meaningless out of that context.

### Criteria for vocabulary additions

A candidate affordance token must satisfy all three:

1. **Grounded** — true in virtue of the object's own construction, not a particular agent.
   `graspable` fails: whether a handle can be grasped depends on the gripper.
2. **Effective** — performing the interaction produces a state change or effect. A cup can be
   pressed; nothing happens, so `pressable` does not apply to it.
3. **Discriminating** — it partitions the asset library. A token true of nearly every object carries
   no information.

A candidate state token must additionally satisfy:

4. **Persistent** — the value can hold with no agent present. This excludes transient descriptions
   of an interaction in progress.

### Scope exclusions

The following are outside this taxonomy regardless of whether they satisfy the criteria above.

**Gestures and manipulation techniques.** An affordance names the interaction an object offers, not
the technique an agent uses to perform it. `swipeable`, `pinchable`, `long_pressable`, `two_handed`,
and `power_grasp` are technique descriptions. Which technique is valid depends on the agent's
morphology and, for interactive displays, on application state that is not represented in the asset.
A touch-operable surface is labeled as such; whether a tap, a drag, or a long press is meaningful is
determined by the software running on it. That application state is out of scope, while the prim's
own actuation state is in scope.

**Implementation technology.** An affordance names what the object offers, not how it is built.
`capacitive`, `resistive`, `servo_driven`, and `spring_loaded` describe mechanism. Mechanism is
represented by the asset's physics and geometry.

**Object identity.** `door`, `drawer`, `button`, and `knob` are object or part categories, not
affordances. They belong to an identity taxonomy.

Quantitative properties — actuation force, travel distance, joint limits, and value ranges — are
numeric and cannot be expressed as tokens. They are deferred rather than excluded.

## Schema / OpenUSD Specification

Defined with the [`SemanticsLabelsAPI` schema](https://openusd.org/release/api/usd_semantics_overview.html), available in OpenUSD 24.11 and later — the same schema used by [Semantic Labels](../../semantic_labels/capability-semantic_labels.md).

## USDA Sample

```usd
def Xform "SlidingPatioDoor" (
    prepend apiSchemas = [
        "SemanticsLabelsAPI:affordance",
        "SemanticsLabelsAPI:affordance_state"
    ]
)
{
    token[] semantics:labels:affordance = ["openable", "slideable", "lockable"]
    token[] semantics:labels:affordance_state = ["closed", "locked"]
}
```

Further examples:

| Object | `affordance` | `affordance_state` |
| --- | --- | --- |
| Hinged door | `openable`, `rotatable`, `lockable` | `closed`, `locked` |
| Drawer | `openable`, `slideable` | `closed` |
| Doorbell | `pressable` | `unpressed` |
| Rocker light switch | `toggleable` | `toggled_off` |
| Latching push-button switch | `pressable`, `toggleable` | `unpressed`, `toggled_off` |
| Capacitive power button | `touch_operable`, `toggleable` | `untouched`, `toggled_off` |
| Volume knob | `rotatable`, `adjustable` | — |
| Socket | `accepts_insertion` | `empty` |

### Requirements

<!-- OBJECT_AFFORDANCES_REQUIREMENTS_LIST_START -->

```{requirements-table}
```

<!-- OBJECT_AFFORDANCES_REQUIREMENTS_LIST_END -->

```{toctree}
:maxdepth: 1
:hidden:

requirements
requirements/object-affordance-valid
requirements/object-affordance-state-valid
```

## Validation and delivery

AFF.001 and AFF.002 check composed authored values at default time and every authored
time sample. Generic semantic-label structure is supplied by
FET011_SemanticLabels.0-2-0. Profile adoption is deferred.

Five semantic fixtures in `tests/fixtures/object_affordances` illustrate the microwave
oven, light switch, filing cabinet, ball valve and padlock. They are validator fixtures,
not production assets or whole-profile qualification. Promotion of actual asset
samples remains subject to review and approval.

## References

- E. Şahin et al., "To afford or not to afford: A new formalization of affordances toward
  affordance-based robot control," *Adaptive Behavior*, 15(4), 2007.
- IEEE Std 1872.1-2024, *Robot Task Representation*. Agent-side capability and task representation,
  which this capability deliberately does not cover.
