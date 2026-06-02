"""
UPI Offline Mesh — Python/FastAPI port
Original Python/Spring Boot project by perryvegehan
Converted to Python by: you
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from model.database import init_db, seed_accounts
from crypto.server_key import ServerKeyHolder
from controller.api_controller import router as api_router
from controller.dashboard_controller import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🔐 Generating RSA-2048 keypair...")
    ServerKeyHolder.initialize()
    print("🗄️  Initialising in-memory database...")
    init_db()
    seed_accounts()
    print("✅ UPI Mesh server started — open http://localhost:8080")
    yield
    # Shutdown
    print("👋 Shutting down UPI Mesh server.")


app = FastAPI(
    title="UPI Offline Mesh",
    description="Offline UPI payments routed through a mesh network",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api")
app.include_router(dashboard_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
