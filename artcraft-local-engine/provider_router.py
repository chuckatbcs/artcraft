import os
import json
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import SETTINGS_DIR, MEDIA_DIR, ARTCRAFT_ROOT, CHECKPOINTS_DIR

PROVIDERS_CONFIG_PATH = SETTINGS_DIR / "ai_providers.json"

DEFAULT_PROVIDERS_CONFIG = {
    "active_provider": "local_comfyui",
    "providers": {
        "local_comfyui": {
            "type": "comfyui",
            "name": "Local GPU (ComfyUI / RTX 4060 Ti)",
            "url": "http://127.0.0.1:20140",
            "checkpoints_dir": str(CHECKPOINTS_DIR),
            "enabled": True,
        },
        "openrouter": {
            "type": "openrouter",
            "name": "OpenRouter",
            "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "default_image_model": "black-forest-labs/flux-1-dev",
            "default_text_model": "anthropic/claude-3.5-sonnet",
            "enabled": False,
        },
        "omniroute": {
            "type": "omniroute",
            "name": "OmniRoute",
            "api_key": "",
            "base_url": "http://localhost:8080/v1",
            "default_image_model": "flux-1-schnell",
            "default_text_model": "gpt-4o",
            "enabled": False,
        },
        "custom_openai": {
            "type": "openai_compatible",
            "name": "Custom OpenAI / Ollama / LocalAI",
            "api_key": "",
            "base_url": "http://localhost:11434/v1",
            "default_image_model": "stable-diffusion",
            "default_text_model": "llama3",
            "enabled": False,
        },
    },
}

def get_providers_config() -> Dict[str, Any]:
    if PROVIDERS_CONFIG_PATH.exists():
        try:
            with open(PROVIDERS_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # Ensure all default provider keys exist
                for k, v in DEFAULT_PROVIDERS_CONFIG["providers"].items():
                    if k not in saved.get("providers", {}):
                        saved.setdefault("providers", {})[k] = v
                return saved
        except Exception:
            pass
    save_providers_config(DEFAULT_PROVIDERS_CONFIG)
    return DEFAULT_PROVIDERS_CONFIG

def save_providers_config(cfg: Dict[str, Any]):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROVIDERS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_active_provider_info() -> Dict[str, Any]:
    cfg = get_providers_config()
    active_key = cfg.get("active_provider", "local_comfyui")
    prov = cfg.get("providers", {}).get(active_key, DEFAULT_PROVIDERS_CONFIG["providers"]["local_comfyui"])
    return {"key": active_key, **prov}

def set_active_provider(provider_key: str):
    cfg = get_providers_config()
    if provider_key in cfg.get("providers", {}):
        cfg["active_provider"] = provider_key
        cfg["providers"][provider_key]["enabled"] = True
        save_providers_config(cfg)
        return True
    return False

def update_provider_details(provider_key: str, updates: Dict[str, Any]):
    cfg = get_providers_config()
    if provider_key in cfg.get("providers", {}):
        for k, v in updates.items():
            if v is not None:
                cfg["providers"][provider_key][k] = v
        save_providers_config(cfg)
        return True
    return False

def query_remote_models(provider_key: str) -> List[Dict[str, Any]]:
    """Fetches available models from a remote OpenRouter, OmniRoute, or OpenAI-compatible provider."""
    cfg = get_providers_config()
    prov = cfg.get("providers", {}).get(provider_key)
    if not prov:
        return []
        
    base_url = prov.get("base_url", "").rstrip("/")
    api_key = prov.get("api_key", "")
    
    if not base_url:
        return []
        
    try:
        req = urllib.request.Request(f"{base_url}/models")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("User-Agent", "ArtCraft-Local-Engine/1.0")
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = data.get("data", [])
            out = []
            for m in raw_models:
                m_id = m.get("id") if isinstance(m, dict) else str(m)
                out.append({
                    "model": m_id,
                    "model_creator": provider_key,
                    "full_name": f"{m_id} ({prov.get('name', provider_key)})",
                    "text_prompt_supported": True,
                    "text_prompt_max_length": 8192,
                    "is_disabled": False
                })
            return out
    except Exception as e:
        print(f"[ProviderRouter] Failed to query {provider_key} models ({e}). Using default presets.")
        return []

def generate_remote_image(prompt: str, model: str = None, output_path: Path = None) -> Optional[Path]:
    """Generates an image via OpenRouter, OmniRoute, or an OpenAI-compatible API."""
    if output_path is None:
        output_path = MEDIA_DIR / f"med_{uuid.uuid4().hex[:16]}.png"
        
    prov = get_active_provider_info()
    base_url = prov.get("base_url", "").rstrip("/")
    api_key = prov.get("api_key", "")
    chosen_model = model or prov.get("default_image_model", "flux-1-schnell")
    
    # Try OpenAI /images/generations endpoint
    url = f"{base_url}/images/generations"
    payload = json.dumps({
        "prompt": prompt,
        "model": chosen_model,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json"
    }).encode("utf-8")
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    try:
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            import base64
            b64 = data["data"][0].get("b64_json")
            if b64:
                img_data = base64.b64decode(b64)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path
            img_url = data["data"][0].get("url")
            if img_url:
                urllib.request.urlretrieve(img_url, str(output_path))
                return output_path
    except Exception as e:
        print(f"[ProviderRouter] Remote image generation failed on {prov.get('name')}: {e}")
        return None
