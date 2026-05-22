"""
controller/dashboard_controller.py — serves the interactive dashboard at /.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import os

router = APIRouter()

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard.html")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with open(_TEMPLATE_PATH, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
