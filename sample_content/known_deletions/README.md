# Known sample asset deletions

## Purpose

Deleting a sample asset is a reviewed operation, not an incidental filesystem
change. Every asset intentionally removed from `sample_content/manifest.csv`
must have one TOML record in this directory.

`nv_core/sr_specs/tests/validate_sample_content.py` compares the current branch
with the default branch. When an asset from the default branch is absent from
the current manifest and validation results, the test passes only if a valid
record identifies the exact deleted asset path.

## Required format

Store one deletion per `*.toml` file directly in this directory:

```toml
[deletion]
asset_path = "sample_content/path/to/deleted/root.usd"
reason = "Why this asset was intentionally removed."
```

The filename is descriptive and does not participate in matching. Matching uses
the value of `deletion.asset_path`.

Both fields are required:

- `asset_path` must be a TOML string containing the exact repository-relative
  path formerly listed in `sample_content/manifest.csv`.
- `reason` must be a TOML string containing at least one non-whitespace
  character.

Additional fields, including an optional date, are ignored and do not gate a
deletion. Additional TOML files in nested directories are not loaded.

## Path rules

`asset_path` is well-formed only when all these conditions hold:

- it starts with `sample_content/`;
- it has no leading or trailing whitespace;
- it uses forward slashes, never backslashes;
- it is repository-relative, not an absolute or drive-qualified path;
- it contains no empty path components, including doubled slashes; and
- it contains no `.` or `..` path components.

For example:

```toml
asset_path = "sample_content/common_assets/props_general/example/simready_usd/example.usd"
```

Malformed path examples include:

```toml
asset_path = "C:/repo/sample_content/example.usd"        # absolute
asset_path = "sample_content\\example.usd"               # backslashes
asset_path = "sample_content/../outside/example.usd"     # traversal
asset_path = "sample_content//example.usd"               # empty component
asset_path = " sample_content/example.usd"               # surrounding whitespace
```

## Malformed records

The test rejects a record when:

- the file is not valid TOML;
- the `[deletion]` table is absent or is not a table;
- `asset_path` or `reason` is missing;
- a required field has the wrong TOML type;
- `asset_path` violates any path rule;
- `reason` is empty or whitespace-only; or
- another TOML record contains the same `asset_path`.

## Repository-state enforcement

A well-formed record must also agree with the current repository state:

- the asset must be absent from `sample_content/manifest.csv`;
- the asset path must not exist on disk; and
- a default-branch asset removed from the current manifest must have a matching
  record.

Therefore:

- deleting only the file still fails because the manifest entry remains;
- deleting the file and manifest row still fails without a TOML record;
- adding the TOML while the asset or manifest row remains still fails; and
- deleting the file and manifest row with a matching TOML record is accepted.

Remove the TOML record if the asset is restored.
