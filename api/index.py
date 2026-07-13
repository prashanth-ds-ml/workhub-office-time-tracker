from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from app import app as workhub_app

app = FastAPI()
app.mount("/api", workhub_app)
