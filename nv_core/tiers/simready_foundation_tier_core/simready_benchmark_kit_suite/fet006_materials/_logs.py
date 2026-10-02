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
"""What the render cannot show: a material that is bound and does not evaluate.

Coverage measures which pixels resolve a material of the asset's own. A shader
that fails to resolve still wins over the weakly bound control, so it counts as
covered and the number says nothing about it. The pixels cannot separate the two
cases -- a failed material draws a solid object in the renderer's own colour, and
so does a red asset.

Kit reports it instead. With ``/persistent/app/material/materialx/validate`` on,
the MaterialX plugin logs an error per material whose document it could not
create, naming the prim and the reason::

    [Error] [rtx.materialx.plugin] Unable to create document for material:
    '/World/AssetRoot/Asset/Looks/Chrome'

Without the setting Kit logs nothing at all for that material -- measured across
273 warnings on a material naming a nodedef that does not exist. It is a
``/persistent`` setting read at startup, so no test can switch it on; it belongs
to how the runner launches Kit. ``validation_enabled`` reads it back so a run
that did not have it reports "not checked" instead of a clean bill.

MaterialX only. There is no equivalent switch for MDL or for UsdPreviewSurface,
so those two contexts have no such report to read.
"""

import re

MATERIALX_VALIDATE_SETTING = "/persistent/app/material/materialx/validate"

MATERIALX_CHANNEL = "rtx.materialx.plugin"

# The message the plugin emits per material it could not build a document for.
_UNRESOLVED = re.compile(
    r"Unable to create document for material:\s*'([^']+)'", re.IGNORECASE)


def validation_enabled():
    """Whether Kit was launched with MaterialX document validation on.

    ``None`` when the setting cannot be read at all, which is what running
    outside Kit looks like, and is reported differently from ``False``.
    """
    try:
        import carb.settings
    except ImportError:
        return None
    value = carb.settings.get_settings().get(MATERIALX_VALIDATE_SETTING)
    if value is None:
        return False
    return bool(value)


def _entries():
    """The live monitor's captured Kit log entries, or an empty list."""
    try:
        from simready_benchmark_engine_kit.kit_log_monitor import KitLogMonitor
    except ImportError:
        return []
    monitor = KitLogMonitor.get_current()
    if monitor is None:
        return []
    try:
        return monitor.get_entries()
    except Exception:                             # noqa: BLE001 - diagnostics only
        return []


def unresolved_materials(root=None, entries=None):
    """Prim paths whose MaterialX document Kit could not create.

    Scoped to ``root`` when given. The control material this family binds is
    itself an OpenPBR network, and the room the scene builds has its own
    material; neither is the asset under test, and a failure in either is a
    fault in the rig rather than in the content.
    """
    found = []
    for entry in entries if entries is not None else _entries():
        if str(entry.get("channel", "") or "") != MATERIALX_CHANNEL:
            continue
        if str(entry.get("level", "") or "") not in ("error", "fatal"):
            continue
        match = _UNRESOLVED.search(str(entry.get("message", "") or ""))
        if not match:
            continue
        path = match.group(1)
        if root and not (path == root or path.startswith(root.rstrip("/") + "/")):
            continue
        if path not in found:
            found.append(path)
    return found
