"""
service/virtual_device.py

VirtualDevice — simulates one phone in the offline mesh.
Has a packet store and a flag indicating whether it currently has internet.
Mirrors VirtualDevice.java.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from model.schemas import MeshPacket


@dataclass
class VirtualDevice:
    device_id:   str
    has_internet: bool = False
    _packets:     list[MeshPacket] = field(default_factory=list)

    def receive(self, packet: MeshPacket):
        """Accept a packet if not already held (dedupe by packet_id)."""
        ids = {p.packet_id for p in self._packets}
        if packet.packet_id not in ids:
            self._packets.append(packet)

    def get_packets(self) -> list[MeshPacket]:
        return list(self._packets)

    def clear(self):
        self._packets.clear()

    def packet_count(self) -> int:
        return len(self._packets)

    def to_dict(self) -> dict:
        return {
            "device_id":    self.device_id,
            "has_internet": self.has_internet,
            "packet_count": self.packet_count(),
        }
