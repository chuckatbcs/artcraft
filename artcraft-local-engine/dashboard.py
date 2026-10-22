DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ArtCraft AI Provider & Model Hub</title>
  <style>
    :root {
      --bg: #0d0f12;
      --card-bg: #14171d;
      --card-border: #232834;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --error: #ef4444;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --font-mono: 'Geist Mono', monospace, ui-monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;
      padding: 24px;
    }
    .container {
      max-width: 1040px;
      margin: 0 auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .logo-area { display: flex; align-items: center; gap: 12px; }
    .logo-badge {
      background: var(--primary);
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 14px;
      letter-spacing: 0.5px;
    }
    h1 { font-size: 22px; font-weight: 700; }
    p.subtitle { color: var(--text-muted); font-size: 14px; }
    
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 13px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-dot {
      width: 8px; height: 8px; border-radius: 50%; background: var(--success);
      box-shadow: 0 0 8px var(--success);
    }
    
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }
    
    .mode-select { display: flex; gap: 16px; align-items: center; }
    .mode-select label { font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
    
    .grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
    
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
      transition: border-color 0.2s;
    }
    .card.active { border-color: var(--primary); }
    
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .card-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 17px;
      font-weight: 600;
    }
    
    .toggle-switch {
      position: relative;
      display: inline-block;
      width: 44px;
      height: 24px;
    }
    .toggle-switch input { opacity: 0; width: 0; height: 0; }
    .slider {
      position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
      background-color: #374151; transition: .2s; border-radius: 24px;
    }
    .slider:before {
      position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px;
      background-color: white; transition: .2s; border-radius: 50%;
    }
    input:checked + .slider { background-color: var(--primary); }
    input:checked + .slider:before { transform: translateX(20px); }
    
    .form-group { margin-bottom: 14px; }
    .form-group label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 6px; }
    .form-control {
      width: 100%;
      background: #0d0f12;
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 14px;
      font-family: inherit;
    }
    .form-control:focus { outline: none; border-color: var(--primary); }
    
    .row { display: flex; gap: 12px; }
    .col { flex: 1; }
    
    .actions { display: flex; gap: 10px; align-items: center; margin-top: 14px; }
    
    button {
      background: var(--primary);
      color: #fff;
      border: none;
      padding: 9px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }
    button:hover { background: var(--primary-hover); }
    button.secondary {
      background: #232834;
      color: var(--text);
    }
    button.secondary:hover { background: #323846; }
    button.success { background: var(--success); }
    
    .test-result {
      font-size: 13px;
      margin-top: 8px;
      padding: 8px 12px;
      border-radius: 6px;
      display: none;
    }
    .test-result.ok { display: block; background: rgba(16, 185, 129, 0.12); color: var(--success); }
    .test-result.err { display: block; background: rgba(239, 68, 68, 0.12); color: var(--error); }
    
    .model-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .pill {
      background: #1a1e27;
      border: 1px solid var(--card-border);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 12px;
      font-family: var(--font-mono);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .pill input { cursor: pointer; }
    
    .tab-btn {
      background: #1a1e27;
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 6px 14px;
      font-size: 13px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s ease;
    }
    .tab-btn:hover {
      color: var(--text);
      border-color: var(--primary);
    }
    .tab-btn.active {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }
    
    .save-banner {
      position: sticky;
      bottom: 24px;
      background: #1e2430;
      border: 1px solid var(--primary);
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      border-radius: 8px;
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 28px;
      z-index: 100;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo-area">
        <div class="logo-badge">ARTCRAFT</div>
        <div>
          <h1>AI Provider & Model Hub</h1>
          <p class="subtitle">Configure OpenAI, OpenRouter, and Local GPU endpoints for ArtCraft with zero paywalls.</p>
        </div>
      </div>
      <div>
        <div class="status-badge">
          <div class="status-dot"></div>
          Local Engine Connected (Port 8000)
        </div>
      </div>
    </header>

    <div class="toolbar">
      <div class="mode-select">
        <label>
          <input type="radio" name="combine_mode" id="mode_combine" checked onchange="saveMode(true)">
          <strong>Unified Provider Mode (Recommended):</strong> Show enabled models from all providers simultaneously in ArtCraft
        </label>
      </div>
      <div>
        <button type="button" class="secondary" onclick="openArtcraft()">Launch ArtCraft App</button>
      </div>
    </div>

    <div class="grid">
      <!-- 1. OpenAI Card -->
      <div class="card" id="card_openai">
        <div class="card-header">
          <div class="card-title">
            <span>🌐 OpenAI (Subscription & Direct API)</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="openai_enabled" onchange="toggleProvider('openai', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-group">
          <label>OpenAI API Key</label>
          <input type="password" id="openai_key" class="form-control" placeholder="sk-proj-..." onchange="markUnsaved()">
        </div>
        <div class="row">
          <div class="col form-group">
            <label>API Base URL</label>
            <input type="text" id="openai_base_url" class="form-control" value="https://api.openai.com/v1" onchange="markUnsaved()">
          </div>
          <div class="col form-group">
            <label>Organization ID (Optional)</label>
            <input type="text" id="openai_org" class="form-control" placeholder="org-..." onchange="markUnsaved()">
          </div>
        </div>
        <div class="form-group">
          <label>Models available in ArtCraft</label>
          <div class="model-pills">
            <span class="pill"><input type="checkbox" id="openai_m_dall_e_3" checked> dall-e-3 (1024x1024)</span>
            <span class="pill"><input type="checkbox" id="openai_m_dall_e_2" checked> dall-e-2</span>
            <span class="pill"><input type="checkbox" id="openai_m_gpt_4o" checked> gpt-4o (Vision)</span>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="secondary" onclick="testConnection('openai')">Test OpenAI Key</button>
          <div id="openai_test_result" class="test-result"></div>
        </div>
      </div>

      <!-- 2. OpenRouter Card -->
      <div class="card" id="card_openrouter">
        <div class="card-header">
          <div class="card-title">
            <span>🔀 OpenRouter (Multi-Model Cloud Hub)</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="openrouter_enabled" onchange="toggleProvider('openrouter', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="form-group">
          <label>OpenRouter API Key</label>
          <input type="password" id="openrouter_key" class="form-control" placeholder="sk-or-v1-..." onchange="markUnsaved()">
        </div>
        <div class="form-group">
          <label>Active OpenRouter Models in ArtCraft Dropdown</label>
          <div class="model-pills" id="openrouter_pills">
            <span class="pill"><input type="checkbox" id="or_m_flux_dev" value="black-forest-labs/flux-1-dev" checked> Flux 1.0 Dev</span>
            <span class="pill"><input type="checkbox" id="or_m_flux_schnell" value="black-forest-labs/flux-1-schnell" checked> Flux 1.0 Schnell</span>
            <span class="pill"><input type="checkbox" id="or_m_recraft" value="recraft-ai/recraft-v3" checked> Recraft V3</span>
            <span class="pill"><input type="checkbox" id="or_m_sdxl" value="stabilityai/stable-diffusion-xl-base-1.0" checked> SDXL Base</span>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="secondary" onclick="testConnection('openrouter')">Test OpenRouter Key</button>
          <button type="button" class="secondary" onclick="fetchRemoteModels('openrouter')">Fetch Remote Models List</button>
          <div id="openrouter_test_result" class="test-result"></div>
        </div>
      </div>

      <!-- 3. Local ComfyUI GPU Card -->
      <div class="card" id="card_local_comfyui">
        <div class="card-header">
          <div class="card-title">
            <span>⚡ Local GPU (ComfyUI / RTX 4060 Ti)</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="local_comfyui_enabled" checked onchange="toggleProvider('local_comfyui', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="row">
          <div class="col form-group">
            <label>ComfyUI Server Endpoint</label>
            <input type="text" id="comfyui_url" class="form-control" value="http://127.0.0.1:20140" onchange="markUnsaved()">
          </div>
          <div class="col form-group">
            <label>Checkpoints Directory</label>
            <input type="text" id="comfyui_checkpoints_dir" class="form-control" value="B:\AI Directory\ComfyUI\models\checkpoints" onchange="markUnsaved()">
          </div>
        </div>
        <div class="form-group">
          <label>Discovered Local Checkpoints (.safetensors)</label>
          <div class="model-pills" id="checkpoints_pills">
            <span class="pill"><input type="checkbox" checked disabled> sd_xl_base_1.0.safetensors (Active GPU Checkpoint)</span>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="secondary" onclick="testConnection('local_comfyui')">Test Local ComfyUI Status</button>
          <div id="local_comfyui_test_result" class="test-result"></div>
        </div>
      </div>

      <!-- 4. OmniRoute Gateway Card -->
      <div class="card" id="card_omniroute">
        <div class="card-header">
          <div class="card-title">
            <span>🎯 OmniRoute Gateway</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="omniroute_enabled" onchange="toggleProvider('omniroute', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="row">
          <div class="col form-group">
            <label>OmniRoute Base URL <small style="color: var(--accent); font-weight: normal;">(Use http://127.0.0.1:20128/v1 — do not use https)</small></label>
            <input type="text" id="omniroute_url" class="form-control" value="http://127.0.0.1:20128/v1" onchange="markUnsaved()">
          </div>
          <div class="col form-group">
            <label>Auth Token / API Key</label>
            <input type="password" id="omniroute_key" class="form-control" placeholder="Token if required" onchange="markUnsaved()">
          </div>
        </div>
        <div class="actions">
          <button type="button" class="secondary" onclick="testConnection('omniroute')">Test OmniRoute</button>
          <div id="omniroute_test_result" class="test-result"></div>
        </div>
      </div>

      <!-- 5. Context-Relative Active Models Filter & Catalog -->
      <div class="card" style="grid-column: 1 / -1;">
        <div class="card-header">
          <div class="card-title">
            <span>🎛️ Context-Relative Model Filter & Live Catalogs</span>
          </div>
          <div style="font-size: 13px; color: var(--text-muted);" id="catalog_stats">
            Loading catalog...
          </div>
        </div>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
          ArtCraft automatically isolates models by application context: you only see image models in the <strong>Create Image</strong> app, video models in the <strong>Video</strong> app, and audio models in the <strong>Sound</strong> app. Pure text/code LLMs are excluded.
        </p>

        <!-- Filter Controls -->
        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; align-items: center;">
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button type="button" class="tab-btn active" id="tab_image" onclick="switchModalityTab('image')">🖼️ Image Models</button>
            <button type="button" class="tab-btn" id="tab_video" onclick="switchModalityTab('video')">🎬 Video Models</button>
            <button type="button" class="tab-btn" id="tab_mesh" onclick="switchModalityTab('mesh')">🧊 3D Models</button>
            <button type="button" class="tab-btn" id="tab_splat" onclick="switchModalityTab('splat')">🌐 Splat Models</button>
            <button type="button" class="tab-btn" id="tab_audio" onclick="switchModalityTab('audio')">🔊 Audio Models</button>
          </div>
          <div style="flex: 1; min-width: 220px;">
            <input type="text" id="model_search" class="form-control" placeholder="🔍 Filter active models..." oninput="filterCatalogDisplay()">
          </div>
        </div>

        <div id="catalog_list_container" style="max-height: 280px; overflow-y: auto; background: #161a23; padding: 12px; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--text-muted); font-size: 13px;">Loading catalog models...</div>
        </div>
      </div>
    </div>

    <!-- Save Floating Banner -->
    <div class="save-banner">
      <div>
        <strong>Save Changes</strong>
        <p style="font-size: 13px; color: var(--text-muted);">Settings take effect immediately in ArtCraft's model picker.</p>
      </div>
      <div style="display: flex; gap: 12px;">
        <button type="button" class="success" onclick="saveAllSettings()">💾 Save & Apply to ArtCraft</button>
      </div>
    </div>
  </div>

  <script>
    let currentConfig = {};

    async function loadConfig() {
      try {
        const res = await fetch('/v1/ai/providers');
        const data = await res.json();
        currentConfig = data;
        
        // Mode
        if (data.combine_all_enabled !== undefined) {
          document.getElementById('mode_combine').checked = data.combine_all_enabled;
        }

        const provs = data.providers || {};
        
        // OpenAI
        if (provs.openai) {
          document.getElementById('openai_enabled').checked = !!provs.openai.enabled;
          if (provs.openai.api_key && provs.openai.api_key !== '****') {
            document.getElementById('openai_key').value = provs.openai.api_key;
          }
          if (provs.openai.base_url) {
            document.getElementById('openai_base_url').value = provs.openai.base_url;
          }
          if (provs.openai.organization_id) {
            document.getElementById('openai_org').value = provs.openai.organization_id;
          }
        }
        
        // OpenRouter
        if (provs.openrouter) {
          document.getElementById('openrouter_enabled').checked = !!provs.openrouter.enabled;
          if (provs.openrouter.api_key && provs.openrouter.api_key !== '****') {
            document.getElementById('openrouter_key').value = provs.openrouter.api_key;
          }
        }

        // Local ComfyUI
        if (provs.local_comfyui) {
          document.getElementById('local_comfyui_enabled').checked = !!provs.local_comfyui.enabled;
          if (provs.local_comfyui.url) {
            document.getElementById('comfyui_url').value = provs.local_comfyui.url;
          }
          if (provs.local_comfyui.checkpoints_dir) {
            document.getElementById('comfyui_checkpoints_dir').value = provs.local_comfyui.checkpoints_dir;
          }
        }

        // OmniRoute
        if (provs.omniroute) {
          document.getElementById('omniroute_enabled').checked = !!provs.omniroute.enabled;
          if (provs.omniroute.base_url) {
            document.getElementById('omniroute_url').value = provs.omniroute.base_url;
          }
        }
      } catch (e) {
        console.error("Failed to load config:", e);
      }
    }

    function markUnsaved() {}

    async function toggleProvider(provKey, enabled) {
      markUnsaved();
    }

    async function saveAllSettings() {
      const payload = {
        combine_all_enabled: document.getElementById('mode_combine').checked,
        providers: {
          openai: {
            enabled: document.getElementById('openai_enabled').checked,
            api_key: document.getElementById('openai_key').value.trim(),
            base_url: document.getElementById('openai_base_url').value.trim(),
            organization_id: document.getElementById('openai_org').value.trim(),
            enabled_models: ['dall-e-3', 'dall-e-2', 'gpt-4o']
          },
          openrouter: {
            enabled: document.getElementById('openrouter_enabled').checked,
            api_key: document.getElementById('openrouter_key').value.trim(),
            base_url: 'https://openrouter.ai/api/v1',
            enabled_models: [
              'black-forest-labs/flux-1-dev',
              'black-forest-labs/flux-1-schnell',
              'recraft-ai/recraft-v3',
              'stabilityai/stable-diffusion-xl-base-1.0'
            ]
          },
          local_comfyui: {
            enabled: document.getElementById('local_comfyui_enabled').checked,
            url: document.getElementById('comfyui_url').value.trim(),
            checkpoints_dir: document.getElementById('comfyui_checkpoints_dir').value.trim()
          },
          omniroute: {
            enabled: document.getElementById('omniroute_enabled').checked,
            base_url: document.getElementById('omniroute_url').value.trim(),
            api_key: document.getElementById('omniroute_key').value.trim()
          }
        }
      };

      try {
        const res = await fetch('/v1/ai/providers/full_save', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const out = await res.json();
        if (out.success) {
          alert('Settings saved successfully! Model listings have been refreshed for ArtCraft.');
          loadConfig();
        } else {
          alert('Save error: ' + (out.error || 'Unknown error'));
        }
      } catch (e) {
        alert('Network error saving settings: ' + e);
      }
    }

    async function testConnection(provKey) {
      const resultEl = document.getElementById(provKey + '_test_result');
      resultEl.className = 'test-result';
      resultEl.style.display = 'block';
      resultEl.textContent = 'Testing connection...';

      // Pass currently typed key and URL for immediate verification
      let key = '';
      let url = '';
      if (provKey === 'openai') {
        key = document.getElementById('openai_key').value.trim();
        url = document.getElementById('openai_base_url').value.trim();
      }
      if (provKey === 'openrouter') {
        key = document.getElementById('openrouter_key').value.trim();
      }
      if (provKey === 'local_comfyui') {
        url = document.getElementById('comfyui_url').value.trim();
      }
      if (provKey === 'omniroute') {
        key = document.getElementById('omniroute_key').value.trim();
        url = document.getElementById('omniroute_url').value.trim();
      }

      try {
        const res = await fetch('/v1/ai/test', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ provider: provKey, api_key: key, base_url: url })
        });
        const data = await res.json();
        if (data.success) {
          resultEl.className = 'test-result ok';
          resultEl.textContent = '✅ ' + (data.message || 'Connected successfully!');
        } else {
          resultEl.className = 'test-result err';
          resultEl.textContent = '❌ ' + (data.error || 'Connection failed.');
        }
      } catch (e) {
        resultEl.className = 'test-result err';
        resultEl.textContent = '❌ Test failed: ' + e;
      }
    }

    function openArtcraft() {
      fetch('/v1/dev/launch_app');
    }

    let currentModality = 'image';
    let cachedCatalog = { image: [], video: [], mesh: [], splat: [], audio: [] };

    async function loadCatalog(modality = 'image') {
      currentModality = modality;
      const container = document.getElementById('catalog_list_container');
      container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">Fetching models for ' + modality + '...</div>';
      try {
        const res = await fetch('/v1/ai/catalog?modality=' + modality);
        const data = await res.json();
        const models = data.models || [];
        cachedCatalog[modality] = models;
        renderCatalog(models);
      } catch (e) {
        container.innerHTML = '<div style="color: var(--error); font-size: 13px;">Failed to load catalog: ' + e + '</div>';
      }
    }

    function switchModalityTab(modality) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById('tab_' + modality);
      if (activeBtn) activeBtn.classList.add('active');
      loadCatalog(modality);
    }

    function renderCatalog(models) {
      const container = document.getElementById('catalog_list_container');
      const stats = document.getElementById('catalog_stats');
      const q = (document.getElementById('model_search')?.value || '').toLowerCase().trim();
      
      const filtered = models.filter(m => {
        if (!q) return true;
        return (m.full_name || '').toLowerCase().includes(q) || (m.model || '').toLowerCase().includes(q) || (m.model_creator || '').toLowerCase().includes(q);
      });

      stats.textContent = `${filtered.length} of ${models.length} ${currentModality.toUpperCase()} models active in ArtCraft`;

      if (filtered.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No models match your search.</div>';
        return;
      }

      let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 8px;">';
      for (const m of filtered) {
        const creatorBadge = m.model_creator || 'artcraft';
        html += `
          <div style="background: #1e2430; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center;">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px;">
              <strong style="font-size: 13px; color: var(--text);">${m.full_name || m.model}</strong>
              <div style="font-size: 11px; color: var(--text-muted);">${m.model}</div>
            </div>
            <span style="font-size: 10px; background: rgba(99,102,241,0.18); color: var(--primary); padding: 2px 8px; border-radius: 12px; text-transform: uppercase; font-weight: 600;">${creatorBadge}</span>
          </div>
        `;
      }
      html += '</div>';
      container.innerHTML = html;
    }

    function filterCatalogDisplay() {
      if (cachedCatalog[currentModality]) {
        renderCatalog(cachedCatalog[currentModality]);
      }
    }

    window.onload = () => {
      loadConfig();
      loadCatalog('image');
    };
  </script>
</body>
</html>
"""
