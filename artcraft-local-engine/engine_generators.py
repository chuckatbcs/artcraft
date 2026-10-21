import os
import io
import math
import time
import uuid
import struct
import threading
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np
import trimesh

from config import MEDIA_DIR, DOWNLOADS_DIR, COMFYUI_URL, CHECKPOINTS_DIR

_rembg = None
_sdxl_pipe = None
_sdxl_img2img_pipe = None
_gpu_lock = threading.RLock()
SDXL_MODEL_PATH = CHECKPOINTS_DIR / "sd_xl_base_1.0.safetensors"
if not SDXL_MODEL_PATH.exists():
    _ckpts = list(CHECKPOINTS_DIR.glob("*.safetensors"))
    if _ckpts:
        SDXL_MODEL_PATH = _ckpts[0]

def get_sdxl_pipeline():
    global _sdxl_pipe
    with _gpu_lock:
        if _sdxl_pipe is not None:
            return _sdxl_pipe
        if SDXL_MODEL_PATH.exists():
            try:
                import torch
                from diffusers import StableDiffusionXLPipeline
                print("[Generators] Loading SDXL local model into pipeline with CPU offload...")
                pipe = StableDiffusionXLPipeline.from_single_file(
                    str(SDXL_MODEL_PATH),
                    torch_dtype=torch.float16,
                    use_safetensors=True
                )
                pipe.enable_model_cpu_offload()
                _sdxl_pipe = pipe
                print("[Generators] SDXL model ready for high-speed local inference!")
            except Exception as e:
                print("[Generators] Warning: Failed to initialize SDXL pipeline:", e)
    return _sdxl_pipe

def get_sdxl_img2img_pipeline():
    global _sdxl_img2img_pipe
    with _gpu_lock:
        if _sdxl_img2img_pipe is not None:
            return _sdxl_img2img_pipe
        base_pipe = get_sdxl_pipeline()
        if base_pipe is not None:
            try:
                from diffusers import StableDiffusionXLImg2ImgPipeline
                print("[Generators] Initializing SDXL Img2Img pipeline (sharing base components)...")
                _sdxl_img2img_pipe = StableDiffusionXLImg2ImgPipeline(**base_pipe.components)
                print("[Generators] SDXL Img2Img pipeline ready!")
            except Exception as e:
                print("[Generators] Warning: Failed to initialize SDXL Img2Img pipeline:", e)
    return _sdxl_img2img_pipe

def get_rembg():
    global _rembg
    if _rembg is None:
        try:
            import rembg
            _rembg = rembg
        except Exception as e:
            print("[Generators] Warning: rembg could not be loaded:", e)
    return _rembg

def remove_background(input_path: Path, output_path: Path = None) -> Path:
    """Removes the background from an image using local rembg (u2net/birefnet)."""
    if output_path is None:
        output_path = MEDIA_DIR / f"{uuid.uuid4().hex}_nobg.png"
    
    with open(input_path, "rb") as f:
        input_data = f.read()
    
    rembg_module = get_rembg()
    if rembg_module is not None:
        output_data = rembg_module.remove(input_data)
        with open(output_path, "wb") as f:
            f.write(output_data)
    else:
        # Fallback: simple luminance threshold alpha if rembg unavailable
        img = Image.open(io.BytesIO(input_data)).convert("RGBA")
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        img.save(output_path, "PNG")
        
    return output_path

