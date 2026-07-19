"""Helpers for building and injecting demo packets into the mesh."""

import uuid
import time
import hashlib

from model.schemas import MeshPacket, SendRequest
from crypto.hybrid_crypto import encrypt
from service import mesh_simulator

INITIAL_TTL = 5


def create_and_inject(req: SendRequest) -> MeshPacket:
    pin_hash = hashlib.sha256(req.pin.encode()).hexdigest()
    payload = {
        "sender_id":   req.sender_id,
        "receiver_id": req.receiver_id,
        "amount":      req.amount,
        "pin_hash":    pin_hash,
        "nonce":       str(uuid.uuid4()),
        "signed_at":   int(time.time() * 1000),
    }

    ciphertext = encrypt(payload)

    packet = MeshPacket(
        packet_id=str(uuid.uuid4()),
        ttl=INITIAL_TTL,
        created_at=int(time.time() * 1000),
        ciphertext=ciphertext,
    )

    mesh_simulator.inject_to_alice(packet)
    return packet
