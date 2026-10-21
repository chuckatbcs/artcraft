import os
from pathlib import Path

# Server network configuration
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://localhost:{PORT}"

# Local ComfyUI integration (managed via PM2 on PCGamer)
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:20140")

# Local directories
HOME_DIR = Path(os.environ.get("USERPROFILE", r"C:\Users\cblac"))
ARTCRAFT_ROOT = HOME_DIR / "Artcraft"
SETTINGS_DIR = ARTCRAFT_ROOT / "settings"
STATE_DIR = ARTCRAFT_ROOT / "state"
DOWNLOADS_DIR = ARTCRAFT_ROOT / "downloads"
ASSETS_DIR = ARTCRAFT_ROOT / "assets"
MEDIA_DIR = ASSETS_DIR / "media"

# Ensure essential runtime directories exist
for d in [ARTCRAFT_ROOT, SETTINGS_DIR, STATE_DIR, DOWNLOADS_DIR, ASSETS_DIR, MEDIA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Model Checkpoints directory (configurable via env var CHECKPOINTS_DIR, falls back to ComfyUI or local folder)
env_ckpt = os.environ.get("CHECKPOINTS_DIR")
if env_ckpt and Path(env_ckpt).exists():
    CHECKPOINTS_DIR = Path(env_ckpt)
elif Path(r"B:\AI Directory\ComfyUI\models\checkpoints").exists():
    CHECKPOINTS_DIR = Path(r"B:\AI Directory\ComfyUI\models\checkpoints")
else:
    CHECKPOINTS_DIR = ARTCRAFT_ROOT / "models"
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
