# object-affordance-valid

| Code     | AFF.001 |
|----------|---------|
| Validator| ObjectAffordancesCapabilityChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

If `SemanticsLabelsAPI:affordance` is applied to a prim, every authored value in
`semantics:labels:affordance` must be one of the allowed affordance tokens.

## Description

`affordance` is a `SemanticsLabelsAPI` taxonomy instance describing the interactions an object
offers an agent, for example "this door is openable." Applying the schema is opt-in per-prim — a
prim is never required to carry this label. When it is applied, however, every authored token must
come from the closed vocabulary below, so that discovery and state-query tooling can rely on a
known, finite set of values instead of free text.

| Axis | Token | Meaning |
|------|-------|---------|
| Actuation | `pressable` | Momentary mechanical actuator with travel; returns to rest; produces an effect |
| Actuation | `touch_operable` | Contact actuates the control; no force or travel required |
| Actuation | `rotatable` | Angular motion about an axis |
| Actuation | `slideable` | Linear translation |
| Outcome | `openable` | Affords transition between open and closed |
| Outcome | `lockable` | Affords engaging a constraint that gates another affordance |
| Outcome | `accepts_insertion` | Affords receiving a mating part |
| State topology | `toggleable` | Two discrete states persisting after release |
| State topology | `adjustable` | Affords setting a continuous value |

Values are case-sensitive and must use the canonical lowercase spelling shown above. For example,
`lockable` is valid and `Lockable` is invalid.

The vocabulary spans three axes, and a prim is expected to carry every token that applies. A sliding
door is `["openable", "slideable"]` — the outcome and the actuation are both true of it, and
authoring only one leaves a consumer unable to tell whether the other axis is inapplicable or merely
unauthored. `AFF.001` accepts the nine tokens above and rejects any other value. It does not check
whether a matching joint, drive, controller, or state threshold exists, and it does not check
whether the set of authored tokens is complete. Those checks are outside the scope of this
requirement.

`SemanticsLabelsAPI:affordance` is the SimReady-controlled affordance taxonomy. Assets that need
additional or simulator-specific affordance values must author them in a separate
`SemanticsLabelsAPI` instance, such as `SemanticsLabelsAPI:affordance_company_a`. Multiple
instances may coexist on the same prim. `AFF.001` does not validate values authored in other
instances.

## Validation

Check composed values at default time and every authored time sample. Each invalid-token
diagnostic identifies the prim, property, token and sample time. Generic label structure
belongs to the Semantic Labels gate. A prim that has not applied this taxonomy is
outside this vocabulary check.

## Examples

```usd
# Valid: outcome, actuation, and constraint tokens all apply to this prim
def Xform "Door" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance"]
)
{
    token[] semantics:labels:affordance = ["openable", "rotatable", "lockable"]
}

# Valid: no affordance API applied at all (opt-in, not required)
def Xform "StaticShelf" {
}

# Valid: the SimReady and company-specific taxonomies coexist
def Xform "Valve" (
    prepend apiSchemas = [
        "SemanticsLabelsAPI:affordance",
        "SemanticsLabelsAPI:affordance_company_a"
    ]
)
{
    token[] semantics:labels:affordance = ["rotatable", "adjustable"]
    token[] semantics:labels:affordance_company_a = ["quarter_turn"]
}

# Invalid: "unlockable" is not in the allowed vocabulary
def Xform "Cabinet" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance"]
)
{
    token[] semantics:labels:affordance = ["openable", "unlockable"]
}

# Invalid: values are case-sensitive
def Xform "UppercaseCabinet" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance"]
)
{
    token[] semantics:labels:affordance = ["Lockable"]
}
```

## Why is it required?

- Keeps the affordance vocabulary closed and discoverable, so tooling can query for a named
  interaction without guessing at free-text values.
- Catches typos and ad-hoc values before they silently break downstream discovery and state-query
  consumers.
- Provides a stable interoperability baseline while allowing separate simulator-specific taxonomies.

## How to comply

1. Apply `SemanticsLabelsAPI:affordance` only to prims that offer an interaction intended for an
   external agent. Internal mechanisms carry joints but are not labeled.
2. Author `semantics:labels:affordance` using the canonical lowercase values from the allowed
   vocabulary above, including every token that applies across the three axes.
3. Author custom affordance values in a separate `SemanticsLabelsAPI` instance, such as
   `SemanticsLabelsAPI:affordance_company_a`.

## Related requirements

- [Object Affordance State Valid (AFF.002)](object-affordance-state-valid.md)
- [Semantic Label Capability (SL.001)](../../../semantic_labels/requirements/semantic-label-capability.md)
- [Joints and Articulations](../../physics_joints/capability-physics_joints.md)
- [Driven Joints](../../physics_driven_joints/capability-physics_driven_joints.md)
- [Base Articulation](../../base_articulation/capability-base-articulation.md)

## For More Information

- [Object Affordances Capability](../capability-object_affordances.md)
