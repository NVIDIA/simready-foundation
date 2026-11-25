---
name: simready-foundation-conform-fet-207-dsxair
description: Prepare a network-equipment USD and verify one mapped data interface against a directly linked peer in DSX Air.
---

# Conform Networking in DSX Air

1. Validate the staged asset against `Networking@0.3.0`. Resolve NET.001–NET.004 using
   the equipment Properties layer and its network-domain ConnectionPoints. Preserve the source asset.
2. For runtime evaluation, obtain the operator's designated running simulation, SSH service IDs,
   source USD port and its corresponding guest interface, and the peer interface and IPv4 address.
3. Follow the [feature procedure](../../features/FET207_Networking.DSXAir.md) to supply the fixture
   and run the connectivity test. Record the mapped endpoints and packet counts. If live access
   is unavailable or a run is outside the requested scope, report static validation and leave
   the runtime result unmeasured.
