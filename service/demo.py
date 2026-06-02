"""
service/demo.py

DemoService — pretends to be the sender's phone.
Builds a PaymentInstruction, encrypts it, wraps it in a MeshPacket,
and hands it to phone-alice for mesh injection.
Mirrors DemoService.Python.
"""

import uuid
import time
import hashlib

from model.schemas import MeshPacket, SendRequest
from crypto.hybrid_crypto import encrypt
from service import mesh_simulator

INITIAL_TTL = 5


def create_and_inject(req: SendRequest) -> MeshPacket:
    """
    Simulate the sender phone encrypting a payment and injecting it into the mesh.
    """
    # Build the inner payload
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
