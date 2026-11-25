# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check one authored network port against a directly linked peer in a running DSX Air lab."""

import argparse
from dataclasses import dataclass
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from pxr import Sdf, Usd


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None  # Keep the bearer on the Air API origin.


def _get(path):
    token = os.environ.get("DSX_AIR_TOKEN")
    if not token:
        raise RuntimeError("Set DSX_AIR_TOKEN to a bearer with read access to the designated simulation.")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if org := os.environ.get("DSX_AIR_ORG"):
        headers["Nv-Ngc-Org"] = org
    request = Request(f"https://api.dsx-air.nvidia.com/api/v3/simulations/{path}", headers=headers)
    try:
        with build_opener(_NoRedirect).open(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"DSX Air returned HTTP {exc.code} for {path}.") from None


def _ssh(service, user, *command):
    # OpenSSH joins the remote argv for a shell. Variable arguments are limited
    # to checked interface names and a canonical IPv4 literal.
    host = service.get("worker_fqdn")
    port = service.get("worker_port")
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise ValueError("Air did not report a usable SSH worker hostname.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Air did not report an active SSH service port.")
    args = ["ssh", "-F", "/dev/null", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ForwardAgent=no", "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=5",
            "-p", str(port), "-l", user, "--", host, "LC_ALL=C", *command]
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"SSH timed out running {command[0]}.") from exc
    if result.returncode and not (command[0] == "ping" and result.returncode == 1):
        raise RuntimeError(f"SSH command {command[0]} exited with status {result.returncode}.")
    return result.stdout


def _object(parent, object_id):
    identifier = str(UUID(str(object_id)))
    row = _get(f"{parent}{identifier}/")
    if row.get("id") != identifier:
        raise ValueError("DSX Air returned a different object than requested.")
    return row


@dataclass
class _Endpoint:
    service: dict
    user: str
    interface: str
    node: dict


def _endpoint(simulation, config):
    interface = config["interface"]
    user = config["user"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}", interface):
        raise ValueError("Expected a Linux data interface name.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", user):
        raise ValueError("Expected an SSH user name.")
    service = _object("nodes/interfaces/services/", config["service_id"])
    if str(service.get("service_type")).lower() != "ssh":
        raise ValueError("The designated management service must be SSH.")
    management = _object("nodes/interfaces/", service["interface"])
    node = _object("nodes/", management["node"])
    if node["simulation"] != simulation:
        raise ValueError("The SSH service belongs to a device in a different simulation.")
    return _Endpoint(service, user, interface, node)


def _asset_port(asset_path, name):
    if not isinstance(name, str) or not Sdf.Path.IsValidIdentifier(name):
        raise ValueError("asset_port must be the name of a direct ConnectionPoints child.")
    stage = Usd.Stage.Open(str(asset_path))
    root = stage.GetDefaultPrim() if stage else None
    if not root or root.GetAttribute("aif:core:assetClass").Get() != "network-equipment":
        raise ValueError("Expected a network-equipment asset with a default prim.")
    scope = root.GetChild("ConnectionPoints")
    port = scope.GetChild(name) if scope and scope.GetTypeName() == "Scope" else None
    if (not port or port.GetTypeName() != "Xform"
            or port.GetAttribute("simready:connectionPoint:domain").Get() != "network"):
        raise ValueError(f"Expected a network-domain connection point named {name}.")
    return str(port.GetPath())


def _linked(links, source, peer):
    pair = {(end.node["name"], end.interface) for end in (source, peer)}
    for link in links:
        if isinstance(link, list) and len(link) == 2 and all(isinstance(end, dict) for end in link):
            endpoints = {(end.get("node"), end.get("interface")) for end in link}
            if endpoints == pair:
                return True
    return False


def _ipv4_addresses(rows, interface=None):
    return {addr["local"] for row in rows if interface is None or row["ifname"] == interface
            for addr in row["addr_info"] if addr["family"] == "inet"}


def run_connectivity(asset_path, fixture_path):
    """Return packet counts for a measured exchange. Raise on a fixture or execution error."""
    config = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    try:
        port_path = _asset_port(asset_path, config["asset_port"])
        target = IPv4Address(config["peer_ipv4"])
        if target.is_loopback or target.is_multicast or target.is_unspecified or target.is_reserved:
            raise ValueError("peer_ipv4 must identify a unicast address on the peer data interface.")
        sim = _object("", config["simulation_id"])
        if sim["state"] != "ACTIVE":
            raise ValueError("The designated DSX Air simulation must be ACTIVE.")
        source = _endpoint(sim["id"], config["source"])
        peer = _endpoint(sim["id"], config["peer"])
        if source.node["id"] == peer.node["id"]:
            raise ValueError("Connectivity requires two distinct devices.")
        export = _get(f"{sim['id']}/export/?topology_format=JSON")
        if not _linked(export["content"]["links"], source, peer):
            raise ValueError("The designated data interfaces do not share a link in the live topology.")
        peer_rows = json.loads(_ssh(peer.service, peer.user, "ip", "-j", "-4", "address", "show", "dev", peer.interface))
        src_rows = json.loads(_ssh(source.service, source.user, "ip", "-j", "-4", "address", "show"))
        if str(target) not in _ipv4_addresses(peer_rows, peer.interface):
            raise ValueError("peer_ipv4 is not assigned to the designated peer interface.")
        if not _ipv4_addresses(src_rows, source.interface) or str(target) in _ipv4_addresses(src_rows):
            raise ValueError("The source needs its own IPv4 address and a nonlocal peer address.")
        reply = _ssh(source.service, source.user, "ping", "-n", "-I", source.interface, "-c", "3", "-W", "2", str(target))
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid DSX Air fixture, inventory or interface data ({exc}).") from None

    counts = re.search(r"^(\d+) packets transmitted, (\d+)(?: packets)? received\b", reply, re.MULTILINE)
    if not counts or int(counts[1]) != 3 or int(counts[2]) > 3:
        raise RuntimeError("Could not verify three transmitted probes in the ping summary.")
    transmitted, received = map(int, counts.groups())
    return {
        "passed": received > 0,
        "simulation_id": sim["id"],
        "asset_port": port_path,
        "source_node": source.node["name"],
        "source_interface": source.interface,
        "peer_node": peer.node["name"],
        "peer_interface": peer.interface,
        "peer_ipv4": str(target),
        "transmitted": transmitted,
        "received": received,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    try:
        result = run_connectivity(args.asset, args.fixture)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
