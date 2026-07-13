# package\_sample tests

Integration tests for the `sr_pkg_sample` packaging workflow.

## Running

Activate the venv created by `setup_venv.sh`, then from this
directory:

```bash
pytest -v
```

## Layout

* **`conftest.py`** — session-scoped engine initialisation (Kit shim +
  `simready.validate.initialize`), shared fixtures (`sample_source`,
  `sample_source_copy`, `foundations_dir`, etc.).
* **`testdata/`** — hand-crafted packaging fixtures used by
  `test_packaging_validators.py`.
