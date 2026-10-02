# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Feature adapters that add the OpenPBR final surface to an existing material.

Mirrors ``neutral_to_physx`` in shape, but the transition is between sibling
appearance contracts rather than physics runtimes: an asset that already
declares a material under ``FET_006_STANDARD`` (UsdPreviewSurface preview) or
``FET_006_MDL`` (OmniPBR / OmniGlass final surface) gains the OpenPBR final
surface on ``outputs:mtlx:surface`` that ``FET_006_OPENPBR`` requires. Nothing
is removed: the preview and MDL surfaces stay exactly as they were, because
they are separate contracts an asset may hold at the same time.

The adapter holds no derivation of its own. It is a declaration over the
conform skill's script, which is the single implementation of this migration:

    skills/simready-foundation-conform-fet-006-openpbr/assets/scripts/migrate_to_openpbr.py

That script owns the parameter mapping, the VM.PBR.002 range clamping, the
MaterialX reader topology, and the rule that a hand-authored OpenPBR surface is
left alone. Running the skill by hand and running this adapter therefore
produce the same result, which is the point: the adapter is the known code path
between the two feature versions, and the skill is the same code with a person
driving it.
"""

import importlib.util
import logging
import os
import sys

from omni.cip.configurable.feature_adapter import feature_adapter
from pxr import Usd

# Add the root directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logger = logging.getLogger(__name__)

# The migration lives with the conform skill rather than here, so the adapter and
# the skill cannot drift apart. Four levels up from this module is the repository
# root: neutral_to_openpbr -> asset_handler_modules -> cip_specs -> nv_core.
_SCRIPT_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "skills",
        "simready-foundation-conform-fet-006-openpbr",
        "assets",
        "scripts",
        "migrate_to_openpbr.py",
    )
)

_migration_module = None


def _migration():
    """Load the conform skill's migration script once, by path.

    The script is not an installed package and the skills tree is not on
    ``sys.path``, so it is loaded from its file location rather than imported by
    name. Failing loudly here is deliberate: an adapter that silently did
    nothing would report a clean upgrade for an asset it never touched.
    """
    global _migration_module
    if _migration_module is None:
        spec = importlib.util.spec_from_file_location(
            "simready_migrate_to_openpbr", _SCRIPT_PATH
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the OpenPBR migration script at {_SCRIPT_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _migration_module = module
    return _migration_module


@feature_adapter(
    name="material_neutral_to_openpbr",
    input_feature_id="FET_006_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_006_OPENPBR",
    output_feature_version="0.1.0",
)
def material_neutral_to_openpbr(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _author_openpbr(output_stage)


@feature_adapter(
    name="material_mdl_to_openpbr",
    input_feature_id="FET_006_MDL",
    input_feature_version="0.1.0",
    output_feature_id="FET_006_OPENPBR",
    output_feature_version="0.1.0",
)
def material_mdl_to_openpbr(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _author_openpbr(output_stage)


def _author_openpbr(output_stage: Usd.Stage):
    """Author the OpenPBR surface on every material of the output stage.

    Both entry points share one implementation because the script reads whichever
    source surface a material carries: an OmniPBR or OmniGlass MDL shader where
    there is one, the UsdPreviewSurface preview otherwise. Declaring the two
    transitions separately keeps the adapter graph explicit about which input
    contracts have a known path to OpenPBR.
    """
    migrated, skipped, conflicts, wired, flattened, notes = _migration().migrate_stage(
        output_stage, wire_textures=True
    )
    logger.info(
        "OpenPBR adapter: %d material(s) migrated, %d skipped, %d conflict(s), "
        "%d texture(s) wired, %d flattened",
        migrated,
        skipped,
        conflicts,
        wired,
        flattened,
    )
    # A conflict is a material carrying a hand-authored OpenPBR surface. The script
    # leaves those alone by design, so the stage can still fail FET_006_OPENPBR
    # after the adapter runs. Surface it rather than reporting a silent success.
    if conflicts:
        for note in notes:
            if "CONFLICT" in note:
                logger.warning("OpenPBR adapter: %s", note.strip())

    if migrated:
        output_stage.Save()
