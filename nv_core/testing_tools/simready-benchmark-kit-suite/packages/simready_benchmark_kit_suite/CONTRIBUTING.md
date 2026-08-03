# Contributing to simready-benchmark-kit-suite

This document captures conventions for authoring tests in this suite.
Framework-level conventions (the `@test` decorator API, async semantics,
`ctx` API) live in the `simready-benchmark` framework's documentation.

## Authoring `description` and `expected_video`

Every `@test(...)` call requires two plain-text metadata fields:

- **`description`** — one paragraph describing what the test verifies, in
  present tense, from an asset-author POV. Mention the headline metric
  and the failure threshold (or the configurable that controls it). Aim
  for ~150–250 characters.
- **`expected_video`** — one paragraph describing what a passing run
  looks like in the captured video — specific visual cues a reviewer
  should look for. Aim for ~150–300 characters.

Both surface in the per-test `result.json` and as side-by-side panels in
the HTML report above the metrics table.

### Examples — good

```python
description=(
    "Drives each non-passive, non-mimic-follower joint to its commanded "
    "position; verifies measured velocity stays within the authored "
    "physxJoint:maxJointVelocity (with a tolerance configurable as "
    "velocity_tolerance_percent, default 20%)."
),
expected_video=(
    "Each tested joint moves one at a time, accelerating from rest, "
    "plateauing at its max velocity, then decelerating back. Only one "
    "joint moves per segment. The robot base stays fixed (carrier holds "
    "it). On a passing run, no joint visibly snaps or jumps."
),
```

### Examples — bad

- `description="Tests velocity."` — too short, no signal.
- `description="Validates correctness of velocity-limit enforcement on driven articulation joints across the full range of motion under various test configurations."` — too verbose, no specifics, no metric mentioned.
- `expected_video="Joints move."` — useless to a reviewer.
- `expected_video="Various transitional states are visible during the test sequence."` — vague, helps no one.

### Style rules

1. **Present tense, asset-author POV.** *"Drives each joint…"*, not *"Will drive each joint…"* or *"This test drives…"*.
2. **Mention the headline metric in the description.** *"…within physxJoint:maxJointVelocity"* — not *"…within velocity limits"*.
3. **Mention the configurable that controls the failure threshold.** *"…with a tolerance configurable as velocity_tolerance_percent."*
4. **Pin specific visual cues in expected_video.** *"velocity-bar overlay never crosses the red max-velocity line"* — not *"video looks correct"*.
5. **Plain text only.** No markdown, HTML, or rich formatting; the report renders the strings as paragraph text and HTML-escapes them.
6. **Both fields are required.** The decorator raises `TypeError` at registration time if either is missing or empty after `.strip()`. There is no opt-out.
