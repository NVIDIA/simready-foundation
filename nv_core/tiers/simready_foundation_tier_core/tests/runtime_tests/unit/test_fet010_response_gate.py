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

"""What the DISP.001 response gate decides, and what it deliberately does not.

``display_color_response`` measures one ratio: the share of the asset's
silhouette that changes when the primvar reader is replaced by a flat constant
of the reader's own fallback colour. Geometry that resolved a display colour
differs between those two frames and geometry that resolved none does not.

The gate on it asks whether that number is distinguishable from nothing. It
does **not** ask whether it is large, and these tests exist mostly to pin that
distinction, because the ratio looks like a coverage measurement and is not one.

The numbers below are why. Two fixtures break DISP.001 -- four of five Gprims
resolving nothing, and one of five -- and the ratio puts them two orders of
magnitude apart, in the wrong order, because it is denominated in pixels and
the requirement is denominated in Gprims. No floor on this ratio separates
them. Both now pass, and DISP.001 fails both in the validator, per Gprim and by
name.
"""

from simready_benchmark.core.decorator import get_registered_tests

# Importing the module is what registers it; the decorator returns the bare
# function, so the config lives on the Definition rather than on the function.
from simready_benchmark_kit_suite.fet010_standard import display_color_response  # noqa: F401

CONFIG = next(
    d.config_defaults
    for d in get_registered_tests()
    if d.name == "display_color_response"
)

# Measured on Isaac Sim 6.0. Some display colour of the asset's own reaches the
# shader in every one of these, so the feature is live and the benchmark says
# yes. How much of the asset carries one varies from all of it to one Gprim in
# five, and this test is not the thing that tells them apart.
LIVE = {
    "reference toaster, a colour on each Gprim": 1.0,
    "reference toaster, one constant on an ancestor Xform": 0.999942,
    "workbench tool": 1.0,
    "joystick": 1.0,
    "lamp": 0.999989,
    "light bulb": 1.0,
    # Four of five Gprims resolve nothing. Passes here, fails DISP.001.
    "toaster, a colour on the body alone": 0.974982,
    # One of five resolves nothing. Passes here, fails DISP.001. Two orders of
    # magnitude below the row above it, for a smaller defect.
    "toaster, a colour on the four small parts alone": 0.027407,
}
# Nothing reaches the shader. These are at or below the swap noise.
INERT = {
    "toaster, no display colour anywhere": 0.000756,
    # Every Gprim resolves a colour and the colour is the probe's own constant,
    # so nothing moves. A false failure, and the one the collapse to a single
    # comparison introduced.
    "toaster, every colour authored as the probe's magenta": 0.000766,
}
# Two renders that should have been identical, across every run measured.
CONTROL = (0.0, 0.000027, 0.00006, 0.000085, 0.000119, 0.000251, 0.000427,
           0.000532, 0.000549)


def gate(response, config=None):
    """The decision the test body makes, kept in step with it."""
    config = config or CONFIG
    return response >= float(config["min_response_ratio"])


def test_the_gate_passes_every_asset_whose_display_colour_reaches_the_shader():
    for asset, response in LIVE.items():
        assert gate(response), asset


def test_the_gate_fails_every_asset_where_nothing_reaches_the_shader():
    for asset, response in INERT.items():
        assert not gate(response), asset


def test_a_partial_asset_passes_because_coverage_is_not_this_test_s_question():
    """The point of the whole file. Both of these break DISP.001 and both pass
    here, on purpose: display colour is doing something in the engine, which is
    all this benchmark is in a position to say."""
    mostly_missing = LIVE["toaster, a colour on the body alone"]
    barely_missing = LIVE["toaster, a colour on the four small parts alone"]

    assert gate(mostly_missing)
    assert gate(barely_missing)
    # The larger defect reads higher than the smaller one, which is what makes
    # the ratio useless as a coverage measure however it is gated.
    assert mostly_missing > barely_missing * 30


def test_the_floor_sits_in_the_gap_between_nothing_and_something():
    """And the gap is narrower than it looks from the conformant end.

    The quietest live run is 2.7%, not 97%, because the geometry carrying a
    display colour there is small. A floor chosen from the conformant assets
    alone -- anything at or above 5% -- fails it.
    """
    floor = float(CONFIG["min_response_ratio"])
    quietest_live = min(LIVE.values())
    loudest_inert = max(INERT.values())

    assert loudest_inert < floor < quietest_live
    # Several times clear of each side, so the floor is not tuned to either.
    assert floor > loudest_inert * 5
    assert quietest_live > floor * 5


def test_the_floor_clears_every_control_ratio_measured():
    """The control is two renders of the same material. The gate has to sit
    well above it or an unsettled render reads as a display colour.

    The worst control across every run on the rig was 0.000549, so the floor
    stands at 9.1 times it. The run is separately rejected as unsettled above
    max_control_ratio, which is another factor of 36 up from there.
    """
    assert max(CONTROL) * 5 < float(CONFIG["min_response_ratio"])
    assert float(CONFIG["min_response_ratio"]) < float(CONFIG["max_control_ratio"])


def test_the_opacity_floor_is_a_presence_floor_too():
    """The workbench tool is why. It renders very dark against this test's
    black room, so an invisible copy of it differs from a visible one over less
    than half the silhouette, and it measured 0.412 with the opacity reader
    working correctly. A floor set for magnitude failed a conformant shipping
    sample on nothing but how dark it is."""
    floor = float(CONFIG["min_opacity_response_ratio"])
    workbench_tool = 0.412132

    assert workbench_tool >= floor
    # And an asset whose opacity reader does nothing at all still fails.
    assert 0.0 < floor
    # Held level with the response floor: same question, same swap noise.
    assert floor == float(CONFIG["min_response_ratio"])


def test_the_dc003_no_change_case_reuses_the_control_ceiling():
    """It is the other pair of frames in this test that should agree, so it
    cannot be tighter than the swap noise the same run demonstrated. The
    coverage limit it used to borrow is gone."""
    assert "max_control_ratio" in CONFIG
    assert "max_coverage_ratio" not in CONFIG
    assert "coverage_noise_multiple" not in CONFIG
