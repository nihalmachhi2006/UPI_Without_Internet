"""Simulation of the mesh devices and gossip flow."""

import threading
from model.schemas import MeshPacket
from service.virtual_device import VirtualDevice
from service import bridge_ingestion

_lock = threading.Lock()

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
    with _lock:
        _devices[0].receive(packet)


def gossip_round():
    with _lock:
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

        for packet in to_propagate:
            for device in _devices:
                device.receive(packet)


def flush_bridges() -> list[dict]:
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
