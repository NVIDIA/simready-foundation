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
"""Reading rendered frames: silhouettes, and differences inside them.

Every measurement in the FET006 material family is denominated in the asset's
own silhouette, cut out of a frame in which the asset has been painted a flat
magenta by a probe material. Nothing here masks against a nominal room colour.

``ctx.compare_object_pixels`` does mask that way, and it only implements two
rooms: white, where object means ``luma < 0.85``, and black, where it means
``luma > 0.03``. Any other colour falls through to the white-room branch with a
warning, so a mid grey room counted as object -- a toaster covering roughly
293,000 pixels measured 724,873 of the 1,048,576 in the frame.

A whole-frame difference is no better as a footprint. It counts the shadow the
asset casts and the light it bounces onto the room as part of the asset. On a
small bright carrier measured on the rig, 95.8% of the difference was neither.

So the silhouette is cut from a painted frame, and every comparison is
restricted to it.
"""


def _load(path):
    """A frame as a float array in 0..1, or None when PIL/numpy are missing."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    return np.asarray(Image.open(path).convert("RGB"), dtype="float32") / 255.0


def changed_pixels(path_a, path_b, threshold=0.04):
    """How many pixels differ between two frames by more than ``threshold``.

    The comparison is the largest single-channel difference, not the mean
    across channels. A mean hides a strong shift in one channel behind two
    unchanged ones, which is exactly the case the colour probes rely on: a
    magenta object against a grey wall moves red and blue hard and leaves
    green almost alone.

    Returns -1 when the frames cannot be read or their shapes disagree, which
    callers should report as an unmeasured run rather than as zero.
    """
    import numpy as np

    a = _load(path_a)
    b = _load(path_b)
    if a is None or b is None or a.shape != b.shape:
        return -1
    return int(np.count_nonzero(np.max(np.abs(a - b), axis=2) > float(threshold)))


def dominant_mask(path, channels, ratio=1.5, floor=0.20):
    """Pixels where every named channel beats every other one, as a mask.

    Two uses, and they want opposite things from it.

    The asset's silhouette is cut with ``channels=(0, 2)``. The asset is painted
    a flat saturated magenta by a probe material and captured; magenta is red
    and blue together over green, so a pixel counts when both of those exceed
    the third by ``ratio`` and are themselves above ``floor``.

    A secondary is a better probe colour than a primary. The mask has to
    survive the specular sheen an OpenPBR surface puts on the object -- specular
    is white, so it lifts all three channels and erodes any dominance test --
    and a secondary starts with two channels at full rather than one, so the
    sheen has further to go before the ratio breaks.

    ``channels=(0,)`` cuts red-dominant pixels instead, which is how
    ``preview_surface_renders`` recognises Kit's default material: it renders at
    (0.7374, 0.1597, 0.1598), a red over four times either other channel.
    Nothing is painted for that one -- it reads the asset's own frame.

    Differencing against an empty-room capture is the obvious alternative and
    it does not work: a saturated object throws a wide, dim tinted bounce across
    the room, and every pixel of that bounce differs from the empty room. Masked
    that way, one toaster part measured 358,868 px against a whole-object
    footprint of about 295,000. The bounce is dim and only weakly tinted, so a
    dominance test with a brightness floor rejects it while keeping the object
    itself, which is saturated and bright.

    Returns None when the frame cannot be read.
    """
    img = _load(path)
    if img is None:
        return None
    channels = tuple(int(c) for c in channels)
    rest = [i for i in range(3) if i not in channels]
    mask = None
    for c in channels:
        band = img[:, :, c]
        for other in rest:
            hit = band > img[:, :, other] * float(ratio)
            mask = hit if mask is None else (mask & hit)
        mask = mask & (band > float(floor))
    return mask


def mask_intersection(mask_a, mask_b):
    """The pixels two masks both select, or None when they cannot be combined.

    Two renders taken in separate stages each cut their own silhouette. The
    intersection is the geometry both frames agree is there, which is the only
    region where a pixel in one corresponds to the same point on the asset in
    the other. How much smaller it is than either input is also what tells a
    caller the camera framed the asset differently between the two.
    """
    if mask_a is None or mask_b is None or mask_a.shape != mask_b.shape:
        return None
    return mask_a & mask_b


def changed_pixels_in(path_a, path_b, mask, threshold=0.04):
    """``changed_pixels`` restricted to a mask.

    Returns -1 when either frame cannot be read, their shapes disagree, or the
    mask does not match them, which callers must report rather than read as
    zero.
    """
    import numpy as np

    a = _load(path_a)
    b = _load(path_b)
    if a is None or b is None or a.shape != b.shape or mask is None:
        return -1
    if a.shape[:2] != mask.shape:
        return -1
    moved = np.max(np.abs(a - b), axis=2) > float(threshold)
    return int(np.count_nonzero(moved & mask))


def mask_size(mask):
    """How many pixels a mask selects. ``-1`` when there is no mask.

    A boolean numpy array sums to its own count, so this needs no import and
    works in a run where numpy could not be loaded -- which is the run where
    ``mask`` is None and the caller has to report an unmeasured result rather
    than crash counting it.
    """
    if mask is None:
        return -1
    return int(mask.sum())


def masked_mean_rgb(path, mask):
    """Mean RGB of one frame over a silhouette mask.

    Returns None when the frame cannot be read, the mask does not match its
    shape, or the mask selects nothing.
    """
    import numpy as np

    img = _load(path)
    if img is None or mask is None:
        return None
    if img.shape[:2] != mask.shape:
        return None
    if int(np.count_nonzero(mask)) == 0:
        return None
    return [float(np.mean(img[:, :, c][mask])) for c in range(3)]


def frame_summary(path):
    """Mean RGB of a frame, for the report. ``None`` when it cannot be read."""
    import numpy as np

    img = _load(path)
    if img is None:
        return None
    return [round(float(v), 4) for v in np.mean(img, axis=(0, 1))]
