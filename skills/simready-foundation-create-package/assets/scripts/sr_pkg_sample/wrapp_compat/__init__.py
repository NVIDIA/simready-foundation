"""WRAPP 2.2 compatibility shims.

Everything in this sub-package works around features that are missing
from WRAPP 2.2 and will be absorbed into WRAPP 2.3:

* ``std_pkg_def`` — backport of ``wrapp std-pkg-def`` (package
  definition + BOM generation).
* ``catalog_patch`` — post-hoc patching of the ``.wrapp`` catalog so
  metadata JSONs ride along in ``wrapp export`` / ``wrapp install``.
* ``checks`` — pre- and post-flight source-folder checks
  (mismatched ``.wrapp`` markers, nested subpackages).
* ``create_and_emit`` — the WRAPP create + metadata-emit
  orchestration that WRAPP 2.3 would perform natively.
"""
