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
"""ASCII-safe overlay text helpers for articulation-phase viewport text.

Wraps simready_benchmark_engine_kit/text_3d.py. The v1-style API
(set_text_context/show_viewport_text/tick_viewport_text_transform/
hide_viewport_text/cleanup_viewport_text) does not exist in this repo;
instead this adapter delegates to the actual API:
create_3d_text, update_3d_text_transform, clear_3d_text, and
compute_screen_position (for screen-space placement). No extension of
text_3d was required. Overlay placement uses screen-space coordinates
so the text tracks the active camera.
"""


OVERLAY_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _.:+-\n")

# Default screen-space placement for articulation-phase overlays.
# Centered horizontally, upper portion of viewport, a couple of units
# in front of the camera. Kept local so callers don't need to know.
_DEFAULT_SCREEN_X = 0.0
_DEFAULT_SCREEN_Y = 0.7
_DEFAULT_SCREEN_DISTANCE = 2.0

# Cache of the most recent screen-space configuration so update calls can
# recompute the world position without the caller having to repeat it.
_last_screen_x = _DEFAULT_SCREEN_X  # type: float
_last_screen_y = _DEFAULT_SCREEN_Y  # type: float
_last_screen_distance = _DEFAULT_SCREEN_DISTANCE  # type: float


def overlay_safe_text(text):
    # type: (Optional[str]) -> str
    """Return text uppercased with disallowed characters replaced by space."""
    up = (text or "").upper()
    return "".join((c if c in OVERLAY_ALLOWED else " ") for c in up)


def show_overlay(stage, camera_path, text, color=(1.0, 1.0, 1.0), scale=0.15):
    # type: (Any, Optional[str], str, Tuple[float, float, float], float) -> None
    """Show viewport text using simready_benchmark_engine_kit.text_3d (lazy import).

    Overlay is non-fatal: any exception from text_3d is swallowed.
    """
    safe = overlay_safe_text(text)
    try:
        from simready_benchmark_engine_kit import text_3d
    except Exception:
        return
    try:
        position = text_3d.compute_screen_position(
            stage,
            screen_x=_last_screen_x,
            screen_y=_last_screen_y,
            distance=_last_screen_distance,
            camera_path=camera_path,
        )
        if position is None:
            return
        text_3d.create_3d_text(
            stage,
            safe,
            position,
            scale=scale,
            color=color,
            billboard=True,
            camera_path=camera_path,
            always_on_top=True,
        )
    except Exception:
        pass


def update_overlay_transform(stage, camera_path):
    # type: (Any, Optional[str]) -> None
    """Tick the overlay transform so it follows the active camera."""
    try:
        from simready_benchmark_engine_kit import text_3d
    except Exception:
        return
    try:
        position = text_3d.compute_screen_position(
            stage,
            screen_x=_last_screen_x,
            screen_y=_last_screen_y,
            distance=_last_screen_distance,
            camera_path=camera_path,
        )
        if position is None:
            return
        text_3d.update_3d_text_transform(
            stage,
            position,
            billboard=True,
            camera_path=camera_path,
        )
    except Exception:
        pass


def hide_overlay(stage=None):
    # type: (Any) -> None
    """Remove the overlay geometry from the stage (non-fatal)."""
    if stage is None:
        return
    try:
        from simready_benchmark_engine_kit import text_3d
    except Exception:
        return
    try:
        text_3d.clear_3d_text(stage)
    except Exception:
        pass


def cleanup_overlay(stage=None):
    # type: (Any) -> None
    """Alias for hide_overlay; reserved for future per-session cleanup."""
    hide_overlay(stage)
