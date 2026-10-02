# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Behavioral checks beyond namespace completeness for fictional CP2 fixtures."""
import importlib.util
import math
from pathlib import Path

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = FIXTURES / 'connection_points'
spec = importlib.util.spec_from_file_location('fixture_cp_builder', SOURCE / 'build_connection_points.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ASSETS = builder.load_values()
PREFIX = 'simready:connectionPoint:'


def ports(name):
    stage = Usd.Stage.Open(str(builder.resolve(ASSETS[name]['asset'])))
    scope = stage.GetDefaultPrim().GetChild('ConnectionPoints')
    return stage, list(scope.GetChildren())


def value(prim, name):
    return prim.GetAttribute(PREFIX + name).Get()


@pytest.mark.parametrize('name', ASSETS)
def test_committed_ports_match_regeneratable_source(name):
    committed = Sdf.Layer.FindOrOpen(str(builder.resolve(ASSETS[name]['layer'])))
    generated = Sdf.Layer.CreateAnonymous()
    assert generated.ImportFromString(builder.layer_text(name))
    assert committed.ExportToString() == generated.ExportToString()


@pytest.mark.parametrize('name', ASSETS)
def test_rigid_frames_and_domain_limits(name):
    stage, frames = ports(name)
    positions = []
    for frame in frames:
        assert frame.GetTypeName() == 'Xform'
        assert value(frame, 'domain') in ('thermal', 'electrical', 'airflow')
        assert UsdGeom.Imageable(frame).GetPurposeAttr().Get() == 'guide'
        matrix = UsdGeom.Xformable(frame).GetLocalTransformation()
        axes = [Gf.Vec3d(*matrix.GetRow(i)[:3]) for i in range(3)]
        for axis in axes:
            assert axis.GetLength() == pytest.approx(1)
        assert Gf.Dot(Gf.Cross(axes[0], axes[1]), axes[2]) == pytest.approx(1)
        positions.append(tuple(matrix.ExtractTranslation()))
        domain = value(frame, 'domain')
        if domain in ('thermal', 'airflow'):
            flow = 'FlowRate' if domain == 'thermal' else 'AirflowRate'
            assert value(frame, f'{domain}:max{flow}') >= value(frame, f'{domain}:design{flow}') > 0
            assert value(frame, f'{domain}:maxTemperature') >= value(frame, f'{domain}:designTemperature')
        if domain == 'thermal':
            assert value(frame, 'thermal:maxPressure') >= value(frame, 'thermal:operatingPressure') > 0
            # 4 m/s, not the 2-3 m/s the fixture bores were first chosen for:
            # a CDU secondary connection is 101 mm and carries up to 30 L/s,
            # which is 3.74 m/s.
            speed = value(frame, 'thermal:designFlowRate') / 1000 / (math.pi * value(frame, 'thermal:portDiameter')**2 / 4)
            assert 1 < speed < 4
        if domain == 'electrical':
            current = value(frame, 'electrical:maxCurrent')
            capacity = math.sqrt(3)*value(frame, 'electrical:nominalVoltage')*value(frame, 'electrical:powerFactor')*current
            assert capacity >= value(frame, 'electrical:ratedPower')
            assert value(frame, 'electrical:breakerRating') >= 1.25*current
        if domain == 'airflow':
            area = value(frame, 'airflow:interfaceWidth')*value(frame, 'airflow:interfaceHeight')*value(frame, 'airflow:freeAreaRatio')
            assert area > 0
            assert value(frame, 'airflow:designAirflowRate')/area < 5
    assert len(positions) == len(set(positions)), 'Unintended co-located interfaces'


@pytest.mark.parametrize('name', ['Generic_CDU', 'Synthetic_CDU'])
def test_cdu_branch_and_heat_balance(name):
    stage, frames = ports(name)
    # 1200 kW of rack duty on the secondary. The facility side carries that plus
    # the CDU's own 22 kW electrical draw, conservatively all rejected to water.
    # 3.9 kJ/L/K is an assumed volumetric heat capacity for the glycol mixture,
    # not water's 4.18.
    for system, capacity, cp in [('TCS', 1200., 3.9), ('FWS', 1222., 4.18)]:
        circuit = [p for p in frames if value(p, 'domain') == 'thermal' and value(p, 'system') == system]
        supply = [p for p in circuit if value(p, 'direction') == 'supply']
        returns = [p for p in circuit if value(p, 'direction') == 'return']
        flow = sum(value(p, 'thermal:designFlowRate') for p in supply)
        assert flow == pytest.approx(sum(value(p, 'thermal:designFlowRate') for p in returns))
        dt = value(returns[0], 'thermal:designTemperature')-value(supply[0], 'thermal:designTemperature')
        assert flow*cp*dt == pytest.approx(capacity, rel=1e-4)
    # Counterflow: the facility side is colder than the secondary side it faces
    # at both ends of the exchanger. Pairing secondary supply against facility
    # *return* instead would forbid any facility rise larger than the approach.
    ends = {(value(p,'system'), value(p,'direction')): p for p in frames if value(p,'domain')=='thermal'}
    for direction in ('supply', 'return'):
        approach = (value(ends[('TCS', direction)], 'thermal:designTemperature')
                    - value(ends[('FWS', direction)], 'thermal:designTemperature'))
        assert approach == pytest.approx(4., abs=0.01)


def test_crah_sensible_total_and_electrical_balance():
    """The coil carries the air-side sensible load, the latent load and the fan draw.

    Gross coil duty is 105 kW. 9 kW of CRAH electrical input lands inside the air
    boundary as sensible heat and 5 kW of the duty is latent, so 91 kW is what the
    air stream actually carries. The namespace has no humidity property, which is
    why the 5 kW appears here as a constant and nowhere on a connection point.
    """
    stage, frames = ports('Synthetic_CRAH')
    air = {value(p,'direction'):p for p in frames if value(p,'domain')=='airflow'}
    water = {value(p,'direction'):p for p in frames if value(p,'domain')=='thermal'}
    net_sensible = value(air['input'],'airflow:designAirflowRate')*1.2*1.006*(value(air['input'],'airflow:designTemperature')-value(air['output'],'airflow:designTemperature'))
    total_coil = value(water['supply'],'thermal:designFlowRate')*4.18*(value(water['return'],'thermal:designTemperature')-value(water['supply'],'thermal:designTemperature'))
    assert net_sensible == pytest.approx(91., rel=1e-4)
    assert total_coil == pytest.approx(net_sensible+5.+9., rel=1e-4)
    assert value(water['supply'],'thermal:operatingPressure')-value(water['return'],'thermal:operatingPressure') == pytest.approx(12*2989.0669, rel=1e-5)


def test_rack_each_four_feed_bank_supports_full_load():
    stage, frames = ports('gb300')
    feeds = sorted([p for p in frames if value(p,'domain')=='electrical'],key=lambda p:p.GetName())
    assert len(feeds)==8
    for bank in (feeds[:4],feeds[4:]):
        assert sum(value(p,'electrical:ratedPower') for p in bank)==136000
        assert all(value(p,'direction')=='input' for p in bank)


def test_ups_is_consistent_output_interface():
    stage, frames = ports('Synthetic_UPS')
    assert len(frames)==1
    port=frames[0]
    assert value(port,'direction')=='output'
    root=stage.GetDefaultPrim()
    for source,target,scale in [('outputActivePower','ratedPower',1000),('outputVoltage','nominalVoltage',1),('loadPowerFactor','powerFactor',1),('electricalOutputFrequency','frequency',1)]:
        assert value(port,'electrical:'+target)==pytest.approx(root.GetAttribute('aif:spec:'+source).Get()*scale)
