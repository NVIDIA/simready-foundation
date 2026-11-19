# ground_stability (FET003 Physics)

| Property | Value |
|---|---|
| Test name | ground_stability |
| Feature(s) | `FET003_RigidBody.0-1-0`, `FET003_RigidBody.0-2-0`, `FET003_RigidBody.PhysX.0-1-0`, `FET003_RigidBody.PhysX.0-2-0`, `FET003_RigidBody.PhysX.0-3-0`, `FET003_RigidBody.PhysX.0-4-0` |
| Engine | Kit / Isaac Sim (>=2024.2.0) |
| Test version | 3.0.2 |
| Wall-clock timeout | 600 seconds |

## Summary

Independently evaluates sampled settling after a flat-floor drop using PhysX.
The existing published binding is retained. Newton owns its separate
`ground_stability_newton` implementation; this page is not Newton policy.

## What Pass Guarantees

After bounding-box proximity, the required live samples met the configured
center-distance and corner-coordinate variation limits over a complete hold
window before the deadline, without exceeding the allowed floor overlap.
This is sampled geometric rest, not measured linear/angular velocity, exact
collision contact, continuous stability or proof of physical realism.
A flat height curve alone cannot establish this result.

## What It Checks

- Minimum box Z crosses `floor_level + floor_margin` from above.
- Subsequent evaluated box Z stays above `floor_level - floor_margin`.
- In a complete post-proximity hold window, every center's Euclidean distance
  to the latest center and every box-corner coordinate's absolute variation
  relative to the latest corners are at most `rest_tolerance`.
- At least two samples establish the window. The deadline is evaluated before
  any recording tail; late settling cannot turn a failure into PASS.
- Every sample in that full window must remain in the existing floor-proximity/
  allowed-overlap band. A flat midair window after an earlier proximity crossing
  cannot qualify rest. A return to the floor needs a fresh complete eligible hold.

Overlap checks remain active in the recording tail and can still invalidate a
result. Only rest/deadline acceptance freezes; later settling cannot rescue it.

## How It Works

Uses the same placement, live bounds, floor and follow-camera policy as
[ground_drop](ground-drop.md), but independently owns its settling verdict.
The floor has a typed physics material with static friction 0.5, dynamic 0.4
and restitution 0. No source asset or collider settings are repaired by this test.
Default rates are 240 Hz physics, capture every 16 observed steps, 15 fps
encoded video. Render retries/warmup can add uncounted ticks; graph time is
nominal requested-step time, not an exact video timestamp.

| Setting | Default | Meaning |
|---|---|---|
| floor_margin | 0.1 | Stage-length proximity and allowed box overlap |
| rest_tolerance | 0.02 | Stage-length center/corner variation allowance |
| penetration_check_seconds | 1.0 | Nominal delay before evaluating rest |
| rest_detection_hold_seconds | 2.0 | Complete sampled hold window |
| rest_detection_max_seconds | 8.0 | Nominal deadline after proximity |
| simulation_seconds | 10.0 | Hard nominal step budget |
| simulate_after_result_seconds | 0.5 | Recording-only nominal tail |

Lengths are stage units, not automatically metres. Configuration must be finite
and correctly typed. A meaningful hold requires positive duration and at least
two samples. A budget unable to evaluate the complete required window leaves
execution incomplete; it cannot prove that the asset would not settle.
The historical world-fixed precheck still skips. Positive Not applicable
evidence additionally requires the complete owned rigid-body anchoring proof
described by [ground_drop](ground-drop.md); a pinned body beside a disconnected
free body is insufficient. Unqualified proof remains Could not assess, not PASS.
Required setup, live readback or
cleanup errors retain their cause and leave execution incomplete.

## Failure Cases

Missing proximity, excessive box overlap, or no qualified sampled rest by the
deadline fail this procedure. A drop PASS with a stability FAIL is consistent:
the rigid-body feature still fails its required stability obligation.

## How to Fix

Inspect the video, complete-window variation curves, phase/deadline, configured
tolerances, stage scale and engine logs. Separate fixture/readback limitations
from a measured response failure before attributing an asset defect. Repair only
a demonstrated contract violation; do not widen tolerances to force success.

## Evidence

The independent result includes settling timing and bounded `ground_stability`
motion JSON/CSV when recording succeeds. Nullable center/corner window channels
are unknown until a complete hold exists, not zero variation. Complete low-
variation curves can still fail floor-band eligibility; compare the height/proxy
plot and recorded qualification metadata. Capture ticks
associate successful captures with preceding observations, not encoded frame
indices. Optional diagnostic failures never change the verdict.
Version 3.0.0 replaces the disabled legacy experiment with this qualified
procedure. Older combined `ground_drop` versions included settling in their
own verdict and must not be compared as if their acceptance were identical.
