# UPI Offline Mesh

FastAPI demo of offline payment packets moving through a simulated mesh and settling once a bridge device reaches the backend.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Open http://localhost:8080 for the dashboard.

## What it includes

- FastAPI backend with REST endpoints under `/api`
- In-memory SQLite data store
- Hybrid encryption for payment packets
- Idempotent bridge ingestion and settlement
- A small browser dashboard for sending, gossiping, flushing, and resetting packets

## Main routes

| Method | Path                 | Purpose                            |
| ------ | -------------------- | ---------------------------------- |
| `GET`  | `/`                  | Dashboard                          |
| `GET`  | `/api/accounts`      | Account balances                   |
| `GET`  | `/api/transactions`  | Recent settlements                 |
| `GET`  | `/api/mesh/state`    | Device state                       |
| `POST` | `/api/demo/send`     | Create a demo packet               |
| `POST` | `/api/mesh/gossip`   | Run one gossip round               |
| `POST` | `/api/mesh/flush`    | Upload packets from bridge devices |
| `POST` | `/api/mesh/reset`    | Clear the mesh                     |
| `POST` | `/api/bridge/ingest` | Bridge ingest endpoint             |

## Tests

```bash
pytest tests/ -v
```

## Notes

This project is a demo, not a production UPI implementation. It shows the packet flow, encryption, duplicate protection, and settlement logic in a compact FastAPI app.
