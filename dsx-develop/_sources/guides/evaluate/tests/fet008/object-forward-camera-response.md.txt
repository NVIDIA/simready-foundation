# object_forward_camera_response (FET008 Object Forward)

| Property | Value |
|---|---|
| Test name | object_forward_camera_response |
| Feature(s) | `FET008_ObjectForward.0-1-0` |
| Engine | Kit / Isaac Sim (>=2024.2.0) |
| Test version | 1.0.1 |

## Summary

Changes facing on two temporary asset references and measures composed
front-camera poses after engine updates.

## What Pass Guarantees

The camera helper places each camera on the selected front side, looking
toward the reference origin. Both position and view errors are finite and
within `pose_tolerance` (default `1e-5`).

## What It Checks

With identity transforms, +X and +Y facing produce independently expected
camera positions and local -Z viewing directions. Y-up stages use +Z for
the second direction. Distance is positive and measured in composed stage
units (default `3.0`).

## How It Works

The loaded root must expose a valid direction. The test creates a unique
session-layer probe scope, references the source twice, clears their transform
orders, and overrides facing. It authors each camera with
`asset_frame.facing_camera_transform`, waits two configured settle cycles, measures its world
pose, and captures a frame. A finally block removes the probes.
Required capture/analysis errors propagate as incomplete execution, including
image `ValueError`; they are not converted to authored-asset failures. Invalid
authored facing remains a measured contract failure. Nonfinite pose observations
are unavailable evidence, not finite out-of-tolerance pose results.

Distance, tolerance and load timeout must be finite positive real controls
before loading a scene; booleans and numeric strings are not valid controls.
Probe removal must acknowledge success and leave no composed probe scope.
Failed required cleanup records worker-retirement evidence; an earlier runtime
error/cancellation is retained with a secondary cleanup note rather than replaced.

## How to Fix

Repair the camera helper or composition if the measured pose differs from
its identity-transform expectation. Supply finite positive camera distance
and pose tolerance. Facing parallel to stage up needs an explicit roll
convention and is rejected by the helper, while remaining valid under AF.001.

## Evidence

`object_forward_X_position_error`, `object_forward_X_view_error`, and the
corresponding `Other` metrics record numeric pose errors. The
`object_forward_camera_X` and `object_forward_camera_Other` captures show the
front-side views. This test does not judge the author's semantic front.

Run this test through `simready-evaluate` with the test selection
`object_forward_camera_response` in a configured Kit/Isaac engine.
