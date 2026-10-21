import os
import io
import time
import uuid
import shutil
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Response, UploadFile, File, BackgroundTasks, Form, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import HOST, PORT, BASE_URL, MEDIA_DIR, DOWNLOADS_DIR, SETTINGS_DIR, CHECKPOINTS_DIR
from engine_generators import (
    remove_background,
    generate_image_locally,
    generate_video_locally,
    generate_3d_mesh_locally,
    generate_gaussian_splat_locally,
)
from provider_router import (
    get_providers_config,
    save_providers_config,
    get_active_provider_info,
    set_active_provider,
    update_provider_details,
    query_remote_models,
    generate_remote_image,
)

app = FastAPI(title="ArtCraft Local Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry of jobs and media files
jobs_registry: Dict[str, Dict[str, Any]] = {}
media_registry: Dict[str, Path] = {}
media_metadata_registry: Dict[str, Dict[str, Any]] = {}

def get_mime_type(suffix: str) -> str:
    ext = suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".glb": "model/gltf-binary",
        ".ply": "application/octet-stream",
        ".splat": "application/octet-stream",
    }
    return media_types.get(ext, "application/octet-stream")

@app.post("/v1/dev/reset")
def dev_reset():
    jobs_registry.clear()
    media_registry.clear()
    media_metadata_registry.clear()
    return {"success": True}

def get_utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_media_from_disk():
    for f in MEDIA_DIR.glob("*.*"):
        if f.is_file() and not f.name.endswith(("_still.png", "_keyframe.png", "_temp.mp4", "_anim.webp", "_h264.mp4")) and not f.name.startswith("test_"):
            token = f.stem
            media_registry[token] = f
            ext = f.suffix.lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp"):
                mclass = "image"
                mtype = ext.lstrip(".")
            elif ext in (".mp4", ".webm"):
                mclass = "video"
                mtype = ext.lstrip(".")
            elif ext == ".glb":
                mclass = "mesh"
                mtype = "glb"
            elif ext == ".ply":
                mclass = "splat"
                mtype = "ply"
            else:
                mclass = "image"
                mtype = ext.lstrip(".")
                
            media_url = f"{BASE_URL}/cdn/{f.name}"
            
            video_previews = None
            still_url = None
            if mclass == "video":
                still_path = MEDIA_DIR / f"{token}_still.png"
                if still_path.exists():
                    still_url = f"{BASE_URL}/cdn/{still_path.name}"
                else:
                    still_url = media_url

                anim_path = MEDIA_DIR / f"{token}_anim.webp"
                anim_url = f"{BASE_URL}/cdn/{anim_path.name}" if anim_path.exists() else still_url

                video_previews = {
                    "still": still_url,
                    "animated": anim_url,
                    "still_thumbnail_template": still_url,
                    "animated_thumbnail_template": anim_url,
                }
                thumbnail_url = still_url
            else:
                still_path = MEDIA_DIR / f"{token}_still.png"
                if still_path.exists():
                    thumbnail_url = f"{BASE_URL}/cdn/{still_path.name}"
                else:
                    thumbnail_url = media_url
                
            if token not in media_metadata_registry:
                media_metadata_registry[token] = {
                    "token": token,
                    "media_type": mtype,
                    "media_class": mclass,
                    "maybe_animation_type": None,
                    "maybe_engine_extension": None,
                    "maybe_batch_token": f"batch_{token}",
                    "maybe_original_filename": f.name,
                    "maybe_creator_user": {
                        "user_token": "user_xskfwjeyf9vmz",
                        "username": "local_creator",
                        "display_name": "Local Creator",
                    },
                    "maybe_prompt_token": None,
                    "origin": {
                        "origin_category": "generation",
                        "product_category": mclass,
                        "maybe_model": {"title": "Local SDXL" if mclass == "image" else "Local Video"},
                    },
                    "origin_category": "generation",
                    "origin_product_category": mclass,
                    "maybe_origin_model_type": "sd_xl_base_1.0" if mclass == "image" else "wan_3p0",
                    "maybe_origin_model_token": None,
                    "maybe_duration_millis": 4000 if mclass == "video" else None,
                    "maybe_style_name": None,
                    "public_bucket_path": f"/cdn/{f.name}",
                    "public_bucket_url": media_url,
                    "media_links": {
                        "cdn_url": media_url,
                        "thumbnail_template": thumbnail_url,
                        "maybe_thumbnail_template": thumbnail_url,
                        "maybe_video_previews": video_previews,
                    },
                    "cover_image": {
                        "maybe_links": {"cdn_url": thumbnail_url},
                        "maybe_cover_image_public_bucket_path": thumbnail_url,
                        "maybe_cover_image_public_bucket_url": thumbnail_url,
                        "default_cover": {"image_index": 0, "color_index": 0},
                    },
                    "creator_set_visibility": "public",
                    "maybe_title": f.stem,
                    "maybe_text_transcript": None,
                    "stats": {"positive_rating_count": 0, "bookmark_count": 0},
                    "created_at": get_utc_now_iso(),
                    "updated_at": get_utc_now_iso(),
                }

init_media_from_disk()

