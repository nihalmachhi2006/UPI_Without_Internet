"""
tests/test_mesh.py

Python port of IdempotencyConcurrencyTest.Python.

Tests
-----
1. test_encrypt_decrypt_round_trip
   Sanity-check hybrid encryption is symmetric.

2. test_tampered_ciphertext_is_rejected
   Flip a byte → bridge_ingestion returns INVALID.

3. test_single_packet_delivered_by_three_bridges_settles_exactly_once
   Three threads deliver the same packet simultaneously.
   Asserts exactly 1 SETTLED, 2 DUPLICATE_DROPPED, balance debited once.

Run with:  pytest tests/
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import threading
import base64
import pytest

from crypto.server_key import ServerKeyHolder
from crypto.hybrid_crypto import encrypt, decrypt
from model.database import init_db, seed_accounts, get_db
from model.schemas import MeshPacket, SendRequest
from service import idempotency
from service import bridge_ingestion
from service.demo import create_and_inject


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup():
    """Fresh keypair, DB, and idempotency cache for every test."""
    ServerKeyHolder.initialize()
    init_db()
    seed_accounts()
    idempotency.reset()
    yield


# ── Test 1: Crypto round-trip ─────────────────────────────────────────────────

def test_encrypt_decrypt_round_trip():
    payload = {
        "sender_id":   "alice",
        "receiver_id": "bob",
        "amount":      500.0,
        "pin_hash":    "abc123",
        "nonce":       "test-nonce-1",
        "signed_at":   9_999_999_999_000,
    }
    ciphertext = encrypt(payload)
    recovered  = decrypt(ciphertext)

    assert recovered["sender_id"]   == "alice"
    assert recovered["receiver_id"] == "bob"
    assert recovered["amount"]      == 500.0
    assert recovered["nonce"]       == "test-nonce-1"


# ── Test 2: Tampered ciphertext rejected ──────────────────────────────────────

def test_tampered_ciphertext_is_rejected():
    import uuid, time
    payload = {
        "sender_id":   "alice",
        "receiver_id": "bob",
        "amount":      100.0,
        "pin_hash":    "x",
        "nonce":       str(uuid.uuid4()),
        "signed_at":   int(time.time() * 1000),
    }
    good_ct = encrypt(payload)

    # Flip bytes somewhere in the AES ciphertext region (past the RSA block)
    raw = bytearray(base64.b64decode(good_ct))
    raw[270] ^= 0xFF          # flip a byte well inside the AES-GCM region
    tampered_ct = base64.b64encode(bytes(raw)).decode()

    packet = MeshPacket(
        packet_id="tampered-packet",
        ttl=3,
        created_at=int(time.time() * 1000),
        ciphertext=tampered_ct,
    )
    result = bridge_ingestion.ingest(packet)
    assert result.outcome == "INVALID", f"Expected INVALID, got {result.outcome}"


# ── Test 3: Three bridges — exactly one settles ───────────────────────────────

def test_single_packet_delivered_by_three_bridges_settles_exactly_once():
    import uuid, time

    payload = {
        "sender_id":   "alice",
        "receiver_id": "bob",
        "amount":      200.0,
        "pin_hash":    "x",
        "nonce":       str(uuid.uuid4()),
        "signed_at":   int(time.time() * 1000),
    }
    ciphertext = encrypt(payload)
    packet = MeshPacket(
        packet_id=str(uuid.uuid4()),
        ttl=3,
        created_at=int(time.time() * 1000),
        ciphertext=ciphertext,
    )

    # Read Alice's balance before
    with get_db() as cur:
        cur.execute("SELECT balance FROM accounts WHERE id='alice'")
        balance_before = cur.fetchone()["balance"]

    # Three threads deliver the same packet simultaneously
    results = []
    lock = threading.Lock()

    def deliver():
        r = bridge_ingestion.ingest(packet)
        with lock:
            results.append(r.outcome)

    threads = [threading.Thread(target=deliver) for _ in range(3)]
    for t in threads: t.start()
    for t in threads: t.join()

    settled   = results.count("SETTLED")
    duplicate = results.count("DUPLICATE_DROPPED")

    assert settled   == 1, f"Expected 1 SETTLED, got {settled}. Results: {results}"
    assert duplicate == 2, f"Expected 2 DUPLICATE_DROPPED, got {duplicate}. Results: {results}"

    # Alice should be debited exactly once
    with get_db() as cur:
        cur.execute("SELECT balance FROM accounts WHERE id='alice'")
        balance_after = cur.fetchone()["balance"]

    assert abs((balance_before - balance_after) - 200.0) < 0.01, (
        f"Expected debit of 200.0, got {balance_before - balance_after}"
    )
