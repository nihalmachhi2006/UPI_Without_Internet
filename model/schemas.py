"""
model/schemas.py  — Pydantic request/response schemas.

MeshPacket       : the opaque wire envelope that travels through the mesh
PaymentInstruction: the decrypted inner payload
"""

from pydantic import BaseModel
from typing import Optional


class MeshPacket(BaseModel):
    packet_id: str
    ttl: int
    created_at: int       # epoch millis
    ciphertext: str       # base64-encoded hybrid-encrypted PaymentInstruction


class PaymentInstruction(BaseModel):
    sender_id:   str
    receiver_id: str
    amount:      float
    pin_hash:    str      # SHA-256 of PIN — demo only, not verified server-side
    nonce:       str      # UUID, ensures distinct ciphertexts for identical amounts
    signed_at:   int      # epoch millis; server rejects if older than 24h


class SendRequest(BaseModel):
    sender_id:   str
    receiver_id: str
    amount:      float
    pin:         str


class IngestResponse(BaseModel):
    outcome:        str            # SETTLED | DUPLICATE_DROPPED | INVALID
    packet_hash:    str
    reason:         Optional[str] = None
    transaction_id: Optional[int] = None