# -------------------------------------------------------------
# Background Workers
# -------------------------------------------------------------
def run_job_task(job_token: str, task_type: str, params: Dict[str, Any]):
    try:
        jobs_registry[job_token]["status"] = "started"
        jobs_registry[job_token]["progress_percentage"] = 30
        
        media_token = f"med_{uuid.uuid4().hex[:16]}"
        out_file = None
        
        if task_type == "image":
            prompt = params.get("prompt", "Local image generation")
            ref_token = params.get("ref_token")
            model_name = params.get("model")
            ref_path = media_registry.get(ref_token) if ref_token else None
            out_file = MEDIA_DIR / f"{media_token}.png"
            
            active_prov = get_active_provider_info()
            if active_prov.get("key") != "local_comfyui":
                print(f"[Engine] Routing image generation to active provider: {active_prov.get('name')}")
                remote_out = generate_remote_image(prompt, model=model_name, output_path=out_file)
                if not remote_out or not remote_out.exists():
                    print("[Engine] Remote provider call failed/empty; falling back to local SDXL GPU.")
                    generate_image_locally(prompt, ref_image_path=ref_path, output_path=out_file, model_name=model_name)
            else:
                generate_image_locally(prompt, ref_image_path=ref_path, output_path=out_file, model_name=model_name)
            
        elif task_type == "video":
            prompt = params.get("prompt", "Local video generation")
            start_token = params.get("start_frame_token")
            model_name = params.get("model")
            start_path = media_registry.get(start_token) if start_token else None
            out_file = MEDIA_DIR / f"{media_token}.mp4"
            generate_video_locally(prompt, start_frame_path=start_path, output_path=out_file)
            
        elif task_type == "bg_removal":
            ref_token = params.get("ref_token")
            ref_path = media_registry.get(ref_token)
            out_file = MEDIA_DIR / f"{media_token}.png"
            if ref_path and ref_path.exists():
                remove_background(ref_path, out_file)
            else:
                generate_image_locally("Clean background", output_path=out_file)
                
        elif task_type == "mesh":
            prompt = params.get("prompt", "Local 3D Object")
            ref_token = params.get("ref_token")
            ref_path = media_registry.get(ref_token) if ref_token else None
            out_file = MEDIA_DIR / f"{media_token}.glb"
            generate_3d_mesh_locally(prompt, image_path=ref_path, output_path=out_file)
            
        elif task_type == "splat":
            prompt = params.get("prompt", "Local Gaussian Splat")
            ref_token = params.get("ref_token")
            ref_path = media_registry.get(ref_token) if ref_token else None
            out_file = MEDIA_DIR / f"{media_token}.ply"
            generate_gaussian_splat_locally(prompt, image_path=ref_path, output_path=out_file)
            
        # Copy to ArtCraft downloads folder for convenience
        if out_file and out_file.exists():
            media_registry[media_token] = out_file
            try:
                shutil.copy(out_file, DOWNLOADS_DIR / out_file.name)
            except Exception:
                pass
            
            media_url = f"{BASE_URL}/cdn/{out_file.name}"
            
            video_previews = None
            still_url = None
            if task_type == "video":
                still_path = MEDIA_DIR / f"{out_file.stem}_still.png"
                if still_path.exists():
                    still_url = f"{BASE_URL}/cdn/{still_path.name}"
                else:
                    still_url = media_url

                anim_path = MEDIA_DIR / f"{out_file.stem}_anim.webp"
                anim_url = f"{BASE_URL}/cdn/{anim_path.name}" if anim_path.exists() else still_url

                video_previews = {
                    "still": still_url,
                    "animated": anim_url,
                    "still_thumbnail_template": still_url,
                    "animated_thumbnail_template": anim_url,
                }
                
            if task_type in ("image", "bg_removal"):
                mclass = "image"
                mtype = "png"
                thumbnail_url = media_url
            elif task_type == "video":
                mclass = "video"
                mtype = "mp4"
                thumbnail_url = still_url
            elif task_type == "mesh":
                mclass = "mesh"
                mtype = "glb"
                still_path = MEDIA_DIR / f"{out_file.stem}_still.png"
                thumbnail_url = f"{BASE_URL}/cdn/{still_path.name}" if still_path.exists() else media_url
            else:
                mclass = "splat"
                mtype = "ply"
                thumbnail_url = media_url

            media_metadata_registry[media_token] = {
                "token": media_token,
                "media_type": mtype,
                "media_class": mclass,
                "maybe_animation_type": None,
                "maybe_engine_extension": None,
                "maybe_batch_token": f"batch_{media_token}",
                "maybe_original_filename": out_file.name,
                "maybe_creator_user": {
                    "user_token": "user_xskfwjeyf9vmz",
                    "username": "local_creator",
                    "display_name": "Local Creator",
                },
                "maybe_prompt_token": None,
                "origin": {
                    "origin_category": "generation",
                    "product_category": task_type,
                    "maybe_model": {"title": params.get("model", "Local Generator")},
                },
                "origin_category": "generation",
                "origin_product_category": task_type,
                "maybe_origin_model_type": params.get("model", "wan_3p0" if task_type == "video" else "flux_1_dev"),
                "maybe_origin_model_token": None,
                "maybe_duration_millis": 4000 if task_type == "video" else None,
                "maybe_style_name": None,
                "public_bucket_path": f"/cdn/{out_file.name}",
                "public_bucket_url": media_url,
                "media_links": {
                    "cdn_url": media_url,
                    "thumbnail_template": thumbnail_url,
                    "maybe_thumbnail_template": thumbnail_url,
                    "maybe_video_previews": video_previews,
                },
                "cover_image": {
                    "maybe_links": {"cdn_url": thumbnail_url},
                    "maybe_cover_image_public_bucket_path": thumbnail_url,
                    "maybe_cover_image_public_bucket_url": thumbnail_url,
                    "default_cover": {"image_index": 0, "color_index": 0},
                },
                "creator_set_visibility": "public",
                "maybe_title": params.get("prompt", "Local Generation"),
                "maybe_text_transcript": None,
                "stats": {"positive_rating_count": 0, "bookmark_count": 0},
                "created_at": get_utc_now_iso(),
                "updated_at": get_utc_now_iso(),
            }
            
            jobs_registry[job_token]["status"] = "complete_success"
            jobs_registry[job_token]["progress_percentage"] = 100
            jobs_registry[job_token]["maybe_result"] = {
                "entity_type": "media_file",
                "entity_token": media_token,
                "media_links": {
                    "cdn_url": media_url,
                    "thumbnail_template": thumbnail_url,
                    "maybe_thumbnail_template": thumbnail_url,
                    "maybe_video_previews": video_previews,
                },
                "maybe_successfully_completed_at": get_utc_now_iso(),
            }
            jobs_registry[job_token]["updated_at"] = get_utc_now_iso()
            print(f"[Engine] Job {job_token} finished successfully -> {out_file.name}")
    except Exception as e:
        print(f"[Engine] Error processing job {job_token}: {e}")
        jobs_registry[job_token]["status"] = "complete_failure"
        jobs_registry[job_token]["maybe_failure_message"] = str(e)


