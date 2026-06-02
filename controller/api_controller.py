"""
controller/api_controller.py

All REST API endpoints — mirrors ApiController.Python.
"""

from fastapi import APIRouter, Header
from typing import Optional

from crypto.server_key import ServerKeyHolder
from model.database import get_db
from model.schemas import MeshPacket, SendRequest, IngestResponse
from service import mesh_simulator, bridge_ingestion
from service.demo import create_and_inject

router = APIRouter()


# ── Server Key ────────────────────────────────────────────────────────────────

@router.get("/server-key")
def get_server_key():
    return {"public_key_b64": ServerKeyHolder.get_public_key_b64()}


# ── Accounts ──────────────────────────────────────────────────────────────────

@router.get("/accounts")
def get_accounts():
    with get_db() as cur:
        cur.execute("SELECT id, name, balance FROM accounts ORDER BY id")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Transactions ──────────────────────────────────────────────────────────────

@router.get("/transactions")
def get_transactions():
    with get_db() as cur:
        cur.execute(
            """
            SELECT t.id, t.sender_id, t.receiver_id, t.amount, t.settled_at,
                   s.name AS sender_name, r.name AS receiver_name
            FROM transactions t
            JOIN accounts s ON s.id = t.sender_id
            JOIN accounts r ON r.id = t.receiver_id
            ORDER BY t.id DESC LIMIT 20
            """
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Mesh State ────────────────────────────────────────────────────────────────

@router.get("/mesh/state")
def mesh_state():
    return mesh_simulator.state()


# ── Demo: Sender Phone ────────────────────────────────────────────────────────

@router.post("/demo/send")
def demo_send(req: SendRequest):
    packet = create_and_inject(req)
    return {
        "message": f"Packet injected into mesh via phone-alice",
        "packet_id": packet.packet_id,
        "ttl": packet.ttl,
    }


# ── Mesh Operations ───────────────────────────────────────────────────────────

@router.post("/mesh/gossip")
def gossip():
    mesh_simulator.gossip_round()
    return {"message": "Gossip round complete", "state": mesh_simulator.state()}


@router.post("/mesh/flush")
def flush_bridges():
    results = mesh_simulator.flush_bridges()
    return {"results": results}


@router.post("/mesh/reset")
def reset_mesh():
    mesh_simulator.reset()
    return {"message": "Mesh and idempotency cache cleared"}


# ── Production Ingest Endpoint ────────────────────────────────────────────────

@router.post("/bridge/ingest", response_model=IngestResponse)
def bridge_ingest(
    packet: MeshPacket,
    x_bridge_node_id: Optional[str] = Header(default=None),
    x_hop_count: Optional[int] = Header(default=None),
):
    """
    The production-facing endpoint.  Real bridge nodes POST here.
    Equivalent to /api/bridge/ingest in the Python version.
    """
    return bridge_ingestion.ingest(packet)
