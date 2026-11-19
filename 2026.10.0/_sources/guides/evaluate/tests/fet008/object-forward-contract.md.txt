# object_forward_contract (FET008 Object Forward)

| Property | Value |
|---|---|
| Test name | object_forward_contract |
| Feature(s) | `FET008_ObjectForward.0-1-0` |
| Engine | Kit / Isaac Sim (>=2024.2.0) |
| Test version | 1.0.0 |

## Summary

Queries explicit local facing on the loaded asset root and authored components.

## What Pass Guarantees

Composition preserves the authored facing locations and direction values
within a vector difference of `1e-4`.

## What It Checks

The source and loaded asset must have valid roots and readable facing values.
Their root-relative paths and vectors must match. AF.001 is the static
requirement; this test proves the same data remains available at runtime.

## How It Works

The test reads source directions, loads the asset, traverses its composed
root including instance proxies, and compares the two maps. It records local
vectors, frames the asset, waits two configured settle cycles, and captures a still.

## How to Fix

Author valid explicit directions under AF.001 and repair references or
composition opinions that remove or override them. Confirm semantic front
with author review.

## Evidence

The `object_forward_local_vectors` metric records the composed directions.
The `object_forward_contract` capture shows the loaded asset.

Run this test through `simready-evaluate` with the test selection
`object_forward_contract` in a configured Kit/Isaac engine.
