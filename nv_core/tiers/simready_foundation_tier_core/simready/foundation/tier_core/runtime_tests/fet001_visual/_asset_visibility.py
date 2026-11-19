# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Require diagnostic pixels attributable to the loaded asset, not the room."""

from ..articulation_phases.error_utils import record_required_cleanup_failure

DIAGNOSTIC_COLOR = (0.9, 0.2, 0.0)
MIN_VISIBILITY_PIXELS = 100
PIXEL_CHANGE_THRESHOLD = 0.02
LUMA_MIN = 0.05
LUMA_MAX = 0.90


def asset_diagnostic_pixel_count(visible_path, hidden_path, expected_color=DIAGNOSTIC_COLOR):
    """Count diagnostic-colored pixels that disappear when the asset is hidden."""
    import numpy as np
    from PIL import Image

    with Image.open(visible_path) as image:
        visible = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    with Image.open(hidden_path) as image:
        hidden = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    if visible.shape != hidden.shape or visible.ndim != 3 or visible.shape[2] != 3:
        raise RuntimeError("Required asset visibility captures have incompatible dimensions")

    dominant = max(range(3), key=lambda channel: expected_color[channel])
    others = [channel for channel in range(3) if channel != dominant]
    luma = 0.299 * visible[:, :, 0] + 0.587 * visible[:, :, 1] + 0.114 * visible[:, :, 2]
    diagnostic = (
        (luma > LUMA_MIN)
        & (luma < LUMA_MAX)
        & (visible[:, :, dominant] > visible[:, :, others[0]])
        & (visible[:, :, dominant] > visible[:, :, others[1]])
    )
    changed = np.mean(np.abs(visible - hidden), axis=2) > PIXEL_CHANGE_THRESHOLD
    return int(np.count_nonzero(diagnostic & changed))


async def ensure_asset_visible(ctx, *, padding, min_pixels=MIN_VISIBILITY_PIXELS):
    """Frame the scene, then compare current and asset-hidden captures."""
    if not await ctx.ensure_object_framed(diagnostic_color=DIAGNOSTIC_COLOR, padding=padding):
        return False
    visible = await ctx.capture_frame(label="asset_visibility_visible", allow_blank=True)
    primary = None
    try:
        ctx.scene.hide_asset()
        await ctx.settle()
        hidden = await ctx.capture_frame(label="asset_visibility_hidden", allow_blank=True)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            ctx.scene.show_asset()
            await ctx.settle()
        except BaseException as cleanup_error:
            record_required_cleanup_failure(
                ctx,
                "Required asset visibility restoration failed.",
                primary if primary is not None else cleanup_error,
            )
            if primary is None:
                raise
            # BaseException.add_note is unavailable in the Python 3.10 Kit
            # environments. Keep the original measurement error authoritative.
            import logging

            try:
                logging.getLogger(__name__).warning("Asset visibility restoration also failed: %s", cleanup_error)
            except Exception:
                pass
    count = asset_diagnostic_pixel_count(visible, hidden)
    ctx.add_metric("visibility_asset_pixels", count)
    return count >= min_pixels
