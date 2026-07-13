"""Test that only root USDs (those listed in
``com.nvidia.simready.root_usds.json``) are opened as stages by the
package validator.

The ``nested_usd_references`` fixture is a hand-rolled package with
three sublayered USDA files — ``root.usda`` -> ``child.usda`` ->
``grandchild.usda`` — and a ``root_usds.json`` that lists only
``root.usda`` as the entry point. A spy ``BaseRuleChecker`` is bolted
onto the same ``ValidationEngine`` ``validate_package`` builds and
records every ``CheckStage`` / ``CheckLayer`` invocation across the
full validation run. The test then asserts that:

* ``CheckLayer`` fires at most once per layer identifier — the engine
  must not re-open ``child.usda`` / ``grandchild.usda`` as separate
  stages (which would trigger a second ``CheckLayer`` round on those
  layers via the new stage's transitive walk).
* ``CheckStage`` fires only on layers declared in ``root_usds.json``.

Both assertions encode the contract from PKG.CONF.002
(``root-usds.md``): "When the file is present, validators MUST use
only the listed entries — no filesystem scanning."
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from omni.asset_validator import BaseRuleChecker

from sr_pkg_sample._validate_package import _build_validation_engine

PACKAGE_DEF_NAME = "com.nvidia.simready.packaging.json"
TESTDATA_DIR = Path(__file__).resolve().parent / "testdata"


class CheckStageLayerSpy(BaseRuleChecker):
    """Records every CheckStage / CheckLayer call across all rule instances.

    The asset-validator engine instantiates a fresh rule object per
    stage, so per-instance state would only show one stage's worth of
    calls. Class-level lists give the cross-stage view we need to
    detect duplicate ``CheckLayer`` invocations on the same layer.
    """

    stage_calls: ClassVar[list[str]] = []
    layer_calls: ClassVar[list[str]] = []

    def CheckStage(self, stage):
        type(self).stage_calls.append(stage.GetRootLayer().identifier)

    def CheckLayer(self, layer):
        type(self).layer_calls.append(layer.identifier)


def test_only_root_usds_are_validated_as_stages() -> None:
    pkg_def = (
        TESTDATA_DIR
        / "nested_usd_references"
        / "1.0.0"
        / PACKAGE_DEF_NAME
    )
    assert pkg_def.is_file(), f"Fixture missing: {pkg_def}"

    CheckStageLayerSpy.stage_calls.clear()
    CheckStageLayerSpy.layer_calls.clear()

    engine = _build_validation_engine("Package", "1.0.0")
    assert engine is not None, "Failed to build validation engine for the Package profile"
    engine.enable_rule(CheckStageLayerSpy)

    engine.validate(str(pkg_def))

    layer_calls = list(CheckStageLayerSpy.layer_calls)
    stage_calls = list(CheckStageLayerSpy.stage_calls)

    assert len(layer_calls) == len(set(layer_calls)), (
        "CheckLayer fired more than once for the same layer "
        f"(non-root USDs were opened as separate stages): {layer_calls}"
    )

    stage_basenames = {Path(p).name for p in stage_calls}
    assert stage_basenames == {"root.usda"}, (
        "CheckStage fired on USDs that are not declared as roots in "
        f"root_usds.json: {stage_calls}"
    )
