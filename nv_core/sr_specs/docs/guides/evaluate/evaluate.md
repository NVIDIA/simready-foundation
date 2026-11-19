# SimReady Evaluate

This guide covers evaluating with `simready-evaluate`. It explains how to plan
runtime tests, run them in the engine, stamp results on the asset, and read
reports. For concepts, test families, and how evaluating relates to
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
Newton Runtime Tests <newton-tests/runtime-tests>
Sensor Tests Reference <sensor-tests/tests>
```

Use `simready-evaluate --list-tests` as the authoritative inventory for the
installed environment. The runtime-test references document procedures owned
by Core, Newton and Sensors; independently installed test packs can add more.