# -------------------------------------------------------------
# Base Health & Status
# -------------------------------------------------------------
@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "artcraft-local-engine",
        "mode": "unlimited-free-local",
        "jobs_count": len(jobs_registry)
    }

# -------------------------------------------------------------
# Credits & Subscriptions (Infinite / Zero Paywall)
# -------------------------------------------------------------
@app.get("/v1/credits/namespace/{namespace}")
def get_credits(namespace: str):
    return {
        "success": True,
        "free_credits": 999999,
        "monthly_credits": 999999,
        "banked_credits": 999999,
        "sum_total_credits": 2999997,
    }

@app.get("/v1/subscriptions/namespace/{namespace}")
def get_subscription(namespace: str):
    return {
        "success": True,
        "active_subscription": {
            "tier": "enterprise_unlimited",
            "status": "active",
            "billing_interval": "never",
            "renews_at": "2099-01-01T00:00:00Z"
        }
    }

# -------------------------------------------------------------
# Authentication & Sessions (Fully Unlocked & Persistent)
# -------------------------------------------------------------
SESSION_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX3Rva2VuIjoic2Vzc2lvbl9qNHdwcTYydnpwNXltZ3FjZDRodHF0cTMiLCJ1c2VyX3Rva2VuIjoidXNlcl94c2tmd2pleWY5dm16IiwidmVyc2lvbiI6IjMifQ.Qt2-0RdJrP6Y3AdzildvXyWTkA7i2pkeZ1B52gwFNYM"
AVT_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJhdnRfdG9rZW4iOiJhdnRfazdrZWNxbWg3eTkzZXlzcmVieDBkbTRrcGJ3OSIsImNvb2tpZV92ZXJzaW9uIjoiMSJ9.OjVza0eheW-6gLZhm1JFUCF9xjJG6kzOo9DPXytZEy8"

SESSION_USER_PAYLOAD = {
    "success": True,
    "logged_in": True,
    "user": {
        "core_info": {
            "user_token": "user_xskfwjeyf9vmz",
            "username": "local_creator",
            "display_name": "Local Creator",
            "gravatar_hash": "00000000000000000000000000000000",
            "default_avatar": {
                "image_index": 0,
                "color_index": 0
            }
        },
        "user_token": "user_xskfwjeyf9vmz",
        "username": "local_creator",
        "display_name": "Local Creator",
        "email_gravatar_hash": "00000000000000000000000000000000",
        "onboarding": {
            "email_not_set": False,
            "email_not_confirmed": False,
            "password_not_set": False,
            "username_not_customized": False
        },
        "can_access_studio": True,
        "maybe_feature_flags": [],
        "fakeyou_plan": "pro",
        "storyteller_stream_plan": "pro",
        "can_use_tts": True,
        "can_use_w2l": True,
        "can_delete_own_tts_results": True,
        "can_delete_own_w2l_results": True,
        "can_delete_own_account": False,
        "can_upload_tts_models": True,
        "can_upload_w2l_templates": True,
        "can_delete_own_tts_models": True,
        "can_delete_own_w2l_templates": True,
        "can_approve_w2l_templates": True,
        "can_edit_other_users_profiles": False,
        "can_edit_other_users_tts_models": False,
        "can_edit_other_users_w2l_templates": False,
        "can_delete_other_users_tts_models": False,
        "can_delete_other_users_tts_results": False,
        "can_delete_other_users_w2l_templates": False,
        "can_delete_other_users_w2l_results": False,
        "can_ban_users": False,
        "can_delete_users": False
    }
}

@app.get("/v1/session")
def get_session(response: Response):
    response.set_cookie(
        key="session",
        value=SESSION_JWT,
        max_age=630720000,
        path="/",
        httponly=False,
        samesite="lax"
    )
    response.set_cookie(
        key="visitor",
        value=AVT_JWT,
        max_age=630720000,
        path="/",
        httponly=False,
        samesite="lax"
    )
    return SESSION_USER_PAYLOAD

