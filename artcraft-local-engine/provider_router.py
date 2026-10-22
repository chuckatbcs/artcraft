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

def normalize_base_url(url: str, provider_key: str = "") -> str:
    """Sanitizes local URLs: converts unintended HTTPS to HTTP, fixes Windows IPv6 hostnames."""
    if not url:
        return url
    url = url.strip()
    # OmniRoute on port 20128: plain HTTP daemon bound to IPv4 (0.0.0.0)
    if "20128" in url or provider_key == "omniroute":
        if url.startswith("https://"):
            url = "http://" + url[len("https://"):]
        url = url.replace("pcgamer:20128", "127.0.0.1:20128").replace("localhost:20128", "127.0.0.1:20128")
        if not url.endswith("/v1") and not url.endswith("/v1/"):
            url = url.rstrip("/") + "/v1"
    elif "20140" in url or provider_key == "local_comfyui":
        if url.startswith("https://"):
            url = "http://" + url[len("https://"):]
        url = url.replace("pcgamer:20140", "127.0.0.1:20140").replace("localhost:20140", "127.0.0.1:20140")
    return url.rstrip("/")

def update_provider_details(provider_key: str, updates: Dict[str, Any]):
    cfg = get_providers_config()
    if provider_key in cfg.get("providers", {}):
        for k, v in updates.items():
            if v is not None:
                if k in ("base_url", "url"):
                    v = normalize_base_url(v, provider_key)
                cfg["providers"][provider_key][k] = v
        save_providers_config(cfg)
        return True
    return False

def test_provider_connection(provider_key: str, override_base_url: str = None, override_api_key: str = None) -> Dict[str, Any]:
    """Tests connection to a provider and returns status details."""
    cfg = get_providers_config()
    prov = cfg.get("providers", {}).get(provider_key)
    if not prov:
        return {"success": False, "error": f"Unknown provider: {provider_key}"}

    if provider_key == "local_comfyui":
        raw_url = override_base_url or prov.get("url", "http://127.0.0.1:20140")
        url = normalize_base_url(raw_url, provider_key)
        try:
            req = urllib.request.Request(f"{url}/system_stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                devices = data.get("devices", [{}])
                gpu_name = devices[0].get("name", "NVIDIA GPU") if devices else "Local GPU"
                return {"success": True, "message": f"Connected to ComfyUI ({gpu_name})"}
        except Exception as e:
            return {"success": False, "error": f"Cannot reach ComfyUI on {url}: {e}"}

    raw_base_url = override_base_url or prov.get("base_url", "")
    base_url = normalize_base_url(raw_base_url, provider_key)
    api_key = override_api_key if override_api_key is not None else prov.get("api_key", "")
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

def is_image_model(model_id: str) -> bool:
    """Returns True if the model is an image generation model."""
    m = model_id.lower()
    # Reject pure text, code, audio, and video patterns
    if any(bad in m for bad in [
        'video', 'tts', 'audio', 'whisper', 'coder', 'coding', 'reasoning',
        'cursor', 'embed', 'embedding', 'translate', 'instruct', 'text-only'
    ]):
        return False
    # Accept explicit image indicators
    if any(good in m for good in [
        'image', 'flux', 'dall', 'recraft', 'diffusion', 'midjourney',
        'sdxl', 'sd_xl', 'sd-xl', 'banana', 'seedream', 'photo', 'paint', 'draw'
    ]):
        return True
    return False

def is_video_model(model_id: str) -> bool:
    """Returns True if the model is a video generation model."""
    m = model_id.lower()
    if 'wandb' in m:
        return False
    if any(bad in m for bad in [
        'audio', 'tts', 'whisper', 'coder', 'coding', 'reasoning',
        'cursor', 'embed', 'embedding', 'translate', 'instruct', 'text-only'
    ]):
        return False
    video_keywords = [
        'video', 'seedance', 'sora', 'runway', 'luma', 'kling',
        'cogvideo', 'animatediff', 'motion', 'anim'
    ]
    if any(k in m for k in video_keywords):
        return True
    if any(m.startswith(w) or f'/{w}' in m or f'-{w}' in m or f'_{w}' in m for w in ['wan', 'wan2', 'wan3', 'wanx']):
        return True
    return False

def is_audio_model(model_id: str) -> bool:
    """Returns True if the model is an audio/TTS model."""
    m = model_id.lower()
    return any(good in m for good in ['audio', 'tts', 'speech', 'voice', 'whisper', 'sound'])

def query_remote_models(provider_key: str, modality: str = "image") -> List[Dict[str, Any]]:
    """Fetches available models from remote OpenRouter, OpenAI, OmniRoute, or custom endpoint filtered by modality."""
    cfg = get_providers_config()
    prov = cfg.get("providers", {}).get(provider_key)
    if not prov or not prov.get("enabled", True):
        return []

    base_url = normalize_base_url(prov.get("base_url", ""), provider_key)
    api_key = prov.get("api_key", "")
    if not base_url:
        return []

    # If the provider has explicitly enabled models listed for this modality, return those
    preset_models = prov.get(f"enabled_{modality}_models") or prov.get("enabled_models", [])
    
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
                
                # Context-relative filter by modality
                if modality == "image" and not is_image_model(m_id):
                    continue
                elif modality == "video" and not is_video_model(m_id):
                    continue
                elif modality == "audio" and not is_audio_model(m_id):
                    continue

                if preset_models and m_id not in preset_models:
                    continue
                    
                display_name = m_id.split("/")[-1].replace("-", " ").title()
                out.append({
                    "model": m_id,
                    "model_creator": provider_key,
                    "full_name": f"{display_name} ({prov.get('name', provider_key)})",
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
        if modality == "image" and not is_image_model(m_id):
            continue
        elif modality == "video" and not is_video_model(m_id):
            continue
        elif modality == "audio" and not is_audio_model(m_id):
            continue
        display_name = m_id.split("/")[-1].replace("-", " ").title()
        out.append({
            "model": m_id,
            "model_creator": provider_key,
            "full_name": f"{display_name} ({prov.get('name', provider_key)})",
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

    base_url = normalize_base_url(prov.get("base_url", ""), prov_key)
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
