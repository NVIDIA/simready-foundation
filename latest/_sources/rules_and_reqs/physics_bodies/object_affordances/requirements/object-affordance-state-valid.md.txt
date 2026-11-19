# object-affordance-state-valid

| Code     | AFF.002 |
|----------|---------|
| Validator| ObjectAffordancesCapabilityChecker |
| Compatibility | {compatibility}`Open USD` |
| Tags     | {tag}`correctness` |

## Summary

If `SemanticsLabelsAPI:affordance_state` is applied to a prim, every authored value in
`semantics:labels:affordance_state` must be one of the allowed state tokens.

## Description

`affordance_state` is a `SemanticsLabelsAPI` taxonomy instance describing the current qualitative
condition of an interaction-bearing prim, for example "this door is closed." Applying the schema is
opt-in per-prim. When it is applied, every authored token must come from the closed vocabulary
below.

| Token | Belongs to | Meaning |
|-------|-----------|---------|
| `open` | `openable` | Aperture traversable |
| `closed` | `openable` | Aperture not traversable |
| `toggled_on` | `toggleable` | Active state |
| `toggled_off` | `toggleable` | Inactive state |
| `locked` | `lockable` | Constraint engaged |
| `unlocked` | `lockable` | Constraint released |
| `empty` | `accepts_insertion` | No mating part present |
| `occupied` | `accepts_insertion` | Mating part present |
| `pressed` | `pressable` | Actuation threshold crossed |
| `unpressed` | `pressable` | Actuation threshold not crossed |
| `touched` | `touch_operable` | Contact registered as actuation |
| `untouched` | `touch_operable` | Contact not registered as actuation |

Values are case-sensitive and must use the canonical lowercase spelling shown above.

Each state token belongs to exactly one affordance, so a flat list is unambiguous without keying.
A door authored `["closed", "locked"]` is unambiguous because `closed` can only belong to `openable`
and `locked` only to `lockable`.

`pressed` and `touched` assert that the actuation threshold has been crossed, not that the actuator
is displaced or that contact occurred. A key can be partially depressed and not `pressed`. Defined
this way, both values carry information that joint position and collision detection do not.

The authored value is the prim's initial state. Runtimes may update it, and consumers must not
assume the authored value reflects current state once simulation has begun. `AFF.002` validates
authored values. It does not check that a state token's corresponding affordance is also authored,
and it does not check the state against the asset's physics. Those checks are outside the scope of
this requirement.

`rotatable` and `slideable` have no state values of their own; the state belongs to the outcome they
serve. `adjustable` resolves to a continuous value, which cannot be expressed as a token.

## Validation

Check composed values at default time and every authored time sample. Each invalid-token
diagnostic identifies the prim, property, token and sample time. Generic label structure
belongs to the Semantic Labels gate. A prim that has not applied this taxonomy is
outside this vocabulary check.

## Examples

```usd
# Valid: both tokens are in the allowed vocabulary and belong to authored affordances
def Xform "Door" (
    prepend apiSchemas = [
        "SemanticsLabelsAPI:affordance",
        "SemanticsLabelsAPI:affordance_state"
    ]
)
{
    token[] semantics:labels:affordance = ["openable", "rotatable", "lockable"]
    token[] semantics:labels:affordance_state = ["closed", "locked"]
}

# Valid: no state API applied at all (opt-in, not required)
def Xform "Doorbell" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance"]
)
{
    token[] semantics:labels:affordance = ["pressable"]
}

# Invalid: "half_open" is not in the allowed vocabulary
def Xform "Cabinet" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance_state"]
)
{
    token[] semantics:labels:affordance_state = ["half_open"]
}

# Invalid: values are case-sensitive
def Xform "UppercaseCabinet" (
    prepend apiSchemas = ["SemanticsLabelsAPI:affordance_state"]
)
{
    token[] semantics:labels:affordance_state = ["Closed"]
}
```

## Why is it required?

- Keeps the state vocabulary closed, so consumers can branch on a known, finite set of values.
- Preserves the one-token-one-affordance property that lets a flat state list be read without
  keying each value to its affordance.
- Catches typos and ad-hoc values before they silently break downstream consumers.

## How to comply

1. Author `semantics:labels:affordance_state` using the canonical lowercase values from the allowed
   vocabulary above.
2. Author a state value only for an affordance the prim actually offers.
3. Author custom state values in a separate `SemanticsLabelsAPI` instance, such as
   `SemanticsLabelsAPI:affordance_state_company_a`.

## Related requirements

- [Object Affordance Valid (AFF.001)](object-affordance-valid.md)
- [Semantic Label Capability (SL.001)](../../../semantic_labels/requirements/semantic-label-capability.md)

## For More Information

- [Object Affordances Capability](../capability-object_affordances.md)
