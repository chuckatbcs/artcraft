import os
import json
import uuid
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import SETTINGS_DIR, MEDIA_DIR, ARTCRAFT_ROOT, CHECKPOINTS_DIR

PROVIDERS_CONFIG_PATH = SETTINGS_DIR / "ai_providers.json"

DEFAULT_PROVIDERS_CONFIG = {
    "active_provider": "local_comfyui",
    "combine_all_enabled": True,
    "providers": {
        "local_comfyui": {
            "type": "comfyui",
            "name": "Local GPU (ComfyUI / RTX 4060 Ti)",
            "url": "http://127.0.0.1:20140",
            "checkpoints_dir": str(CHECKPOINTS_DIR),
            "active_checkpoint": "sd_xl_base_1.0.safetensors",
            "enabled": True,
        },
        "openai": {
            "type": "openai",
            "name": "OpenAI (Direct / Subscription)",
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "organization_id": "",
            "enabled_models": ["dall-e-3", "dall-e-2"],
            "default_image_model": "dall-e-3",
            "enabled": False,
        },
        "openrouter": {
            "type": "openrouter",
            "name": "OpenRouter",
            "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "enabled_models": [
                "black-forest-labs/flux-1-dev",
                "black-forest-labs/flux-1-schnell",
                "recraft-ai/recraft-v3",
                "stabilityai/stable-diffusion-xl-base-1.0"
            ],
            "default_image_model": "black-forest-labs/flux-1-dev",
            "default_text_model": "anthropic/claude-3.5-sonnet",
            "enabled": False,
        },
        "omniroute": {
            "type": "omniroute",
            "name": "OmniRoute Gateway",
            "api_key": "",
            "base_url": "http://localhost:20128/v1",
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
                for k, v in DEFAULT_PROVIDERS_CONFIG["providers"].items():
                    if k not in saved.get("providers", {}):
                        saved.setdefault("providers", {})[k] = v
                if "combine_all_enabled" not in saved:
                    saved["combine_all_enabled"] = True
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

def test_provider_connection(provider_key: str) -> Dict[str, Any]:
    """Tests connection to a provider and returns status details."""
    cfg = get_providers_config()
    prov = cfg.get("providers", {}).get(provider_key)
    if not prov:
        return {"success": False, "error": f"Unknown provider: {provider_key}"}

    if provider_key == "local_comfyui":
        url = prov.get("url", "http://127.0.0.1:20140").rstrip("/")
        try:
            req = urllib.request.Request(f"{url}/system_stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                devices = data.get("devices", [{}])
                gpu_name = devices[0].get("name", "NVIDIA GPU") if devices else "Local GPU"
                return {"success": True, "message": f"Connected to ComfyUI ({gpu_name})"}
        except Exception as e:
            return {"success": False, "error": f"Cannot reach ComfyUI on {url}: {e}"}

    base_url = prov.get("base_url", "").rstrip("/")
    api_key = prov.get("api_key", "")
    if not base_url:
        return {"success": False, "error": "Base URL not configured"}

    headers = {"User-Agent": "ArtCraft-Local-Engine/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if prov.get("organization_id"):
        headers["OpenAI-Organization"] = prov["organization_id"]

    try:
        req = urllib.request.Request(f"{base_url}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            count = len(data.get("data", []))
            return {"success": True, "message": f"Verified! Provider returned {count} available models."}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def query_remote_models(provider_key: str) -> List[Dict[str, Any]]:
    """Fetches available models from remote OpenRouter, OpenAI, OmniRoute, or custom endpoint."""
    cfg = get_providers_config()
    prov = cfg.get("providers", {}).get(provider_key)
    if not prov or not prov.get("enabled", True):
        return []

    base_url = prov.get("base_url", "").rstrip("/")
    api_key = prov.get("api_key", "")
    if not base_url:
        return []

    # If the provider has explicitly enabled models listed, return those
    preset_models = prov.get("enabled_models", [])
    
    # Try fetching remote list
    headers = {"User-Agent": "ArtCraft-Local-Engine/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if prov.get("organization_id"):
        headers["OpenAI-Organization"] = prov["organization_id"]

    try:
        req = urllib.request.Request(f"{base_url}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("data", [])
            out = []
            for m in raw:
                m_id = m.get("id") if isinstance(m, dict) else str(m)
                # Filter for image/video relevant models if list is huge
                if preset_models and m_id not in preset_models:
                    continue
                out.append({
                    "model": m_id,
                    "model_creator": provider_key,
                    "full_name": f"{m_id} ({prov.get('name', provider_key)})",
                    "text_prompt_supported": True,
                    "text_prompt_max_length": 8192,
                    "is_disabled": False,
                })
            if out:
                return out
    except Exception as e:
        print(f"[ProviderRouter] Failed to query {provider_key} models: {e}")

    # Fallback to configured preset list
    out = []
    for m_id in preset_models:
        out.append({
            "model": m_id,
            "model_creator": provider_key,
            "full_name": f"{m_id} ({prov.get('name', provider_key)})",
            "text_prompt_supported": True,
            "text_prompt_max_length": 8192,
            "is_disabled": False,
        })
    return out

def generate_remote_image(prompt: str, model: str = None, provider_key: str = None, output_path: Path = None) -> Optional[Path]:
    """Generates an image via OpenAI, OpenRouter, OmniRoute, or an OpenAI-compatible endpoint."""
    if output_path is None:
        output_path = MEDIA_DIR / f"med_{uuid.uuid4().hex[:16]}.png"

    cfg = get_providers_config()
    
    # Determine target provider
    prov_key = provider_key
    if not prov_key:
        # Infer provider from model name
        if model:
            if "dall-e" in model.lower():
                prov_key = "openai"
            elif any(x in model.lower() for x in ["flux", "claude", "recraft", "midjourney", "stable-diffusion"]):
                prov_key = "openrouter" if cfg.get("providers", {}).get("openrouter", {}).get("enabled") else "openai"
        if not prov_key:
            prov_key = cfg.get("active_provider", "openai")

    prov = cfg.get("providers", {}).get(prov_key)
    if not prov or not prov.get("enabled", True):
        # Fallback to active provider
        prov_key = cfg.get("active_provider", "local_comfyui")
        prov = cfg.get("providers", {}).get(prov_key, {})

    base_url = prov.get("base_url", "").rstrip("/")
    api_key = prov.get("api_key", "")
    chosen_model = model or prov.get("default_image_model", "dall-e-3")

    url = f"{base_url}/images/generations"
    payload = json.dumps({
        "prompt": prompt,
        "model": chosen_model,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json"
    }).encode("utf-8")

    headers = {"Content-Type": "application/json", "User-Agent": "ArtCraft-Local-Engine/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if prov.get("organization_id"):
        headers["OpenAI-Organization"] = prov["organization_id"]

    try:
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=75) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            item = data["data"][0]
            b64 = item.get("b64_json")
            if b64:
                img_data = base64.b64decode(b64)
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path
            img_url = item.get("url")
            if img_url:
                urllib.request.urlretrieve(img_url, str(output_path))
                return output_path
    except Exception as e:
        print(f"[ProviderRouter] Remote image generation failed on {prov.get('name', prov_key)} with model {chosen_model}: {e}")
        return None
