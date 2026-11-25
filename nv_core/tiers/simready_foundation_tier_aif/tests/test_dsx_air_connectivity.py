# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""DSX Air connectivity contract with in-process API/SSH doubles only."""
import copy
import json
from pathlib import Path

import pytest

from simready.foundation.tier_aif import dsx_air


SIMULATION = "11111111-1111-4111-8111-111111111111"
OTHER_SIMULATION = "99999999-9999-4999-8999-999999999999"
SOURCE_SERVICE = "22222222-2222-4222-8222-222222222222"
PEER_SERVICE = "33333333-3333-4333-8333-333333333333"
SOURCE_MGMT = "44444444-4444-4444-8444-444444444444"
PEER_MGMT = "55555555-5555-4555-8555-555555555555"
SOURCE_NODE = "66666666-6666-4666-8666-666666666666"
PEER_NODE = "77777777-7777-4777-8777-777777777777"
PING_OK = "3 packets transmitted, 3 received, 0% packet loss, time 2001ms\n"


def _guest_address(address):
    return [{"ifname": "swp1", "addr_info": [{"family": "inet", "local": address}]}]


@pytest.fixture
def lab_double(monkeypatch, tmp_path):
    fixture = {
        "simulation_id": SIMULATION,
        "asset_port": "ethernet_01",
        "source": {"service_id": SOURCE_SERVICE, "interface": "swp1", "user": "cumulus"},
        "peer": {"service_id": PEER_SERVICE, "interface": "swp1", "user": "cumulus"},
        "peer_ipv4": "192.0.2.2",
    }
    responses = {
        f"{SIMULATION}/": {"id": SIMULATION, "state": "ACTIVE"},
        f"{SIMULATION}/export/?topology_format=JSON": {
            "content": {"links": [[
                {"node": "leaf1", "interface": "swp1"},
                {"node": "leaf2", "interface": "swp1"},
            ]]},
        },
        f"nodes/interfaces/services/{SOURCE_SERVICE}/": {
            "id": SOURCE_SERVICE, "interface": SOURCE_MGMT, "service_type": "SSH",
            "worker_fqdn": "worker.example", "worker_port": 11001,
        },
        f"nodes/interfaces/services/{PEER_SERVICE}/": {
            "id": PEER_SERVICE, "interface": PEER_MGMT, "service_type": "SSH",
            "worker_fqdn": "worker.example", "worker_port": 11002,
        },
        f"nodes/interfaces/{SOURCE_MGMT}/": {"id": SOURCE_MGMT, "node": SOURCE_NODE},
        f"nodes/interfaces/{PEER_MGMT}/": {"id": PEER_MGMT, "node": PEER_NODE},
        f"nodes/{SOURCE_NODE}/": {"id": SOURCE_NODE, "name": "leaf1", "simulation": SIMULATION},
        f"nodes/{PEER_NODE}/": {"id": PEER_NODE, "name": "leaf2", "simulation": SIMULATION},
    }
    state = {
        "fixture": fixture,
        "responses": responses,
        "source_addresses": _guest_address("192.0.2.1") + [
            {"ifname": "eth0", "addr_info": [{"family": "inet", "local": "198.51.100.10"}]},
        ],
        "peer_addresses": _guest_address("192.0.2.2"),
        "ping_output": PING_OK,
        "ping_error": None,
        "api_calls": [],
        "ssh_calls": [],
    }

    def fake_get(path):
        state["api_calls"].append(path)
        assert path in responses, f"Unexpected API path: {path}"
        return copy.deepcopy(responses[path])

    def fake_ssh(service, user, *command):
        state["ssh_calls"].append((copy.deepcopy(service), user, command))
        assert user == "cumulus"
        if command == ("ip", "-j", "-4", "address", "show", "dev", "swp1"):
            assert service["id"] == PEER_SERVICE
            return json.dumps(state["peer_addresses"])
        if command == ("ip", "-j", "-4", "address", "show"):
            assert service["id"] == SOURCE_SERVICE
            return json.dumps(state["source_addresses"])
        if command == ("ping", "-n", "-I", "swp1", "-c", "3", "-W", "2", fixture["peer_ipv4"]):
            assert service["id"] == SOURCE_SERVICE
            if state["ping_error"]:
                raise RuntimeError(state["ping_error"])
            return state["ping_output"]
        raise AssertionError(f"Unexpected guest command: {command}")

    monkeypatch.setattr(dsx_air, "_get", fake_get)
    monkeypatch.setattr(dsx_air, "_ssh", fake_ssh)
    asset = Path(__file__).resolve().parents[4] / (
        "sample_content/aif/Synthetic_NetworkEquipment/asset/Synthetic_NetworkEquipment.usda"
    )
    fixture_path = tmp_path / "designated-simulation.json"

    def run():
        fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
        return dsx_air.run_connectivity(asset, fixture_path)

    state["run"] = run
    return state