@app.post("/v1/login")
@app.post("/v1/create_account")
def auth_login(response: Response):
    response.set_cookie(
        key="session",
        value=SESSION_JWT,
        max_age=630720000,
        path="/",
        httponly=False,
        samesite="lax"
    )
    return {
        "success": True,
        "signed_session": SESSION_JWT
    }

@app.post("/v1/login_challenges/create")
def create_challenge():
    return {
        "success": True,
        "device_token": "a" * 43,
        "verification_url": f"{BASE_URL}/verify",
        "confirmation_code": "LOCAL-1234",
        "expires_at": "2099-01-01T00:00:00Z",
        "poll_interval_seconds": 5
    }

@app.post("/v1/login_challenges/poll")
def poll_challenge(response: Response):
    response.set_cookie(
        key="session",
        value=SESSION_JWT,
        max_age=630720000,
        path="/",
        httponly=False,
        samesite="lax"
    )
    return {
        "success": True,
        "status": "redeemed",
        "maybe_failure_type": None,
        "maybe_signed_session": SESSION_JWT
    }

# -------------------------------------------------------------
# Cost Estimation (Free / Unlimited)
# -------------------------------------------------------------
@app.post("/v1/omni_gen/cost/image")
@app.post("/v1/omni_gen/cost/video")
@app.post("/v1/generate/cost_estimate/image")
@app.post("/v1/generate/cost_estimate/video")
@app.post("/v1/generate/cost_estimate/splat")
@app.post("/v1/generate/cost_estimate/mesh")
def cost_estimate():
    return {
        "success": True,
        "cost_in_credits": 0,
        "cost_in_usd_cents": 0,
        "is_free": True,
        "is_unlimited": True,
        "is_rate_limited": False,
        "has_watermark": False,
        "failures_are_refunded": True
    }

# -------------------------------------------------------------
# Dynamic AI Provider Management (OmniRoute / OpenRouter / Local ComfyUI)
# -------------------------------------------------------------
@app.get("/v1/ai/providers")
def get_ai_providers():
    cfg = get_providers_config()
    safe_providers = {}
    for k, v in cfg.get("providers", {}).items():
        v_copy = dict(v)
        key = v_copy.get("api_key", "")
        if key and len(key) > 8:
            v_copy["api_key"] = key[:4] + "..." + key[-4:]
        elif key:
            v_copy["api_key"] = "****"
        safe_providers[k] = v_copy
    return {
        "success": True,
        "active_provider": cfg.get("active_provider", "local_comfyui"),
        "providers": safe_providers
    }

@app.post("/v1/ai/providers")
async def update_ai_providers(request: Request):
    data = await request.json()
    active = data.get("active_provider")
    if active:
        set_active_provider(active)
    updates = data.get("provider_details")
    target = data.get("target_provider") or active
    if target and updates:
        update_provider_details(target, updates)
    return {"success": True, "active_provider": get_active_provider_info()}

@app.get("/v1/ai/models")
def get_ai_models(provider: Optional[str] = None):
    prov = provider or get_active_provider_info().get("key", "local_comfyui")
    if prov == "local_comfyui":
        return list_image_models()
    models = query_remote_models(prov)
    return {"success": True, "provider": prov, "models": models}

