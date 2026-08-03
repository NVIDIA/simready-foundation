# SimReady Benchmark

This guide covers benchmarking with `simready-benchmark`. It explains how to plan
benchmarks, run them in the engine, stamp results on the asset, and read
reports. For concepts, test families, and how benchmarking relates to
[schema validation](../validate_workflow.md), start with Overview in the table
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

For verifying a `simready-benchmark` release, the command-line QA test plan
(every command, exit-code gating, and the list-tests against plan against report
consistency gate) lives in the `simready-explorer` repository at
`docs/qa-cli-test-plan.md`.
