"""
service/mesh_simulator.py

MeshSimulatorService — manages the five virtual phones and drives the
gossip protocol. Mirrors MeshSimulatorService.java.

Gossip rule: every device broadcasts every packet it holds to every other
device. TTL decrements by 1 per hop; packets with TTL=0 are dropped.
In real life this happens organically as people walk past each other.
"""

import threading
from model.schemas import MeshPacket
from service.virtual_device import VirtualDevice
from service import bridge_ingestion

_lock = threading.Lock()

# Five virtual devices — one has internet (the bridge)
_devices: list[VirtualDevice] = [
    VirtualDevice("phone-alice",   has_internet=False),
    VirtualDevice("phone-bob",     has_internet=False),
    VirtualDevice("phone-charlie", has_internet=False),
    VirtualDevice("phone-diana",   has_internet=False),
    VirtualDevice("phone-bridge",  has_internet=True),
]


def get_devices() -> list[VirtualDevice]:
    return list(_devices)


def inject_to_alice(packet: MeshPacket):
    """Simulate the sender handing the packet to phone-alice (Step 1 in the demo)."""
    with _lock:
        _devices[0].receive(packet)


def gossip_round():
    """
    One round: every device broadcasts all packets to all other devices.
    TTL decrements; packets at TTL=0 are not forwarded.
    Mirrors MeshSimulatorService.gossipRound().
    """
    with _lock:
        # Collect packets to propagate this round (snapshot)
        to_propagate: list[MeshPacket] = []
        for device in _devices:
            for packet in device.get_packets():
                if packet.ttl > 0:
                    to_propagate.append(
                        MeshPacket(
                            packet_id=packet.packet_id,
                            ttl=packet.ttl - 1,
                            created_at=packet.created_at,
                            ciphertext=packet.ciphertext,
                        )
                    )

        # Broadcast each propagated packet to all devices
        for packet in to_propagate:
            for device in _devices:
                device.receive(packet)


def flush_bridges() -> list[dict]:
    """
    Bridge devices upload all their packets to the backend in parallel.
    Returns a list of ingest results.
    Mirrors MeshSimulatorService.flushBridges().
    """
    results = []
    with _lock:
        bridges = [d for d in _devices if d.has_internet]

    threads = []
    result_store: list[dict] = []
    result_lock = threading.Lock()

    def upload(device: VirtualDevice):
        for packet in device.get_packets():
            response = bridge_ingestion.ingest(packet)
            with result_lock:
                result_store.append({
                    "bridge":   device.device_id,
                    "packet_id": packet.packet_id,
                    **response.model_dump(),
                })

    for bridge in bridges:
        t = threading.Thread(target=upload, args=(bridge,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return result_store


def reset():
    """Clear all device packet stores and the idempotency cache."""
    from service import idempotency
    with _lock:
        for d in _devices:
            d.clear()
    idempotency.reset()


def state() -> list[dict]:
    with _lock:
        return [d.to_dict() for d in _devices]
