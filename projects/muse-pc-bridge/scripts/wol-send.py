#!/usr/bin/env python3
"""wol-send.py — send a Wake-on-LAN magic packet. No bridge needed.

    python wol-send.py AA:BB:CC:DD:EE:FF [--broadcast 192.168.1.255] [--port 9]

This is the standalone half of the bridge's Wake-on-LAN story. The
bridge agent can send magic packets FROM the PC (POST /v1/wol) to
wake other machines on the home LAN — but a sleeping PC cannot run
its own agent, so NOTHING in the bridge can wake the bridge PC
itself. To wake it, this script (or any WoL tool) must run on some
other device that is awake on the same LAN at that moment: a router
with a WoL function, a NAS, a Raspberry Pi, a phone app, or an awake
computer joined to the same network over Tailscale (the packet must
leave on the LAN broadcast address — Tailscale itself carries only
unicast, so the sender has to be a LAN peer).

Prerequisites on the target machine (one-time, owner-side): WoL
enabled in BIOS/UEFI ("Power On By PCI-E" / "Wake on LAN"), the NIC
allowed to wake the machine in the OS, and ideally a wired Ethernet
connection — most Wi-Fi adapters cannot be woken. On Windows the
wired NIC's MAC is shown by `ipconfig /all` ("Physical Address").

Python 3 standard library only, like the rest of this project.
"""

from __future__ import annotations

import argparse
import re
import socket
import sys

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([:-]?[0-9A-Fa-f]{2}){5}$")


def normalize_mac(value: str) -> str:
    if not _MAC_RE.match(value.strip()):
        raise ValueError(f"invalid MAC address: {value!r}")
    digits = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def build_magic_packet(mac: str) -> bytes:
    raw = bytes.fromhex(normalize_mac(mac).replace(":", ""))
    return b"\xff" * 6 + raw * 16


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send a Wake-on-LAN magic packet.")
    parser.add_argument("mac", help="target MAC address "
                                    "(AA:BB:CC:DD:EE:FF, dashes or bare hex)")
    parser.add_argument("--broadcast", default="255.255.255.255",
                        help="broadcast address of the target's LAN "
                             "(default: 255.255.255.255; a subnet "
                             "broadcast like 192.168.1.255 is more "
                             "reliable when the sender is routed)")
    parser.add_argument("--port", type=int, default=9,
                        help="UDP port (default: 9; 7 is the other "
                             "conventional choice)")
    args = parser.parse_args(argv)
    try:
        mac = normalize_mac(args.mac)
    except ValueError as exc:
        print(f"wol-send: {exc}", file=sys.stderr)
        return 2
    if not 0 < args.port < 65536:
        print("wol-send: port must be in 1..65535", file=sys.stderr)
        return 2
    packet = build_magic_packet(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (args.broadcast, args.port))
    finally:
        sock.close()
    print(f"sent {len(packet)}-byte magic packet for {mac} "
          f"to {args.broadcast}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
