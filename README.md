# UPI Offline Mesh — Python/FastAPI Port

> **Python conversion** of [perryvegehan/UPI_Without_Internet](https://github.com/perryvegehan/UPI_Without_Internet) (Java/Spring Boot).  
> All original logic, architecture, and cryptography preserved — zero Java required.

A FastAPI backend that demonstrates **offline UPI payments routed through a Bluetooth-style mesh network**. You're in a basement with zero connectivity. You encrypt a payment, broadcast it to nearby phones, and the packet hops device-to-device until _some_ phone walks outside, gets 4G, and silently uploads it to this backend. The backend decrypts, deduplicates, and settles — exactly once.

---

## What this demo proves

1. **A payment can travel through untrusted intermediaries** without any of them being able to read or tamper with it. (Hybrid RSA-OAEP + AES-256-GCM encryption.)
2. **Even if the same payment reaches the backend simultaneously through multiple bridge nodes, it settles exactly once.** (Idempotency via atomic compare-and-set on the ciphertext hash.)
3. **A tampered or replayed packet is rejected** before it touches the ledger.

---

## Tech Stack

| Layer | Java original | Python port |
|-------|--------------|-------------|
| Web framework | Spring Boot 3.3 | **FastAPI + Uvicorn** |
| Database | H2 in-memory (JPA) | **SQLite in-memory (sqlite3)** |
| Idempotency store | `ConcurrentHashMap` | **`dict` + `threading.Lock`** |
| Crypto | JCA (RSA + AES) | **`cryptography` library** |
| Schema validation | Java records | **Pydantic v2** |
| Tests | JUnit 5 | **pytest** |
| Templates | Thymeleaf | **Plain HTML served by FastAPI** |

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python main.py
```

Open **http://localhost:8080** — you'll get a dark interactive dashboard.

See [SETUP.md](SETUP.md) for the full step-by-step guide including troubleshooting.

---

## Project Structure

```
upi_offline_mesh/
├── main.py                          FastAPI app entry point + lifespan hooks
├── requirements.txt
├── SETUP.md                         Quick setup guide
│
├── crypto/
│   ├── server_key.py                RSA-2048 keypair singleton (startup-generated)
│   └── hybrid_crypto.py             RSA-OAEP + AES-256-GCM encrypt/decrypt + hash
│
├── model/
│   ├── database.py                  SQLite init, seed, get_db() context manager
│   └── schemas.py                   Pydantic: MeshPacket, PaymentInstruction, etc.
│
├── service/
│   ├── idempotency.py               Atomic claim — dict + Lock (≈ Redis SETNX)
│   ├── settlement.py                @Transactional debit + credit + ledger insert
│   ├── bridge_ingestion.py          THE pipeline: hash→claim→decrypt→freshness→settle
│   ├── virtual_device.py            One simulated phone in the mesh
│   ├── mesh_simulator.py            Gossip protocol + bridge flush
│   └── demo.py                      Simulates the sender phone encrypting a payment
│
├── controller/
│   ├── api_controller.py            All /api/* REST endpoints
│   └── dashboard_controller.py      Serves dashboard HTML at /
│
├── templates/
│   └── dashboard.html               Interactive dark demo dashboard
│
└── tests/
    └── test_mesh.py                 3 tests (round-trip, tamper, concurrency)
```

---

## The Demo Flow

The dashboard has four step buttons:

### Step 1 — Inject into Mesh
Fill in sender, receiver, amount, PIN and click **📤 Inject into Mesh**.

The server simulates the sender's phone: builds a `PaymentInstruction` with a unique nonce and timestamp, encrypts it with the server's RSA public key (hybrid encryption), wraps it in a `MeshPacket` with TTL=5, and hands it to `phone-alice`.

### Step 2 — Gossip Rounds
Click **🔄 Run Gossip Round** once or twice.

Each round every device that holds a packet broadcasts it to every other device. TTL decrements per hop. After two rounds all five virtual phones hold the packet.

### Step 3 — Bridge Uploads
Click **📡 Bridges Upload**.

`phone-bridge` is the only device with `has_internet=True`. It POSTs every packet it holds to `/api/bridge/ingest`. Watch the balances update and a new row appear in the ledger.

### Reset
Click **🗑️ Clear Mesh** to wipe all device stores and the idempotency cache.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     SENDER PHONE (offline)                   │
│  PaymentInstruction { sender, receiver, amount, nonce, time }│
│              │                                               │
│              ▼  encrypt (RSA-OAEP + AES-256-GCM)            │
│   MeshPacket { packet_id, ttl, created_at, ciphertext }      │
└──────────────────────────┬───────────────────────────────────┘
                           │  Bluetooth gossip (simulated)
                           ▼
     ┌────────┐  hop  ┌────────┐  hop  ┌─────────┐
     │stranger│──────▶│stranger│──────▶│ bridge  │◀─ walks outside
     └────────┘       └────────┘       └────┬────┘  gets 4G
                                            │
                                            ▼ HTTPS POST
┌──────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (this project)                  │
│                                                              │
│  /api/bridge/ingest                                          │
│    [1] SHA-256(ciphertext) → packet_hash                     │
│    [2] idempotency.claim(hash)  ← atomic; duplicates dropped │
│    [3] hybrid_crypto.decrypt()  ← tampered = exception       │
│    [4] freshness check: signed_at within 24h                 │
│    [5] settlement.settle()  ← debit + credit + ledger        │
└──────────────────────────────────────────────────────────────┘
```

---

## The Three Hard Problems

### 1. Untrusted intermediaries
A stranger's phone carries your payment. **Solution: Hybrid encryption (RSA-OAEP + AES-256-GCM).** Only the server holds the private key. AES-GCM is _authenticated_ encryption — one flipped bit causes decryption to throw `InvalidTag`, so the server can never process tampered data.

### 2. Duplicate storms
Three bridges hold the same packet and POST simultaneously. **Solution: Atomic compare-and-set on the ciphertext hash.** `dict` + `threading.Lock` (in Python) / `ConcurrentHashMap.putIfAbsent` (in Java) — exactly one thread wins, the rest are short-circuited as `DUPLICATE_DROPPED` before any DB work. In production: Redis `SET key NX EX 86400`.

### 3. Replay attacks
An attacker replays a captured ciphertext. **Solution:** The inner payload contains a `signed_at` timestamp (server rejects packets older than 24h) and a `nonce` UUID (each unique payment has a distinct ciphertext). A replayed packet is byte-identical → same hash → caught by the idempotency cache.

---

## Running the Tests

```bash
pytest tests/ -v
```

| Test | What it checks |
|------|---------------|
| `test_encrypt_decrypt_round_trip` | Hybrid encryption is symmetric |
| `test_tampered_ciphertext_is_rejected` | Flipped byte → `INVALID` outcome |
| `test_single_packet_delivered_by_three_bridges_settles_exactly_once` | 3 threads, 1 packet → exactly 1 `SETTLED`, 2 `DUPLICATE_DROPPED`, balance debited once |

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/api/server-key` | RSA public key (base64 DER) |
| `GET` | `/api/accounts` | All accounts and balances |
| `GET` | `/api/transactions` | Last 20 transactions |
| `GET` | `/api/mesh/state` | Per-device packet counts |
| `POST` | `/api/demo/send` | Simulate sender phone |
| `POST` | `/api/mesh/gossip` | One gossip round |
| `POST` | `/api/mesh/flush` | Bridge nodes upload to backend |
| `POST` | `/api/mesh/reset` | Clear mesh + idempotency cache |
| `POST` | `/api/bridge/ingest` | **Production endpoint** |

Interactive Swagger docs: **http://localhost:8080/docs**

### `/api/bridge/ingest` request / response

```json
// Request body
{
  "packet_id": "550e8400-e29b-41d4-a716-446655440000",
  "ttl": 2,
  "created_at": 1730000000000,
  "ciphertext": "base64-encoded-RSA-and-AES-blob"
}

// Response
{
  "outcome": "SETTLED",           // or "DUPLICATE_DROPPED" or "INVALID"
  "packet_hash": "a3f8c9...",
  "reason": null,                 // populated on INVALID
  "transaction_id": 42            // populated on SETTLED
}
```

---

## What's NOT Real (Production Delta)

| Demo | Production |
|------|-----------|
| SQLite in-memory DB | PostgreSQL / MySQL with replicas |
| `dict` + `Lock` for idempotency | Redis `SET NX EX 86400` |
| RSA keypair regenerated on startup | Private key in HSM (AWS KMS / Vault) |
| Software-simulated mesh | Real BLE GATT or Wi-Fi Direct |
| `DemoService` pretends to be sender phone | Same code on Android (Kotlin port) |
| No auth on `/api/bridge/ingest` | Mutual TLS or signed bridge-node certificates |
| In-memory accounts | Real KYC'd users, real UPI VPAs, real PIN verification |

---

## Honest Limitations of the Concept

1. **No offline balance proof.** The receiver can't verify the sender has funds until the packet settles at the backend. A sender with ₹0 can send a packet that will be `REJECTED` later.
2. **Double-spend is possible offline.** A sender can dispatch two packets for the same balance to different people; whichever settles first wins. (This is why real offline UPI Lite uses a pre-funded hardware wallet.)
3. **Bluetooth in practice is hard.** Background BLE on Android 8+ is throttled; iOS peripheral mode is restricted. This demo skips that entirely.

For a portfolio project, present this honestly as **"mesh-routed deferred settlement"** rather than real-time offline UPI. The cryptography and idempotency engineering is real and worth showcasing.

---

## Credits

Original Java/Spring Boot implementation by [perryvegehan](https://github.com/perryvegehan/UPI_Without_Internet).  
Python port preserves all architecture decisions, cryptographic design, and the three core proofs.

## License

Demo / educational code. Use freely for learning.