# -------------------------------------------------------------
# Model Catalog
# -------------------------------------------------------------
@app.get("/v1/omni_gen/models/image")
def list_image_models():
    aspect_ratios = [
        "square", "square_hd", "tall_nine_by_sixteen", 
        "wide_sixteen_by_nine", "tall_three_by_four", "wide_four_by_three"
    ]
    
    # 0. Check active provider from provider_router
    active_prov = get_active_provider_info()
    remote_models = []
    if active_prov.get("key") != "local_comfyui":
        remote_models = query_remote_models(active_prov.get("key"))
        for rm in remote_models:
            rm["aspect_ratio_options"] = aspect_ratios
            rm["aspect_ratio_default"] = "square"
            rm["aspect_ratio_default_when_editing"] = "square"
            rm["resolution_options"] = ["auto_1K", "auto_2K"]
            rm["resolution_default"] = "auto_1K"
            rm["quality_options"] = ["standard", "high"]
            rm["default_quality"] = "standard"
            rm["batch_size_min"] = 1
            rm["batch_size_max"] = 4
            rm["batch_size_options"] = [1, 2, 4]
            rm["batch_size_default"] = 1

    # 1. Dynamically scan checkpoints folder for any local safetensors
    discovered_models = []
    ckpt_dir = CHECKPOINTS_DIR
    if ckpt_dir.exists():
        for ckpt in sorted(ckpt_dir.glob("*.safetensors")):
            model_key = ckpt.stem.lower().replace(" ", "_").replace(".", "_")
            discovered_models.append({
                "model": model_key,
                "model_creator": "local",
                "full_name": f"{ckpt.stem} (Local Checkpoint)",
                "text_prompt_supported": True,
                "text_prompt_max_length": 4096,
                "negative_text_prompt_supported": True,
                "negative_text_prompt_max_length": 4096,
                "image_refs_supported": True,
                "image_refs_max": 4,
                "has_fixed_editing_aspect_ratio": False,
                "aspect_ratio_options": aspect_ratios,
                "aspect_ratio_default": "square",
                "aspect_ratio_default_when_editing": "square",
                "resolution_options": ["auto_1K", "auto_2K"],
                "resolution_default": "auto_1K",
                "quality_options": ["standard", "high"],
                "default_quality": "standard",
                "batch_size_min": 1,
                "batch_size_max": 4,
                "batch_size_options": [1, 2, 4],
                "batch_size_default": 1,
                "is_disabled": False,
            })

    # 2. Built-in models / aliases mapped to local engine
    standard_models = [
        {
            "model": "nano_banana_pro",
            "model_creator": "google",
            "full_name": "Nano Banana Pro (Google)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 8192,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 6,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "nano_banana",
            "model_creator": "google",
            "full_name": "Nano Banana (Google)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 8192,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 6,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "nano_banana_2",
            "model_creator": "google",
            "full_name": "Nano Banana 2 (Google)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 8192,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 6,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "flux_1_dev",
            "model_creator": "black_forest_labs",
            "full_name": "FLUX.1 [dev] (Local)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "flux_1_schnell",
            "model_creator": "black_forest_labs",
            "full_name": "FLUX.1 [schnell] (Local)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "flux_pro_1p1",
            "model_creator": "black_forest_labs",
            "full_name": "Flux Pro 1.1 (BFL)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "flux_pro_1p1_ultra",
            "model_creator": "black_forest_labs",
            "full_name": "Flux Pro 1.1 Ultra (BFL)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "grok_imagine_image",
            "model_creator": "grok",
            "full_name": "Grok Imagine (xAI)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 8000,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4000,
            "image_refs_supported": True,
            "image_refs_max": 6,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 6,
            "batch_size_options": [1, 2, 4, 6],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "midjourney",
            "model_creator": "midjourney",
            "full_name": "Midjourney v6/v7",
            "text_prompt_supported": True,
            "text_prompt_max_length": 6000,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 2000,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K", "auto_2K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard", "high"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "gpt_image_1",
            "model_creator": "open_ai",
            "full_name": "GPT Image 1 (GPT-4o)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "seedream_4",
            "model_creator": "bytedance",
            "full_name": "Seedream 4 (Bytedance)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 4,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1, 2, 4],
            "batch_size_default": 1,
            "is_disabled": False,
        },
        {
            "model": "sd_xl_base_1.0",
            "model_creator": "stability",
            "full_name": "SDXL Base 1.0 (Local GPU)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 4096,
            "negative_text_prompt_supported": True,
            "negative_text_prompt_max_length": 4096,
            "image_refs_supported": True,
            "image_refs_max": 2,
            "has_fixed_editing_aspect_ratio": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "square",
            "aspect_ratio_default_when_editing": "square",
            "resolution_options": ["auto_1K"],
            "resolution_default": "auto_1K",
            "quality_options": ["standard"],
            "default_quality": "standard",
            "batch_size_min": 1,
            "batch_size_max": 4,
            "batch_size_options": [1],
            "batch_size_default": 1,
            "is_disabled": False,
        }
    ]
    
    # Merge remote, discovered, and standard models without duplicates
    seen = set()
    models = []
    for m in remote_models + discovered_models + standard_models:
        if m["model"] not in seen:
            seen.add(m["model"])
            models.append(m)
            
    return {
        "success": True,
        "models": models,
        "providers": [{"provider": "artcraft", "models": [{"model": m["model"]} for m in models]}]
    }

@app.get("/v1/omni_gen/models/video")
def list_video_models():
    aspect_ratios = ["wide_sixteen_by_nine", "tall_nine_by_sixteen", "square"]
    models = [
        {
            "model": "wan_3p0",
            "model_creator": "wan_ai",
            "full_name": "Wan 2.1 (Local 14B/1.3B)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 2048,
            "start_frame_supported": True,
            "start_and_end_frame_supported": True,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "wide_sixteen_by_nine",
            "durations_seconds_supported": [3, 5, 8],
            "duration_seconds_default": 5,
            "is_disabled": False,
        },
        {
            "model": "wan_3p0_prime",
            "model_creator": "wan_ai",
            "full_name": "Wan 2.1 High Quality (Local)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 2048,
            "start_frame_supported": True,
            "start_and_end_frame_supported": True,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "wide_sixteen_by_nine",
            "durations_seconds_supported": [5],
            "duration_seconds_default": 5,
            "is_disabled": False,
        },
        {
            "model": "seedance_2p0",
            "model_creator": "bytedance",
            "full_name": "Seedance 2.0 (Local Engine)",
            "text_prompt_supported": True,
            "text_prompt_max_length": 2048,
            "start_frame_supported": True,
            "start_and_end_frame_supported": False,
            "aspect_ratio_options": aspect_ratios,
            "aspect_ratio_default": "wide_sixteen_by_nine",
            "durations_seconds_supported": [5],
            "duration_seconds_default": 5,
            "is_disabled": False,
        }
    ]
    return {
        "success": True,
        "models": models,
        "providers": [{"provider": "artcraft", "models": [{"model": m["model"]} for m in models]}]
    }

@app.get("/v1/omni_gen/models/mesh")
def list_mesh_models():
    models = [
        {
            "model": "hunyuan_3d_2p0",
            "model_creator": "tencent",
            "full_name": "Hunyuan3D 2.0 (Local Mesh)",
            "is_disabled": False
        },
        {
            "model": "hunyuan_3d_3",
            "model_creator": "tencent",
            "full_name": "Hunyuan3D v3 (Local Mesh)",
            "is_disabled": False
        }
    ]
    return {
        "success": True,
        "models": models,
        "providers": [{"provider": "artcraft", "models": [{"model": m["model"]} for m in models]}]
    }

