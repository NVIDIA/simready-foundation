# SimReady Benchmark

This guide covers benchmarking with `simready-benchmark`. It explains how to plan
benchmarks, run them in the engine, stamp results on the asset, and read
reports. For concepts, test families, and how benchmarking relates to
[schema validation](../validate_workflow.md), start with [Overview](overview.md) in the table
of contents below.

Read the pages below in order, or jump to [Running Tests](running.md) if you are already set up.

```{toctree}
:maxdepth: 2

Overview <overview>
Pipeline and Stages <pipeline>
Running Tests <running>
Reading Reports <reading-reports>
Tests Reference <tests/tests>
```

Use `simready-benchmark --list-tests` as the authoritative inventory for the
installed environment. The Foundation runtime-test reference documents the
tests shipped by this tier; independently installed test packs can add more.
