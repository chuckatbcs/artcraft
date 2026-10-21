import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "ArtCraft/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())

def post(path, body):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "ArtCraft/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode())

def test_all():
    print("Testing ArtCraft Local Engine Endpoints...")
    
    # 1. Health
    s, r = get("/health")
    assert s == 200 and r["status"] == "ok"
    print(" [PASS] Health check")
    
    # 1b. Session & Authentication (Zero Paywall / Auto-login)
    s, r = get("/v1/session")
    assert s == 200 and r["logged_in"] is True and r["user"]["can_access_studio"] is True
    print(f" [PASS] Session endpoint: logged in as {r['user']['username']} ({r['user']['display_name']}), studio access unlocked")

    s, r = post("/v1/login", {"username_or_email": "local", "password": "password"})
    assert s == 200 and r["success"] is True and "signed_session" in r
    print(" [PASS] Login fallback endpoint: instant authentication success")
    
    # 2. Credits
    s, r = get("/v1/credits/namespace/artcraft")
    assert s == 200 and r["sum_total_credits"] > 1000000
    print(f" [PASS] Credits endpoint: {r['sum_total_credits']:,} free credits available")
    
    # 3. Subscriptions
    s, r = get("/v1/subscriptions/namespace/artcraft")
    assert s == 200 and r["active_subscription"]["status"] == "active"
    print(f" [PASS] Subscriptions endpoint: {r['active_subscription']['tier']} tier active")
    
    # 4. Models
    s, r = get("/v1/omni_gen/models/image")
    assert s == 200 and len(r["models"]) > 0
    print(f" [PASS] Image models: {[m['model'] for m in r['models']]}")
    
    s, r = get("/v1/omni_gen/models/video")
    assert s == 200 and len(r["models"]) > 0
    print(f" [PASS] Video models: {[m['model'] for m in r['models']]}")
    
    # 5. Cost estimate
    s, r = post("/v1/omni_gen/cost/image", {"prompt": "A fantasy landscape", "model": "flux_1_dev"})
    assert s == 200 and r["is_free"] is True and r["cost_in_credits"] == 0
    print(" [PASS] Cost estimation (0 credits, free unlocked)")
    
    # 6. Generate Image
    s, r_img = post("/v1/omni_gen/generate/image", {"prompt": "A majestic cybernetic lion in neon forest"})
    assert s == 200 and r_img["success"] is True
    job_img = r_img["inference_job_token"]
    print(f" [PASS] Enqueued Image generation -> {job_img}")
    
    # 7. Generate Video
    s, r_vid = post("/v1/omni_gen/generate/video", {"prompt": "Ocean waves at sunrise with smooth slow motion"})
    assert s == 200 and r_vid["success"] is True
    job_vid = r_vid["inference_job_token"]
    print(f" [PASS] Enqueued Video generation -> {job_vid}")
    
    # 8. Generate 3D Mesh
    s, r_mesh = post("/v1/generate/object/hunyuan_2.0_image_to_3d", {"prompt": "Sculpted golden crystal relic"})
    assert s == 200 and r_mesh["success"] is True
    job_mesh = r_mesh["inference_job_token"]
    print(f" [PASS] Enqueued 3D Mesh generation -> {job_mesh}")
    
    # 9. Generate Gaussian Splat
    s, r_splat = post("/v1/generate/splat/worldlabs_marble_0p1_mini", {"prompt": "Ancient mossy stone archway"})
    assert s == 200 and r_splat["success"] is True
    job_splat = r_splat["inference_job_token"]
    print(f" [PASS] Enqueued 3D Splat generation -> {job_splat}")
    
    # 10. Wait and Poll Jobs Session
    print(" Waiting for local engines to finish generation jobs...")
    time.sleep(2)
    s, r_jobs = get("/v1/jobs/session")
    assert s == 200 and len(r_jobs["jobs"]) >= 4
    
    completed = [j for j in r_jobs["jobs"] if j["status"]["status"] == "complete_success"]
    print(f" [PASS] Jobs session returned {len(r_jobs['jobs'])} total jobs, {len(completed)} completed")
    
    for c in completed:
        entity_token = c["maybe_result"]["entity_token"]
        cdn_url = c["maybe_result"]["media_links"]["cdn_url"]
        print(f"   * Result {c['request']['inference_category']}: {cdn_url}")
        # Test downloading file
        req = urllib.request.Request(cdn_url, headers={"User-Agent": "ArtCraft/1.0"})
        with urllib.request.urlopen(req, timeout=5) as m_resp:
            body = m_resp.read()
            print(f"     Downloaded {len(body):,} bytes ({m_resp.headers.get('Content-Type')})")
            
    print("\nALL VERIFICATION CHECKS PASSED 100%!")

if __name__ == "__main__":
    test_all()