@app.get("/v1/omni_gen/models/splat")
def list_splat_models():
    models = [
        {
            "model": "marble_0p1_mini",
            "model_creator": "world_labs",
            "full_name": "Gaussian Splat Marble (Local)",
            "is_disabled": False
        }
    ]
    return {
        "success": True,
        "models": models,
        "providers": [{"provider": "artcraft", "models": [{"model": m["model"]} for m in models]}]
    }

@app.get("/v1/omni_gen/models/audio")
def list_audio_models():
    return {
        "success": True,
        "models": [],
        "providers": []
    }

# -------------------------------------------------------------
# Generation Endpoints (Image, Video, 3D Object, Splat, BG Removal)
# -------------------------------------------------------------
@app.post("/v1/omni_gen/generate/image")
async def generate_image_endpoint(request: Request, bg_tasks: BackgroundTasks):
    data = await request.json()
    job_token = f"job_img_{uuid.uuid4().hex[:12]}"
    prompt = data.get("text_prompt") or data.get("prompt") or "A creative composition"
    ref_tokens = data.get("reference_image_media_tokens") or data.get("image_media_tokens") or []
    ref_token = ref_tokens[0] if ref_tokens else None
    model_name = data.get("model", "sd_xl_base_1.0")
    
    jobs_registry[job_token] = {
        "job_token": job_token,
        "status": "pending",
        "progress_percentage": 0,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
        "request": {
            "inference_category": "image_generation",
            "maybe_model_type": model_name,
            "maybe_raw_inference_text": prompt,
        },
        "maybe_result": None
    }
    
    bg_tasks.add_task(run_job_task, job_token, "image", {"prompt": prompt, "ref_token": ref_token, "model": model_name})
    return {"success": True, "inference_job_token": job_token, "all_job_tokens": [job_token]}

@app.post("/v1/omni_gen/generate/video")
async def generate_video_endpoint(request: Request, bg_tasks: BackgroundTasks):
    data = await request.json()
    job_token = f"job_vid_{uuid.uuid4().hex[:12]}"
    prompt = data.get("text_prompt") or data.get("prompt") or "Cinematic motion video"
    start_frame = data.get("start_frame_image_media_token")
    model_name = data.get("model", "wan_3p0")
    
    jobs_registry[job_token] = {
        "job_token": job_token,
        "status": "pending",
        "progress_percentage": 0,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
        "request": {
            "inference_category": "video_generation",
            "maybe_model_type": model_name,
            "maybe_raw_inference_text": prompt,
        },
        "maybe_result": None
    }
    
    bg_tasks.add_task(run_job_task, job_token, "video", {"prompt": prompt, "start_frame_token": start_frame, "model": model_name})
    return {"success": True, "inference_job_token": job_token, "all_job_tokens": [job_token]}
    return {"success": True, "inference_job_token": job_token, "all_job_tokens": [job_token]}

@app.post("/v1/generate/image/remove_background")
async def remove_bg_endpoint(request: Request, bg_tasks: BackgroundTasks):
    data = await request.json()
    job_token = f"job_bg_{uuid.uuid4().hex[:12]}"
    ref_token = data.get("image_media_token")
    
    jobs_registry[job_token] = {
        "job_token": job_token,
        "status": "pending",
        "progress_percentage": 0,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
        "request": {
            "inference_category": "background_removal",
            "maybe_model_type": "rembg",
        },
        "maybe_result": None
    }
    
    bg_tasks.add_task(run_job_task, job_token, "bg_removal", {"ref_token": ref_token})
    return {"success": True, "job_token": job_token, "inference_job_token": job_token, "all_job_tokens": [job_token]}

@app.post("/v1/generate/object/hunyuan_2.0_image_to_3d")
@app.post("/v1/generate/object/hunyuan_2.1_image_to_3d")
@app.post("/v1/generate/object/multi_function/hunyuan3d_v3")
async def generate_mesh_endpoint(request: Request, bg_tasks: BackgroundTasks):
    data = await request.json()
    job_token = f"job_mesh_{uuid.uuid4().hex[:12]}"
    ref_token = data.get("image_media_token")
    prompt = data.get("prompt", "3D Object Model")
    
    jobs_registry[job_token] = {
        "job_token": job_token,
        "status": "pending",
        "progress_percentage": 0,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
        "request": {
            "inference_category": "object_generation",
            "maybe_model_type": "hunyuan3d",
            "maybe_raw_inference_text": prompt,
        },
        "maybe_result": None
    }
    
    bg_tasks.add_task(run_job_task, job_token, "mesh", {"prompt": prompt, "ref_token": ref_token})
    return {"success": True, "job_token": job_token, "inference_job_token": job_token, "all_job_tokens": [job_token]}

@app.post("/v1/generate/splat/worldlabs_marble_0p1_mini")
@app.post("/v1/generate/splat/worldlabs_marble_0p1_plus")
async def generate_splat_endpoint(request: Request, bg_tasks: BackgroundTasks):
    data = await request.json()
    job_token = f"job_splat_{uuid.uuid4().hex[:12]}"
    ref_token = data.get("image_media_token")
    prompt = data.get("prompt", "Gaussian Splat World")
    
    jobs_registry[job_token] = {
        "job_token": job_token,
        "status": "pending",
        "progress_percentage": 0,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
        "request": {
            "inference_category": "splat_generation",
            "maybe_model_type": "worldlabs_marble",
            "maybe_raw_inference_text": prompt,
        },
        "maybe_result": None
    }
    
    bg_tasks.add_task(run_job_task, job_token, "splat", {"prompt": prompt, "ref_token": ref_token})
    return {"success": True, "job_token": job_token, "inference_job_token": job_token, "all_job_tokens": [job_token]}

