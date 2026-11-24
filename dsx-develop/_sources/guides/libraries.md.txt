# SimReady Python Libraries

SimReady ships a family of Python libraries. Each one does a single job in the
asset pipeline: find an asset, fetch it, check it, package it, or render its
thumbnail. You can use any of them on their own. They all read the same
profiles and requirements from the Foundation tiers you install, so they agree
on what a valid asset looks like.

This page is a map of the family. For the full reference for one library, read
its page on PyPI or the `docs/` folder inside its wheel.

To install the tiers themselves, refer to
[SimReady Foundation PyPI Packages](foundation_pypi.md).

## The libraries

| Library | What it does | Command |
| --- | --- | --- |
| `simready.search` | Finds assets that match filters you set | none, library only |
| `simready.retrieve` | Downloads an asset and prepares it for use | `simready-retrieve`, `simready-derive` |
| `simready.validate` | Checks an asset against a profile | `simready-validate` |
| `simready.package` | Builds a package and records where it came from | `simready-package` |
| `simready.evaluate` | Runs an asset in an engine and reports how it behaved | `simready-evaluate` |
| `simready.thumbnail` | Renders an asset thumbnail | `simready-thumbnail` |
| `simready.manage` | Drives the review and publish pipeline | `simready-manage` |

## Install

Use Python 3.12. Most of these libraries require it, and `simready.evaluate`
requires exactly 3.12.

Five of them install from public PyPI:

```bash
pip install simready.search
```

Install `simready.retrieve` from your configured package source:

```bash
pip install simready.retrieve
```

Check the available versions on your configured indexes when matching a
specific release. Check what you have with `pip show <library>`.

## Find assets

`simready.search` loads a project's asset metadata and returns the assets that
match your filters. It has no command line; you call it from Python.

Build an `AssetLibrary`, add one or more sources, then search:

```python
import asyncio

from simready.search import AssetLibrary, SearchFilterClass, SearchFilterHeight


async def main():
    library = AssetLibrary()
    await library.add_cache_source("project_config.toml")

    matches = library.search(
        include_all=[SearchFilterClass("prop"), SearchFilterHeight(minimum=1.0)],
    )
    for asset in matches:
        print(asset.asset_path)


asyncio.run(main())
```

There are twelve filters. You can combine them four ways: `include_all`,
`include_any`, `exclude_all`, and `exclude_any`. Cache, S3, and indexed sources
are added with `await`. Service sources are not.

An indexed source finds file paths only. `SearchFilterPathContains` is the one
filter that matches an asset added that way.

## Download assets

`simready.retrieve` downloads an asset from OmniStorage, Hugging Face, or S3.
It picks the backend from the URI scheme, so you pass one address and it works
out the rest:

```bash
simready-retrieve fetch <uri>
```

From Python, `fetch` returns the local path:

```python
import asyncio

from simready.retrieve import fetch

path = asyncio.run(fetch("<uri>"))
```

Retrieve looks for a bill of materials inside the asset and downloads only the
files it lists. If the asset has no bill of materials, Retrieve downloads the
whole folder.

The same wheel ships `simready.derive` and its `simready-derive` command, which
prepares a downloaded asset for a target runtime.

## Package assets

`simready.package` builds a package from an asset and records what went into
it.

There are two different packaging libraries with the same name, and they do not
share an API:

- The **2026.10 line** is a workspace library. It builds around a read-only
  package space and a writable install space.
- The **earlier line** is the `Packager` API, with pre-validation and
  post-validation steps and WRAPP publishing. Public PyPI still serves this
  one.

Check which one you have before you write code against it:

```bash
pip show simready.package
```

## Evaluate assets

`simready.evaluate` runs an asset in an engine and reports how it behaved. Use
it when a static check cannot answer the question, such as whether a gripper
can actually hold a prop.

```bash
simready-evaluate --help
```

The engine runs through a separate package. Install it with the `kit` extra:

```bash
pip install "simready.evaluate[kit]"
```

This library was renamed from `benchmark`. The older name is still in use in
places you will see:

- Public PyPI publishes the earlier version as `simready-benchmark`.
- A test pack still declares itself in a file named `benchmark-provider.json`.
  That filename is current, not deprecated.

Do not hand-edit generated plans, result files, or reports.

## Render thumbnails

`simready.thumbnail` renders the thumbnail an asset needs to satisfy the
`SR.002` requirement. The command takes no subcommands:

```bash
simready-thumbnail --help
```

For what makes a good thumbnail, refer to
[Thumbnail Guidelines](thumbnail_guidelines.md).

## Manage the pipeline

`simready.manage` drives assets through review and publishing without Kit. It
is the most workflow-specific library here, and it depends on the earlier
packaging line rather than the 2026.10 one.

```bash
simready-manage --help
```

When you submit an asset, let it run its evaluation. Quality review treats a
missing evaluation result as a failure. A result that ran and failed still
counts as present; one that never ran does not.

## Validate assets

`simready.validate` checks an asset against a profile and reports which
requirements it missed. It is the library the other tools call when they need a
verdict.

```bash
simready-validate --profile Robotics-Prop --version 3.2.0 asset.usd
```

Refer to [SimReady Validation Workflow](validate_workflow.md) for the full
workflow, and to
[SimReady Foundation PyPI Packages](foundation_pypi.md) for installing the
tiers that supply the profiles.
