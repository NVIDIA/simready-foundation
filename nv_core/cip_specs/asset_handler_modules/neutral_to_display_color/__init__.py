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
"""Feature adapters that derive display colour from an existing material.

Mirrors ``neutral_to_physx`` in shape, but the transition is between sibling
appearance contracts rather than physics runtimes: an asset that already
declares a material under ``FET_006_STANDARD``, ``FET_006_OPENPBR`` or
``FET_006_MDL`` gains the constant ``primvars:displayColor`` on every renderable
Gprim that ``FET_010_STANDARD`` requires. The shaded surfaces are not
touched; display colour is the appearance layer for a consumer that does not
evaluate materials, and it is added beside them.

The colour is derived from the bound material, so this adapter cannot conform an
asset that has no material to derive from. Those Gprims are reported and left
without a display colour rather than given an invented one, which means the
stage can still fail ``DISP.001`` after the adapter runs.

The adapter holds no derivation of its own. It is a declaration over the conform
skill's script, which is the single implementation of this derivation:

    skills/simready-foundation-conform-fet-010-standard/assets/scripts/author_display_color.py

That script owns the surface resolution order, the area-weighted texture
sampling, the linear-light decode, the DISP.002 range handling, and the rule that
a display colour it did not author is left alone. Running the skill by hand and
running this adapter therefore produce the same value.
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

# The derivation lives with the conform skill rather than here, so the adapter and
# the skill cannot drift apart. Four levels up from this module is the repository
# root: neutral_to_display_color -> asset_handler_modules -> cip_specs -> nv_core.
_SCRIPT_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "skills",
        "simready-foundation-conform-fet-010-standard",
        "assets",
        "scripts",
        "author_display_color.py",
    )
)

_authoring_module = None


def _authoring():
    """Load the conform skill's authoring script once, by path.

    The script is not an installed package and the skills tree is not on
    ``sys.path``, so it is loaded from its file location rather than imported by
    name. Failing loudly here is deliberate: an adapter that silently did
    nothing would report a clean upgrade for an asset it never touched.
    """
    global _authoring_module
    if _authoring_module is None:
        spec = importlib.util.spec_from_file_location(
            "simready_author_display_color", _SCRIPT_PATH
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load the display colour script at {_SCRIPT_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _authoring_module = module
    return _authoring_module


@feature_adapter(
    name="material_neutral_to_display_color",
    input_feature_id="FET_006_STANDARD",
    input_feature_version="0.1.0",
    output_feature_id="FET_010_STANDARD",
    output_feature_version="0.1.0",
)
def material_neutral_to_display_color(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _author_display_color(output_stage)


@feature_adapter(
    name="material_openpbr_to_display_color",
    input_feature_id="FET_006_OPENPBR",
    input_feature_version="0.1.0",
    output_feature_id="FET_010_STANDARD",
    output_feature_version="0.1.0",
)
def material_openpbr_to_display_color(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _author_display_color(output_stage)


@feature_adapter(
    name="material_mdl_to_display_color",
    input_feature_id="FET_006_MDL",
    input_feature_version="0.1.0",
    output_feature_id="FET_010_STANDARD",
    output_feature_version="0.1.0",
)
def material_mdl_to_display_color(input_stage: Usd.Stage, output_stage: Usd.Stage):
    _author_display_color(output_stage)


def _author_display_color(output_stage: Usd.Stage):
    """Author the display colour on every renderable Gprim of the output stage.

    All three entry points share one implementation because the script resolves
    whichever surface a material carries, in the order OpenPBR, UsdPreviewSurface,
    MDL. Declaring the three transitions separately keeps the adapter graph
    explicit about which input contracts have a known path to display colour.

    Texture sampling is requested, and it needs ``numpy`` and ``Pillow``. Install
    them. Without them the adapter does not fail, but on a texture-driven material
    it has only whatever constant the material authors beside its texture to fall
    back on, and where the material authors none there is nothing to derive from
    at all: the Gprim is logged as skipped and left without a display colour.

    That is the common case rather than the exception. Across the sample library
    every texture-driven material reaches its base colour through a
    ``UsdPreviewSurface`` whose ``diffuseColor`` is connected, with no
    ``inputs:fallback`` on the reader and no ``diffuse_color_constant`` on the MDL
    surface beside it. So a bare USD environment is not this adapter running at
    reduced fidelity on those assets; it is this adapter authoring nothing and
    saving nothing, and ``DISP.001`` still failing afterwards. The OpenPBR migration
    is the one path that writes such a constant, on the MaterialX reader's
    ``default`` input, and even there it is usually the nodedef default rather
    than a colour the material shows.
    """
    authored, skipped, conflicts, _per_material, notes = _authoring().author_stage(
        output_stage, sample_textures=True
    )
    logger.info(
        "Display colour adapter: %d Gprim(s) authored, %d skipped, %d conflict(s)",
        authored,
        skipped,
        conflicts,
    )
    # A skip is geometry with nothing to derive a colour from; a conflict is a
    # display colour somebody authored by hand. Both leave DISP.001 failing on that
    # prim, so surface them rather than reporting a silent success.
    if skipped or conflicts:
        for note in notes:
            if "SKIPPED" in note or "CONFLICT" in note:
                logger.warning("Display colour adapter: %s", note.strip())

    if authored:
        output_stage.Save()