# -------------------------------------------------------------
# Polling Endpoint for Session Jobs
# -------------------------------------------------------------
@app.get("/v1/jobs/session")
def list_session_jobs(include_states: Optional[str] = None, exclude_states: Optional[str] = None):
    # Formulate jobs list according to artcraft_api_defs
    items = []
    for token, job in sorted(jobs_registry.items(), key=lambda x: x[1]["created_at"], reverse=True)[:50]:
        status_name = job["status"]
        if include_states and status_name not in include_states.split(","):
            continue
            
        items.append({
            "job_token": token,
            "request": job["request"],
            "status": {
                "status": status_name,
                "progress_percentage": job["progress_percentage"],
                "attempt_count": 1,
                "requires_keepalive": False,
                "maybe_failure_message": job.get("maybe_failure_message")
            },
            "maybe_result": job.get("maybe_result"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"]
        })
        
    return {
        "success": True,
        "jobs": items
    }

# -------------------------------------------------------------
# Media Files Management & Gallery
# -------------------------------------------------------------
@app.post("/v1/media_files/upload")
@app.post("/v1/media_files/upload/image")
@app.post("/v1/media_files/upload/new_video")
async def upload_media_file(file: UploadFile = File(...)):
    token = f"med_{uuid.uuid4().hex[:16]}"
    ext = os.path.splitext(file.filename)[1] or ".png"
    dest_path = MEDIA_DIR / f"{token}{ext}"
    
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
        
    media_registry[token] = dest_path
    media_url = f"{BASE_URL}/cdn/{token}{ext}"
    mclass = "image" if ext in (".png", ".jpg", ".webp") else ("video" if ext in (".mp4", ".webm") else "dimensional")
    mtype = ext.lstrip(".")
    
    meta = {
        "token": token,
        "media_type": mtype,
        "media_class": mclass,
        "maybe_animation_type": None,
        "maybe_engine_extension": None,
        "maybe_batch_token": f"batch_{token}",
        "maybe_original_filename": file.filename,
        "maybe_creator_user": {
            "user_token": "user_xskfwjeyf9vmz",
            "username": "local_creator",
            "display_name": "Local Creator",
        },
        "maybe_prompt_token": None,
        "origin": {
            "origin_category": "upload",
            "product_category": mclass,
            "maybe_model": None,
        },
        "origin_category": "upload",
        "origin_product_category": mclass,
        "maybe_origin_model_type": None,
        "maybe_origin_model_token": None,
        "maybe_duration_millis": None,
        "maybe_style_name": None,
        "public_bucket_path": f"/cdn/{token}{ext}",
        "public_bucket_url": media_url,
        "media_links": {
            "cdn_url": media_url,
            "thumbnail_template": None,
            "maybe_thumbnail_template": None,
            "maybe_video_previews": None,
        },
        "cover_image": {
            "maybe_cover_image_public_bucket_path": None,
            "default_cover": {"image_index": 0, "color_index": 0},
        },
        "creator_set_visibility": "public",
        "maybe_title": file.filename,
        "maybe_text_transcript": None,
        "stats": {"positive_rating_count": 0, "bookmark_count": 0},
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso(),
    }
    media_metadata_registry[token] = meta
    
    return {
        "success": True,
        "media_file_token": token,
        "media_file": meta
    }

def serve_raw_file(filename: str):
    target = MEDIA_DIR / filename
    if target.exists() and target.is_file():
        return FileResponse(str(target), media_type=get_mime_type(target.suffix))
    stem = filename.split(".")[0]
    matches = list(MEDIA_DIR.glob(f"{stem}*"))
    if matches and matches[0].is_file():
        return FileResponse(str(matches[0]), media_type=get_mime_type(matches[0].suffix))
    return Response(status_code=404, content="Media file not found")

@app.get("/cdn/{filename:path}")
def serve_cdn_file(filename: str):
    return serve_raw_file(filename)

@app.get("/v1/media_files/file/{token}")
@app.get("/v1/media_files/token/{token}")
@app.get("/v1/media_files/by_token/{token}")
def get_media_file_or_meta(token: str, request: Request):
    has_ext = "." in token
    accept_header = request.headers.get("accept", "")
    base_token = token.split(".")[0]

    # If asking for metadata:
    if not has_ext and ("application/json" in accept_header or "*/*" in accept_header):
        if base_token in media_metadata_registry:
            return {"success": True, "media_file": media_metadata_registry[base_token]}
        for k, v in media_metadata_registry.items():
            if k == base_token or k.startswith(base_token):
                return {"success": True, "media_file": v}

    return serve_raw_file(token)

@app.get("/v1/media_files/list/user/{username}")
@app.get("/v1/media_files/list")
@app.get("/v1/media_files/list_featured")
@app.get("/v1/media_files/search_session")
@app.get("/v1/media_files/search_featured")
def list_user_media_files(
    username: Optional[str] = None,
    filter_media_classes: Optional[str] = None,
    filter_media_type: Optional[str] = None,
    filter_engine_categories: Optional[str] = None,
    search_term: Optional[str] = None,
    page_size: int = 50,
    page: int = 0
):
    results = sorted(list(media_metadata_registry.values()), key=lambda x: x.get("created_at", ""), reverse=True)
    if filter_media_classes:
        allowed = set(filter_media_classes.split(","))
        results = [m for m in results if m.get("media_class") in allowed]
    if filter_media_type:
        allowed = set(filter_media_type.split(","))
        results = [m for m in results if m.get("media_type") in allowed]
    if search_term:
        st = search_term.lower()
        results = [m for m in results if st in (m.get("maybe_title") or "").lower()]

    return {
        "success": True,
        "results": results,
        "media_files": results,
        "pagination": {
            "current": page,
            "total_page_count": 1,
            "total_item_count": len(results),
            "has_more": False,
        }
    }

@app.get("/v1/media_files/mesh/list")
def list_mesh_media():
    results = [m for m in media_metadata_registry.values() if m.get("media_class") in ("mesh", "dimensional") or m.get("media_type") == "glb"]
    return {
        "success": True,
        "results": results,
        "pagination": {
            "current": 0,
            "total_page_count": 1,
            "total_item_count": len(results),
            "has_more": False,
        }
    }

@app.get("/v1/media_files/splat/list")
def list_splat_media():
    results = [m for m in media_metadata_registry.values() if m.get("media_class") in ("splat", "dimensional") or m.get("media_type") == "ply"]
    return {
        "success": True,
        "results": results,
        "pagination": {
            "current": 0,
            "total_page_count": 1,
            "total_item_count": len(results),
            "has_more": False,
        }
    }

@app.get("/v1/media_files/project/list")
def list_project_media():
    return {
        "success": True,
        "results": [],
        "pagination": {
            "current": 0,
            "total_page_count": 0,
            "total_item_count": 0,
            "has_more": False,
        }
    }

@app.get("/v1/media_files/batch")
def get_media_files_batch(tokens: Optional[str] = None):
    token_list = [t.strip() for t in (tokens or "").split(",") if t.strip()]
    files = [media_metadata_registry[t] for t in token_list if t in media_metadata_registry]
    if not files:
        files = list(media_metadata_registry.values())
    return {
        "success": True,
        "media_files": files
    }

@app.get("/v1/media_files/batch_gen_redux/{batch_token}")
def get_batch_redux(batch_token: str):
    matches = [m for m in media_metadata_registry.values() if m.get("maybe_batch_token") == batch_token]
    if not matches:
        matches = sorted(list(media_metadata_registry.values()), key=lambda x: x.get("created_at", ""), reverse=True)[:1]
    return {
        "success": True,
        "media_files": matches
    }

@app.get("/v1/tags/media_files/list_tagged")
@app.get("/v1/tags/media_files/list_untagged")
@app.get("/v1/tags/media_files/with_tag/{tag_token}")
def list_tagged_media(tag_token: Optional[str] = None):
    items = []
    for m in sorted(list(media_metadata_registry.values()), key=lambda x: x.get("created_at", ""), reverse=True):
        items.append({
            "token": m["token"],
            "media_class": m["media_class"],
            "media_type": m["media_type"],
            "maybe_original_filename": m.get("maybe_original_filename"),
            "maybe_title": m.get("maybe_title"),
            "cover_image": m.get("cover_image"),
            "media_links": m.get("media_links"),
            "created_at": m.get("created_at"),
            "updated_at": m.get("updated_at"),
            "tag_names": [],
            "tag_tokens": []
        })
    return {
        "success": True,
        "media_files": items,
        "maybe_cursor": None
    }

@app.post("/v1/tags/media_files/bulk_list_tags")
def bulk_list_tags(payload: dict = Body(...)):
    tokens = payload.get("media_file_tokens", [])
    return {
        "success": True,
        "media_files": [{"token": t, "tags": []} for t in tokens]
    }

@app.post("/v1/media_files/rename/{token}")
def rename_media(token: str, payload: dict = Body(...)):
    name = payload.get("name", "Untitled")
    if token in media_metadata_registry:
        media_metadata_registry[token]["maybe_title"] = name
    return {"success": True}

@app.delete("/v1/media_files/record/{token}")
@app.delete("/v1/media_files/file/{token}")
def delete_media(token: str):
    base = token.split(".")[0]
    if base in media_metadata_registry:
        del media_metadata_registry[base]
    if base in media_registry:
        del media_registry[base]
    # Remove files from disk so deleted items stay deleted
    for p in MEDIA_DIR.glob(f"{base}*"):
        try:
            if p.is_file():
                p.unlink()
        except Exception as e:
            print(f"[Engine] Warning: Could not unlink {p.name}: {e}")
    return {"success": True}

# -------------------------------------------------------------
# Analytics & Logging (Quiet Success)
# -------------------------------------------------------------
@app.post("/v1/analytics/active_user_v2")
def active_user_v2():
    return {
        "success": True,
        "wait_for_retry_millis": 60000
    }

@app.post("/v1/analytics/{path:path}")
def analytics_mock():
    return {"success": True}

# -------------------------------------------------------------
# Main Runner
# -------------------------------------------------------------
if __name__ == "__main__":
    print(f"[ArtCraft Local Engine] Starting on http://{HOST}:{PORT}...")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
