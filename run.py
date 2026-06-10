#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
Config.ensure_dirs()

port = int(os.getenv("PORT", "8080"))
print(f"\n  CerebraFX Studio")
print(f"  ─────────────")
print(f"  Abre http://127.0.0.1:{port} en tu navegador\n")

import uvicorn
uvicorn.run("web.server:app", host="127.0.0.1", port=port, log_level="info")