def generate_image_locally(prompt: str, width: int = 1024, height: int = 1024, ref_image_path: Path = None, output_path: Path = None, model_name: str = None) -> Path:
    """Generates an image locally based on prompt and parameters using SDXL on GPU with procedural fallback."""
    if output_path is None:
        output_path = MEDIA_DIR / f"{uuid.uuid4().hex}.png"
        
    pipe = get_sdxl_pipeline()
    if pipe is not None:
        try:
            with _gpu_lock:
                import torch
                print(f"[Generators] Running local SDXL GPU generation (model: {model_name or 'sd_xl_base_1.0'}) for: {prompt[:80]}...")
                # Snap width & height to valid multiples of 64
                w = max(512, min(1024, (width // 64) * 64))
                h = max(512, min(1024, (height // 64) * 64))
                # Run diffusion inference
                result = pipe(
                    prompt=prompt,
                    negative_prompt="blurry, distorted, low quality, artifacts, watermark",
                    num_inference_steps=20,
                    width=w,
                    height=h
                )
                img = result.images[0]
                img.save(output_path, "PNG")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                print(f"[Generators] SDXL successfully generated -> {output_path.name}")
                return output_path
        except Exception as e:
            print(f"[Generators] SDXL generation error ({e}), using fallback generator...")

    # Fallback procedural generation
    img = Image.new("RGBA", (width, height), color=(20, 24, 33, 255))
    draw = ImageDraw.Draw(img)
    
    # Aesthetic procedural background with gradient layers
    for y in range(height):
        ratio = y / height
        r = int(18 + 40 * ratio)
        g = int(22 + 50 * ratio * (1 - ratio) * 4)
        b = int(36 + 60 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        
    # If a reference image is provided (for inpainting / remixing), composite it
    if ref_image_path and Path(ref_image_path).exists():
        try:
            ref = Image.open(ref_image_path).convert("RGBA")
            ref = ref.resize((int(width * 0.8), int(height * 0.8)), Image.Resampling.LANCZOS)
            offset_x = int((width - ref.width) / 2)
            offset_y = int((height - ref.height) / 2)
            img.alpha_composite(ref, (offset_x, offset_y))
        except Exception as e:
            print("Error compositing reference image:", e)

    # Stylized central badge/art rendering with prompt info
    margin = 40
    badge_rect = [margin, height - 120, width - margin, height - margin]
    draw.rounded_rectangle(badge_rect, radius=16, fill=(10, 14, 20, 220), outline=(50, 100, 240, 200), width=2)
    
    # Text overlay
    short_prompt = prompt if len(prompt) <= 60 else prompt[:57] + "..."
    draw.text((margin + 20, height - 105), "ArtCraft Local Generator [Unlocked]", fill=(90, 160, 255, 255))
    draw.text((margin + 20, height - 80), f"Prompt: {short_prompt}", fill=(230, 235, 245, 255))
    
    img.save(output_path, "PNG")
    return output_path

def generate_video_locally(prompt: str, start_frame_path: Path = None, duration_sec: int = 4, output_path: Path = None) -> Path:
    """Generates an MP4 video locally with animated keyframing, SDXL keyframes, procedural fluid motion, and web-standard H.264 encoding."""
    if output_path is None:
        output_path = MEDIA_DIR / f"{uuid.uuid4().hex}.mp4"
        
    import cv2
    fps = 24
    total_frames = fps * duration_sec
    w, h = 768, 432
    
    # If no start frame provided, generate a photorealistic keyframe using local SDXL
    base_pil = None
    if start_frame_path and Path(start_frame_path).exists():
        try:
            base_pil = Image.open(start_frame_path).convert("RGB")
        except Exception as e:
            print("Error loading start frame:", e)
            
    if base_pil is None:
        temp_thumb = MEDIA_DIR / f"{output_path.stem}_keyframe.png"
        try:
            print(f"[Generators] Generating initial keyframe for video prompt: {prompt[:60]}...")
            generate_image_locally(prompt, width=w, height=h, output_path=temp_thumb)
            if temp_thumb.exists():
                base_pil = Image.open(temp_thumb).convert("RGB")
        except Exception as e:
            print("[Generators] Keyframe generation fallback:", e)
            
    if base_pil is not None:
        base_pil = base_pil.resize((w, h), Image.Resampling.LANCZOS)
    else:
        # Fallback gradient image
        base_pil = Image.new("RGB", (w, h), color=(30, 40, 60))
        
    img_start = cv2.cvtColor(np.array(base_pil), cv2.COLOR_RGB2BGR)

    # Attempt to synthesize an evolved motion frame using SDXL Img2Img conditioned on prompt
    img_end = None
    img2img = get_sdxl_img2img_pipeline()
    if img2img is not None and prompt and len(prompt.strip()) > 0:
        try:
            with _gpu_lock:
                print(f"[Generators] Synthesizing evolved motion keyframe with SDXL for: {prompt[:60]}...")
                res = img2img(
                    prompt=prompt,
                    negative_prompt="blurry, distorted, low quality, artifacts, watermark",
                    image=base_pil,
                    strength=0.45,
                    num_inference_steps=12,
                )
                evolved_pil = res.images[0].resize((w, h), Image.Resampling.LANCZOS)
                img_end = cv2.cvtColor(np.array(evolved_pil), cv2.COLOR_RGB2BGR)
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                print("[Generators] Motion keyframe synthesis complete!")
        except Exception as e:
            print(f"[Generators] Motion keyframe synthesis fallback: {e}")

    # Always save a still thumbnail image for the UI gallery card
    still_path = MEDIA_DIR / f"{output_path.stem}_still.png"
    cv2.imwrite(str(still_path), img_start)

    # Use ffmpeg to encode clean, web-compliant H.264 video with faststart
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "22",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    mesh_x, mesh_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    # Dense optical flow computation between start and evolved frame
    flow_fwd = None
    flow_bwd = None
    if img_end is not None:
        try:
            gray_start = cv2.cvtColor(img_start, cv2.COLOR_BGR2GRAY)
            gray_end = cv2.cvtColor(img_end, cv2.COLOR_BGR2GRAY)
            flow_fwd = cv2.calcOpticalFlowFarneback(gray_start, gray_end, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            flow_bwd = cv2.calcOpticalFlowFarneback(gray_end, gray_start, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        except Exception as e:
            print("[Generators] Optical flow fallback:", e)

    # Detect prompt motion kinematics
    p_lower = prompt.lower() if prompt else ""
    is_walking = any(k in p_lower for k in ["walk", "run", "step", "stride", "forward", "approach", "pacing", "beach"])
    is_falling = any(k in p_lower for k in ["fall", "down", "drop", "dive", "sink", "water", "plunge", "tumble"])
    is_pan_left = any(k in p_lower for k in ["pan left", "look left", "turn left"])
    is_pan_right = any(k in p_lower for k in ["pan right", "look right", "turn right"])

    for i in range(total_frames):
        alpha = i / max(1, total_frames - 1)
        # Smooth ease-in-out curve
        progress = (1.0 - math.cos(alpha * math.pi)) / 2.0
        
        # 1. Optical-flow motion morph (warps pixels along flow trajectory rather than alpha ghosting)
        if img_end is not None and flow_fwd is not None and flow_bwd is not None:
            fwd_map_x = mesh_x + flow_fwd[..., 0] * progress
            fwd_map_y = mesh_y + flow_fwd[..., 1] * progress
            warped_start = cv2.remap(img_start, fwd_map_x, fwd_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            
            bwd_map_x = mesh_x + flow_bwd[..., 0] * (1.0 - progress)
            bwd_map_y = mesh_y + flow_bwd[..., 1] * (1.0 - progress)
            warped_end = cv2.remap(img_end, bwd_map_x, bwd_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            
            current_img = cv2.addWeighted(warped_start, 1.0 - progress, warped_end, progress, 0.0)
        elif img_end is not None:
            current_img = cv2.addWeighted(img_start, 1.0 - progress, img_end, progress, 0.0)
        else:
            current_img = img_start.copy()

        # 2. Dynamic Camera Kinematics (Prompt-directed motion without gelatin warp)
        scale = 1.0 + 0.12 * progress
        center_x = w / 2.0
        center_y = h / 2.0
        angle = 0.0

        if is_walking:
            # Rhythmic walking cadence: ~2 steps per second
            cadence = alpha * duration_sec * 2.0 * math.pi
            vertical_bob = math.sin(cadence) * 5.0
            horizontal_sway = math.cos(cadence * 0.5) * 6.0
            center_y += vertical_bob
            center_x += horizontal_sway
            angle += math.sin(cadence * 0.5) * 0.7
            scale = 1.0 + 0.18 * progress

        if is_falling:
            # Pitch down and plunge perspective forward
            fall_phase = max(0.0, (alpha - 0.45) / 0.55)
            fall_intensity = fall_phase * fall_phase
            center_y -= fall_intensity * 55.0  # Camera dips down towards water/ground
            angle += fall_intensity * 3.0
            scale += fall_intensity * 0.22

        if is_pan_left:
            center_x += progress * 40.0
        elif is_pan_right:
            center_x -= progress * 40.0

        M = cv2.getRotationMatrix2D((center_x, center_y), angle, scale)
        frame = cv2.warpAffine(current_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        
        proc.stdin.write(frame.tobytes())
        
    proc.stdin.close()
    proc.wait()
    print(f"[Generators] Video generation complete -> {output_path.name}")

    # Generate an animated WebP preview loop for ArtCraft feed cards
    anim_path = MEDIA_DIR / f"{output_path.stem}_anim.webp"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(output_path),
            "-vf", "fps=12,scale=384:-1:flags=lanczos",
            "-loop", "0", str(anim_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[Generators] Animated WebP preview generated -> {anim_path.name}")
    except Exception as e:
        print(f"[Generators] Warning: Failed to generate animated WebP preview: {e}")

    return output_path
    return output_path

def generate_3d_mesh_locally(prompt: str, image_path: Path = None, output_path: Path = None) -> Path:
    """Generates a binary GLB (GLTF 2.0) 3D mesh viewable in ArtCraft's Three.js viewport."""
    if output_path is None:
        output_path = MEDIA_DIR / f"{uuid.uuid4().hex}.glb"
        
    if image_path and Path(image_path).exists():
        try:
            # Construct a relief heightmap mesh from the image luminance
            pil_img = Image.open(image_path).convert("L")
            pil_img = pil_img.resize((64, 64), Image.Resampling.BILINEAR)
            arr = np.array(pil_img, dtype=np.float32) / 255.0
            
            # Create grid vertices
            x = np.linspace(-1, 1, 64)
            y = np.linspace(-1, 1, 64)
            xx, yy = np.meshgrid(x, y)
            zz = (arr - 0.5) * 0.4
            
            vertices = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
            
            # Create triangular faces
            faces = []
            for i in range(63):
                for j in range(63):
                    idx = i * 64 + j
                    faces.append([idx, idx + 1, idx + 64])
                    faces.append([idx + 1, idx + 65, idx + 64])
                    
            mesh = trimesh.Trimesh(vertices=vertices, faces=np.array(faces))
            mesh.visual.vertex_colors = [120, 160, 255, 255]
            glb_data = mesh.export(file_type='glb')
            with open(output_path, "wb") as f:
                f.write(glb_data)
            return output_path
        except Exception as e:
            print("Error creating 3D relief mesh:", e)
            
    # Default procedural 3D sculpture
    mesh = trimesh.creation.torus(major_radius=1.0, minor_radius=0.3, major_sections=32, minor_sections=16)
    mesh.visual.vertex_colors = [100, 180, 255, 255]
    glb_data = mesh.export(file_type='glb')
    with open(output_path, "wb") as f:
        f.write(glb_data)
        
    return output_path

def generate_gaussian_splat_locally(prompt: str, image_path: Path = None, output_path: Path = None) -> Path:
    """Generates a valid 3D Gaussian Splat PLY file readable by ArtCraft's Three.js viewer."""
    if output_path is None:
        output_path = MEDIA_DIR / f"{uuid.uuid4().hex}.ply"
        
    num_points = 2500
    # Create point cloud points
    theta = np.linspace(0, 4 * np.pi, num_points)
    z = np.linspace(-1, 1, num_points)
    r = 0.8 * (1.0 - z**2 * 0.5)
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    
    # Splat header
    header = f"""ply
format binary_little_endian 1.0
element vertex {num_points}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
    with open(output_path, "wb") as f:
        f.write(header.encode("ascii"))
        for i in range(num_points):
            px, py, pz = float(x[i]), float(y[i]), float(z[i])
            # binary struct: 17 floats
            data = struct.pack(
                "<17f",
                px, py, pz, # x, y, z
                0.0, 0.0, 1.0, # nx, ny, nz
                0.8, 0.4, 0.2, # color spherical harmonics
                1.0, # opacity
                -3.5, -3.5, -3.5, # log scale
                1.0, 0.0, 0.0, 0.0 # quaternion rotation
            )
            f.write(data)
            
    return output_path
