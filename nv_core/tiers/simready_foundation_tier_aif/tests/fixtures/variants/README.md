# Negative fixtures

Each fixture is named for one requirement and violates it. Other requirements fail on it too -- the metadata variants carry no connection points, so CP, TC and EL fail alongside the one under test -- and the suite asserts only the named one. All 19 AIF requirements have at least one fixture. Do not author from these.

- **Add one** — copy an entry point and its `*_Properties.usda` or `*_ConnectionPoints.usd` sublayer, introduce a single violation, then map the path to the requirement code in `NEGATIVE_FIXTURES` in [test_aif.py](../../test_aif.py).
- **Default prim** — `TestCDU` where the fixture has equipment metadata, `TestAsset` where it has connection points alone.
- **Positives** — `cp_pass_complete.usda` uses all nine CP.004 type prefixes and three vendor prefixes, more than any equipment class requires. The v0.2.0 positives are [`Synthetic_CP2_*`](../synthetic), one per connection point domain.
- Sublayer references are local to this directory.