def test_designated_link_connectivity_success(lab_double):
    result = lab_double["run"]()
    assert result["transmitted"] == 3
    assert result["received"] == 3
    assert lab_double["ssh_calls"][-1][2] == (
        "ping", "-n", "-I", "swp1", "-c", "3", "-W", "2", "192.0.2.2",
    )


def test_inactive_simulation_is_rejected(lab_double):
    lab_double["responses"][f"{SIMULATION}/"]["state"] = "STOPPED"
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_services_from_different_simulations_are_rejected(lab_double):
    lab_double["responses"][f"nodes/{PEER_NODE}/"]["simulation"] = OTHER_SIMULATION
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_missing_topology_link_is_rejected(lab_double):
    lab_double["responses"][f"{SIMULATION}/export/?topology_format=JSON"]["content"]["links"] = []
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_same_service_cannot_be_source_and_peer(lab_double):
    lab_double["fixture"]["peer"]["service_id"] = SOURCE_SERVICE
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_same_node_cannot_be_source_and_peer(lab_double):
    lab_double["responses"][f"nodes/interfaces/{PEER_MGMT}/"]["node"] = SOURCE_NODE
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_missing_usd_network_port_is_rejected(lab_double):
    lab_double["fixture"]["asset_port"] = "missing_ethernet_port"
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_ping_command_failure_is_reported(lab_double):
    lab_double["ping_error"] = "ping exited with status 1"
    with pytest.raises(RuntimeError):
        lab_double["run"]()
    assert any(call[2][0] == "ping" for call in lab_double["ssh_calls"])


@pytest.mark.parametrize("received,passed", [(0, False), (1, True), (2, True)])
def test_received_echoes_determine_reachability(lab_double, received, passed):
    loss = (3 - received) / 3 * 100
    lab_double["ping_output"] = f"3 packets transmitted, {received} received, {loss:.4f}% packet loss, time 2000ms\n"
    result = lab_double["run"]()
    assert result["transmitted"] == 3
    assert result["received"] == received
    assert result["passed"] is passed


def test_target_address_must_belong_to_peer_interface(lab_double):
    lab_double["fixture"]["peer_ipv4"] = "192.0.2.3"
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not any(call[2][0] == "ping" for call in lab_double["ssh_calls"])


def test_target_address_cannot_be_local_to_source(lab_double):
    lab_double["fixture"]["peer_ipv4"] = "192.0.2.1"
    lab_double["peer_addresses"] = _guest_address("192.0.2.1")
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not any(call[2][0] == "ping" for call in lab_double["ssh_calls"])


def test_target_must_be_numeric_ipv4(lab_double):
    lab_double["fixture"]["peer_ipv4"] = "peer.example"
    with pytest.raises((RuntimeError, ValueError)):
        lab_double["run"]()
    assert not lab_double["ssh_calls"]


def test_source_data_interface_requires_own_address(lab_double):
    lab_double["source_addresses"] = [
        {"ifname": "eth0", "addr_info": [{"family": "inet", "local": "198.51.100.10"}]},
    ]
    with pytest.raises(ValueError):
        lab_double["run"]()
    assert not any(call[2][0] == "ping" for call in lab_double["ssh_calls"])


def test_ssh_command_error_is_reported_without_network(monkeypatch):
    from types import SimpleNamespace

    def failed_process(*args, **kwargs):
        return SimpleNamespace(returncode=-1, stdout="", stderr="mock transport failure")

    monkeypatch.setattr(dsx_air.subprocess, "run", failed_process)
    with pytest.raises(RuntimeError, match="status -1"):
        dsx_air._ssh({"worker_fqdn": "worker.example", "worker_port": 11001}, "cumulus", "ip", "-j")


def test_ping_no_reply_exit_is_preserved_for_runtime_result(monkeypatch):
    from types import SimpleNamespace

    output = "3 packets transmitted, 0 received, 100% packet loss, time 2000ms\n"
    monkeypatch.setattr(dsx_air.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout=output, stderr="",
    ))
    assert dsx_air._ssh({"worker_fqdn": "worker.example", "worker_port": 11001}, "cumulus",
                        "ping", "-n", "-c", "3", "192.0.2.2") == output
