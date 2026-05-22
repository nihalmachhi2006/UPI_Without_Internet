"""
service/bridge_ingestion.py

BridgeIngestionService — THE server-side pipeline:

  1. Hash the ciphertext (SHA-256)
  2. Claim the hash (idempotency — drops duplicates here, before any work)
  3. Decrypt with hybrid RSA+AES  (rejects tampered packets)
  4. Freshness check  (rejects replays older than 24h)
  5. Settle (debit + credit + ledger)

Mirrors BridgeIngestionService.java exactly.
"""

import time
import logging

from model.schemas import MeshPacket, PaymentInstruction, IngestResponse
from crypto.hybrid_crypto import decrypt, ciphertext_hash
from service import idempotency, settlement

logger = logging.getLogger(__name__)

FRESHNESS_WINDOW_MS = 86_400 * 1000   # 24 hours in milliseconds


def ingest(packet: MeshPacket) -> IngestResponse:
    """Process one MeshPacket delivered by a bridge node."""

    # ── Step 1: Hash the ciphertext ──────────────────────────────────────────
    p_hash = ciphertext_hash(packet.ciphertext)

    # ── Step 2: Idempotency claim ─────────────────────────────────────────────
    if not idempotency.claim(p_hash):
        logger.info("DUPLICATE_DROPPED packet_hash=%s", p_hash[:16])
        return IngestResponse(
            outcome="DUPLICATE_DROPPED",
            packet_hash=p_hash,
            reason="Already seen this ciphertext",
        )

    # ── Step 3: Decrypt ───────────────────────────────────────────────────────
    try:
        payload = decrypt(packet.ciphertext)
    except Exception as exc:
        logger.warning("INVALID — decryption failed: %s", exc)
        return IngestResponse(
            outcome="INVALID",
            packet_hash=p_hash,
            reason=f"Decryption failed: {exc}",
        )

    instruction = PaymentInstruction(**payload)

    # ── Step 4: Freshness check ───────────────────────────────────────────────
    age_ms = int(time.time() * 1000) - instruction.signed_at
    if age_ms > FRESHNESS_WINDOW_MS:
        logger.warning("INVALID — packet too old (%d ms)", age_ms)
        return IngestResponse(
            outcome="INVALID",
            packet_hash=p_hash,
            reason=f"Packet is {age_ms // 1000}s old (max {FRESHNESS_WINDOW_MS // 1000}s)",
        )

    # ── Step 5: Settle ────────────────────────────────────────────────────────
    try:
        tx_id = settlement.settle(instruction, p_hash)
    except settlement.InsufficientFundsError as exc:
        logger.warning("INVALID — insufficient funds: %s", exc)
        return IngestResponse(
            outcome="INVALID",
            packet_hash=p_hash,
            reason=str(exc),
        )
    except Exception as exc:
        logger.error("INVALID — settlement error: %s", exc)
        return IngestResponse(
            outcome="INVALID",
            packet_hash=p_hash,
            reason=str(exc),
        )

    logger.info(
        "SETTLED tx=%s  %s→%s  ₹%.2f",
        tx_id, instruction.sender_id, instruction.receiver_id, instruction.amount,
    )
    return IngestResponse(
        outcome="SETTLED",
        packet_hash=p_hash,
        transaction_id=tx_id,
    )
