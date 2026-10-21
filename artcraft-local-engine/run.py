import os
import sys
from pathlib import Path

# Add directory to sys.path
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import uvicorn
from config import HOST, PORT
import server

if __name__ == "__main__":
    print(f"==================================================")
    print(f"  ArtCraft Local Unlocked Engine v1.0.0")
    print(f"  Zero Paywall * Infinite Credits * Local Models")
    print(f"  Listening on: http://{HOST}:{PORT}")
    print(f"==================================================")
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")
