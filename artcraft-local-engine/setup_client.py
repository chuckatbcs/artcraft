import json
from pathlib import Path
from config import SETTINGS_DIR

SESSION_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX3Rva2VuIjoic2Vzc2lvbl9qNHdwcTYydnpwNXltZ3FjZDRodHF0cTMiLCJ1c2VyX3Rva2VuIjoidXNlcl94c2tmd2pleWY5dm16IiwidmVyc2lvbiI6IjMifQ.Qt2-0RdJrP6Y3AdzildvXyWTkA7i2pkeZ1B52gwFNYM"
AVT_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJhdnRfdG9rZW4iOiJhdnRfazdrZWNxbWg3eTkzZXlzcmVieDBkbTRrcGJ3OSIsImNvb2tpZV92ZXJzaW9uIjoiMSJ9.OjVza0eheW-6gLZhm1JFUCF9xjJG6kzOo9DPXytZEy8"

def configure_artcraft_desktop():
    """Configures ArtCraft desktop client to route all requests to the local engine and auto-login."""
    # 1. Update env_configs.json to route to localhost:8000
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    config_path = SETTINGS_DIR / "env_configs.json"
    
    config_data = {
        "version": "1",
        "storyteller_host": "localhost",
        "storyteller_port": 8000
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
        
    print(f"[ArtCraft Setup] Desktop configuration written to: {config_path}")
    print("[ArtCraft Setup] storyteller_host set to 'localhost:8000'.")

    # 2. Write credential files to Artcraft/credentials
    creds_dir = SETTINGS_DIR.parent / "credentials"
    creds_dir.mkdir(parents=True, exist_ok=True)
    
    session_file = creds_dir / "artcraft_session.txt"
    avt_file = creds_dir / "artcraft_avt.txt"
    
    with open(session_file, "w", encoding="utf-8") as f:
        f.write(SESSION_JWT)
    with open(avt_file, "w", encoding="utf-8") as f:
        f.write(AVT_JWT)
    print(f"[ArtCraft Setup] Local credential tokens saved to {creds_dir}")

    # 3. Write persistent cookies for localhost into ai.artcraft.app/.cookies
    local_app_data = Path.home() / "AppData" / "Local" / "ai.artcraft.app"
    if local_app_data.exists():
        cookies_file = local_app_data / ".cookies"
        cookies_data = [
            {
                "raw_cookie": f"session={SESSION_JWT}; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:33:35 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "localhost"},
                "expires": {"AtUtc": "2046-10-12T08:34:01Z"}
            },
            {
                "raw_cookie": f"visitor={AVT_JWT}; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:32:24 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "localhost"},
                "expires": {"AtUtc": "2046-10-12T08:32:50Z"}
            },
            {
                "raw_cookie": f"session={SESSION_JWT}; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:33:35 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "127.0.0.1"},
                "expires": {"AtUtc": "2046-10-12T08:34:01Z"}
            },
            {
                "raw_cookie": f"visitor={AVT_JWT}; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:32:24 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "127.0.0.1"},
                "expires": {"AtUtc": "2046-10-12T08:32:50Z"}
            },
            {
                "raw_cookie": f"session={SESSION_JWT}; SameSite=None; Secure; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:33:35 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "api.storyteller.ai"},
                "expires": {"AtUtc": "2046-10-12T08:34:01Z"}
            },
            {
                "raw_cookie": f"visitor={AVT_JWT}; SameSite=None; Secure; Path=/; Max-Age=630720000; Expires=Fri, 12 Oct 2046 08:32:24 GMT",
                "path": ["/", True],
                "domain": {"HostOnly": "api.storyteller.ai"},
                "expires": {"AtUtc": "2046-10-12T08:32:50Z"}
            }
        ]
        with open(cookies_file, "w", encoding="utf-8") as f:
            json.dump(cookies_data, f)
        print(f"[ArtCraft Setup] Cookie jar synchronized at {cookies_file}")

if __name__ == "__main__":
    configure_artcraft_desktop()
