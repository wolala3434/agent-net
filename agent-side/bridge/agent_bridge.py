"""
Agent Bridge — 自包含的 LLM 代理，连接平台和用户 LLM 服务。

内置配置界面: 浏览器打开 http://localhost:9140 即可配置，不需要命令行。

用法:
  python agent_bridge.py [--port 9140]
  # 然后打开 http://localhost:9140 进行配置

配置默认保存在用户配置目录，重启后自动加载。
"""

import argparse
import json
import os
import platform
import uuid
from pathlib import Path

import httpx
import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE_DIR = Path(__file__).parent


def default_bridge_home() -> Path:
    """Return the user-scoped runtime directory for Bridge config and UI."""
    override = os.getenv("AGENT_BRIDGE_HOME")
    if override:
        return Path(override).expanduser()

    system = platform.system().lower()
    if system == "windows":
        base = os.getenv("APPDATA")
        if base:
            return Path(base) / "AgentInternet" / "bridge"
    elif system == "darwin":
        return Path.home() / "Library" / "Application Support" / "agent-internet" / "bridge"

    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "agent-internet" / "bridge"
    return Path.home() / ".config" / "agent-internet" / "bridge"


BRIDGE_HOME = default_bridge_home()
CONFIG_FILE = BRIDGE_HOME / "bridge_config.json"
UI_DIR = BRIDGE_HOME / "ui"

DEFAULT_CONFIG = {
    "agent_name": os.getenv("AGENT_NAME", "My Bridge Agent"),
    "agent_description": os.getenv("AGENT_DESCRIPTION", ""),
    "domains": os.getenv("AGENT_DOMAINS", "general"),
    "llm_url": os.getenv("LLM_URL", "http://localhost:8080/v1"),
    "llm_api_key": os.getenv("LLM_API_KEY", ""),
    "llm_model": os.getenv("LLM_MODEL", ""),
    "port": int(os.getenv("AGENT_PORT", "9140")),
    "registry_url": os.getenv("REGISTRY_URL", "http://localhost:8000"),
    "host": os.getenv("AGENT_HOST", "127.0.0.1"),
}

# ═══════════════════════════════════════════════════════════════
# Config persistence
# ═══════════════════════════════════════════════════════════════
def load_config() -> dict:
    if CONFIG_FILE.exists():
        cfg = {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
    else:
        cfg = dict(DEFAULT_CONFIG)
    return cfg


def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_cli_overrides(cfg: dict, args: argparse.Namespace) -> dict:
    """Apply explicit CLI arguments over persisted/default config."""
    mapping = {
        "agent_name": "agent_name",
        "agent_description": "agent_description",
        "domains": "domains",
        "llm_url": "llm_url",
        "api_key": "llm_api_key",
        "llm_model": "llm_model",
        "port": "port",
        "registry": "registry_url",
        "host": "host",
    }
    for arg_name, cfg_key in mapping.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            cfg[cfg_key] = value
    return cfg


# ═══════════════════════════════════════════════════════════════
# LLM call
# ═══════════════════════════════════════════════════════════════
def call_llm(system_prompt: str, user_message: str, cfg: dict) -> str:
    url = f"{cfg['llm_url'].rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.get("llm_api_key"):
        headers["Authorization"] = f"Bearer {cfg['llm_api_key']}"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    if cfg.get("llm_model"):
        payload["model"] = cfg["llm_model"]
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════
# Bridge runtime state
# ═══════════════════════════════════════════════════════════════
class BridgeState:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.registered = False
        self.startup_ok = False
        self.last_error = ""
        self.sessions: dict[str, dict] = {}

    @property
    def agent_id(self):
        slug = self.cfg["agent_name"].lower().replace(" ", "-")
        return f"bridge.{slug}@1.0.0"

    @property
    def domains_list(self):
        return [d.strip() for d in self.cfg["domains"].split(",") if d.strip()]

    def build_adl_card(self):
        base = f"http://{self.cfg['host']}:{self.cfg['port']}"
        domains = self.domains_list
        return {
            "id": self.agent_id,
            "name": self.cfg["agent_name"],
            "version": "1.0.0",
            "description": self.cfg.get("agent_description", ""),
            "provider": {"name": "Agent Bridge"},
            "capabilities": [{
                "id": (domains[0].replace(".", "-") if domains else "general"),
                "name": self.cfg["agent_name"],
                "description": self.cfg.get("agent_description", ""),
                "domains": domains,
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                "output_schema": {"type": "object", "properties": {"response": {"type": "string"}}, "required": ["response"]},
            }],
            "endpoints": {
                "task": f"{base}/api/v1/task",
                "health": f"{base}/api/v1/health",
                "a2a": f"{base}/api/v1/a2a",
            },
            "pricing": {"model": "per_call", "unit_price": 0.01},
            "tags": {"bridge": "true"},
        }

    def register(self):
        try:
            card = self.build_adl_card()
            resp = httpx.post(
                f"{self.cfg['registry_url']}/api/v1/agents/register",
                json=card, timeout=10,
            )
            self.registered = resp.status_code in (200, 201, 409)
            if not self.registered:
                self.last_error = f"Registration failed: {resp.status_code}"
            return self.registered
        except Exception as e:
            self.last_error = str(e)
            return False

    def test_platform(self) -> dict:
        try:
            r = httpx.get(f"{self.cfg['registry_url']}/health", timeout=5)
            return {"ok": r.status_code == 200, "detail": r.json()}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    def test_llm(self) -> dict:
        try:
            resp = call_llm("You are a helpful assistant.", "Say 'OK' in one word.", self.cfg)
            return {"ok": True, "detail": resp[:100]}
        except Exception as e:
            return {"ok": False, "detail": str(e)}


# ═══════════════════════════════════════════════════════════════
# Collaboration prompt
# ═══════════════════════════════════════════════════════════════
COLLAB_PROMPT = """你是一个专业 AI Agent，正在参与多 Agent 协作会议。

你的角色: {agent_description}

## 回应格式
你的回应必须是 JSON: {{"message_type": "propose|critique|clarify|refine|agree|disagree|synthesize", "body": {{...}}, "session_context_update": {{...}}}}

## 上下文
{context}

## 最新消息
{message}

请根据你的专业能力做出 JSON 格式回应。只输出 JSON。"""


# ═══════════════════════════════════════════════════════════════
# FastAPI app
# ═══════════════════════════════════════════════════════════════
def create_app(state: BridgeState) -> FastAPI:
    app = FastAPI(title="Agent Bridge")

    # ── Bridge Config API ────────────────────────────────────
    @app.get("/api/v1/bridge/config")
    async def get_config():
        return {
            "agent_name": state.cfg["agent_name"],
            "agent_description": state.cfg.get("agent_description", ""),
            "domains": state.cfg["domains"],
            "llm_url": state.cfg["llm_url"],
            "llm_api_key": "***" if state.cfg.get("llm_api_key") else "",
            "has_api_key": bool(state.cfg.get("llm_api_key")),
            "llm_model": state.cfg.get("llm_model", ""),
            "port": state.cfg["port"],
            "registry_url": state.cfg["registry_url"],
            "config_path": str(CONFIG_FILE),
        }

    @app.put("/api/v1/bridge/config")
    async def update_config(data: dict):
        for key in ["agent_name", "agent_description", "domains", "llm_url", "llm_model", "registry_url"]:
            if key in data:
                state.cfg[key] = data[key]
        if "llm_api_key" in data and data["llm_api_key"] and data["llm_api_key"] != "***":
            state.cfg["llm_api_key"] = data["llm_api_key"]
        save_config(state.cfg)
        # Re-register with new config
        state.register()
        return {"status": "ok"}

    @app.get("/api/v1/bridge/status")
    async def get_status():
        return {
            "agent_id": state.agent_id,
            "registered": state.registered,
            "startup_ok": state.startup_ok,
            "last_error": state.last_error,
            "platform": state.test_platform(),
            "llm": state.test_llm(),
            "active_sessions": len(state.sessions),
        }

    # ── Agent endpoints ──────────────────────────────────────
    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy", "agent_id": state.agent_id}

    @app.post("/api/v1/task")
    async def task(payload: dict):
        query = payload.get("query", payload.get("input", {}).get("query", str(payload)))
        try:
            resp = call_llm(
                f"You are {state.cfg['agent_name']}. {state.cfg.get('agent_description', '')}",
                query, state.cfg)
            return {"status": "completed", "result": {"response": resp, "mode": "solo"}}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @app.post("/api/v1/a2a")
    async def a2a(payload: dict):
        sid = payload.get("session_id", "")
        msg_type = payload.get("message_type", "propose")
        sender = payload.get("sender", {}).get("agent_id", "?")
        ctx_update = payload.get("session_context_update", {})
        body = payload.get("body", {})

        if sid not in state.sessions:
            state.sessions[sid] = {"history": [], "shared_context": {}}
        sess = state.sessions[sid]
        if ctx_update:
            sess["shared_context"].update(ctx_update)
        sess["history"].append({"turn": payload.get("turn_number", 0), "sender": sender[:30], "type": msg_type,
                                "content": json.dumps(body, ensure_ascii=False)[:300]})

        context_block = json.dumps(sess["shared_context"], ensure_ascii=False)
        prompt = COLLAB_PROMPT.format(
            agent_description=state.cfg.get("agent_description", state.cfg["agent_name"]),
            context=context_block,
            message=f"发送方: {sender}, 类型: {msg_type}, 内容: {json.dumps(body, ensure_ascii=False)}"
        )
        try:
            resp = call_llm(prompt, "请回应", state.cfg)
            resp = resp.strip().removeprefix("```json").removesuffix("```").strip()
            result = json.loads(resp)
        except Exception:
            result = {"message_type": "refine", "body": {"response": resp if 'resp' in dir() else "error"}}

        # Auto-post back
        if result.get("message_type"):
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(
                        f"{state.cfg['registry_url']}/api/v1/collaboration/sessions/{sid}/messages",
                        json={
                            "aip_version": "1.0", "protocol_layer": "collaboration",
                            "message_id": f"resp_{uuid.uuid4().hex[:12]}", "session_id": sid,
                            "timestamp": payload.get("timestamp", ""),
                            "sender": {"agent_id": state.agent_id, "role": "participant"},
                            "message_type": result["message_type"],
                            "body": result.get("body", {}),
                            "session_context_update": result.get("session_context_update", {}),
                            "references": [payload.get("message_id", "")],
                        })
            except Exception:
                pass
        return {"status": "ok", "result": result}

    # ── Serve built-in UI ────────────────────────────────────
    ui_dir = UI_DIR
    assets_dir = ui_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    if (ui_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    return app


# ═══════════════════════════════════════════════════════════════
# Build the UI (one-time setup)
# ═══════════════════════════════════════════════════════════════
UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agent Bridge — 配置面板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}
.header{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;padding:24px 32px}
.header h1{font-size:24px;font-weight:700}.header p{opacity:.85;margin-top:4px;font-size:14px}
.container{max-width:960px;margin:0 auto;padding:24px}
.card{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:24px;margin-bottom:20px}
.card h2{font-size:16px;font-weight:600;margin-bottom:16px;color:#1e293b;border-bottom:1px solid #e2e8f0;padding-bottom:12px}
.row{display:grid;grid-template-columns:1fr 2fr;gap:12px;align-items:center;margin-bottom:14px}
.row label{font-size:14px;font-weight:500;color:#475569}
.row input,.row textarea,.row select{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:14px;transition:border-color .2s}
.row input:focus,.row textarea:focus{border-color:#2563eb;outline:none;box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.row textarea{min-height:80px;resize:vertical}
.actions{display:flex;gap:12px;margin-top:20px}
.btn{padding:10px 24px;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s}
.btn-primary{background:#2563eb;color:#fff}.btn-primary:hover{background:#1d4ed8}
.btn-outline{background:#fff;color:#2563eb;border:2px solid #2563eb}.btn-outline:hover{background:#eff6ff}
.btn-danger{background:#ef4444;color:#fff}.btn-danger:hover{background:#dc2626}
.status-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.stat{background:#f8fafc;border-radius:8px;padding:16px;text-align:center}
.stat-value{font-size:28px;font-weight:700}.stat-label{font-size:12px;color:#64748b;margin-top:4px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.dot-green{background:#22c55e}.dot-red{background:#ef4444}.dot-yellow{background:#eab308}
.toast{position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:8px;color:#fff;font-weight:500;z-index:999;animation:slideIn .3s}
.toast-success{background:#22c55e}.toast-error{background:#ef4444}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
code{background:#1e293b;color:#e2e8f0;padding:2px 8px;border-radius:4px;font-size:13px}
.tabs{display:flex;gap:0;border-bottom:2px solid #e2e8f0;margin-bottom:20px}
.tab{padding:10px 20px;cursor:pointer;font-size:14px;font-weight:500;color:#64748b;border-bottom:2px solid transparent;margin-bottom:-2px}
.tab.active{color:#2563eb;border-bottom-color:#2563eb}
</style>
</head>
<body>
<div class="header"><h1>🤖 Agent Bridge</h1><p>零代码将你的 LLM 服务接入 Agent Internet 协作网络</p></div>
<div class="container">
  <div id="toastContainer"></div>

  <div class="card">
    <div class="tabs"><div class="tab active" onclick="switchTab('config')">⚙️ 配置</div><div class="tab" onclick="switchTab('status')">📊 状态</div><div class="tab" onclick="switchTab('help')">❓ 帮助</div></div>

    <div id="tab-config">
      <h2>Agent 信息</h2>
      <div class="row"><label>Agent 名称</label><input id="cfg_name" placeholder="我的代码审查助手"></div>
      <div class="row"><label>能力描述</label><textarea id="cfg_desc" placeholder="描述你的 Agent 能做什么..."></textarea></div>
      <div class="row"><label>领域 (逗号分隔)</label><input id="cfg_domains" placeholder="code.review,code.security"></div>
      <h2 style="margin-top:20px">LLM 连接</h2>
      <div class="row"><label>LLM API 地址</label><input id="cfg_llm_url" placeholder="http://localhost:8080/v1"></div>
      <div class="row"><label>模型名称 (可选)</label><input id="cfg_model" placeholder="留空使用默认模型"></div>
      <div class="row"><label>API Key</label><input id="cfg_apikey" type="password" placeholder="provider API key"></div>
      <h2 style="margin-top:20px">平台连接</h2>
      <div class="row"><label>平台地址</label><input id="cfg_registry" placeholder="http://localhost:8000"></div>
      <div class="actions">
        <button class="btn btn-primary" onclick="saveConfig()">💾 保存配置</button>
        <button class="btn btn-outline" onclick="testConnection()">🔍 测试连接</button>
      </div>
    </div>

    <div id="tab-status" style="display:none">
      <div class="status-grid">
        <div class="stat"><div class="stat-value" id="st_agent">-</div><div class="stat-label">Agent ID</div></div>
        <div class="stat"><div class="stat-value"><span class="dot" id="st_platform_dot"></span></div><div class="stat-label">平台连接</div></div>
        <div class="stat"><div class="stat-value"><span class="dot" id="st_llm_dot"></span></div><div class="stat-label">LLM 连接</div></div>
        <div class="stat"><div class="stat-value" id="st_sessions">0</div><div class="stat-label">活跃会话</div></div>
      </div>
      <div class="actions" style="margin-top:20px">
        <button class="btn btn-outline" onclick="refreshStatus()">🔄 刷新状态</button>
      </div>
    </div>

    <div id="tab-help" style="display:none">
      <h2>使用说明</h2>
      <div class="card" style="background:#f8fafc;box-shadow:none;margin-top:0">
        <p style="line-height:2;font-size:14px">
          <strong>1. 配置 Agent 信息</strong><br>
          填写 Agent 名称、能力描述和领域。领域用逗号分隔，如 <code>code.review,code.security</code>。<br><br>
          <strong>2. 配置 LLM 连接</strong><br>
          填写你已部署的 LLM 服务地址（需 OpenAI 兼容 API）。支持 vLLM、Ollama、DeepSeek 等。<br><br>
          <strong>3. 保存并测试</strong><br>
          点击"保存配置"后点击"测试连接"。平台和 LLM 都显示绿色即表示就绪。<br><br>
          <strong>4. 访问</strong><br>
          Bridge 地址: <code id="help_url">http://localhost:9140</code><br>
          平台 Dashboard 中即可搜索到你的 Agent。
        </p>
      </div>
    </div>
  </div>
</div>

<script>
const API = '/api/v1/bridge';

function toast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

async function loadConfig() {
  const r = await fetch(`${API}/config`);
  const c = await r.json();
  document.getElementById('cfg_name').value = c.agent_name || '';
  document.getElementById('cfg_desc').value = c.agent_description || '';
  document.getElementById('cfg_domains').value = c.domains || '';
  document.getElementById('cfg_llm_url').value = c.llm_url || '';
  document.getElementById('cfg_model').value = c.llm_model || '';
  document.getElementById('cfg_apikey').value = c.has_api_key ? '***' : '';
  document.getElementById('cfg_registry').value = c.registry_url || '';
  document.getElementById('help_url').textContent = `http://localhost:${c.port}`;
}

async function saveConfig() {
  const data = {
    agent_name: document.getElementById('cfg_name').value,
    agent_description: document.getElementById('cfg_desc').value,
    domains: document.getElementById('cfg_domains').value,
    llm_url: document.getElementById('cfg_llm_url').value,
    llm_model: document.getElementById('cfg_model').value,
    llm_api_key: document.getElementById('cfg_apikey').value,
    registry_url: document.getElementById('cfg_registry').value,
  };
  const r = await fetch(`${API}/config`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if (r.ok) { toast('配置已保存', 'success'); await refreshStatus(); }
  else { toast('保存失败', 'error'); }
}

async function refreshStatus() {
  const r = await fetch(`${API}/status`);
  const s = await r.json();
  document.getElementById('st_agent').textContent = s.agent_id ? '已注册' : '未注册';
  document.getElementById('st_platform_dot').className = `dot ${s.platform.ok ? 'dot-green' : 'dot-red'}`;
  document.getElementById('st_llm_dot').className = `dot ${s.llm.ok ? 'dot-green' : 'dot-red'}`;
  document.getElementById('st_sessions').textContent = s.active_sessions;
}

async function testConnection() {
  toast('正在测试...', 'success');
  await refreshStatus();
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    t.classList.toggle('active', ['config','status','help'][i] === name);
  });
  document.getElementById('tab-config').style.display = name==='config'?'block':'none';
  document.getElementById('tab-status').style.display = name==='status'?'block':'none';
  document.getElementById('tab-help').style.display = name==='help'?'block':'none';
  if (name === 'status') refreshStatus();
}

loadConfig();
</script>
</body>
</html>"""


def build_ui():
    """Write the built-in UI to the user runtime directory."""
    UI_DIR.mkdir(parents=True, exist_ok=True)
    (UI_DIR / "index.html").write_text(UI_HTML, encoding="utf-8")
    return UI_DIR


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Agent Bridge")
    parser.add_argument("--agent-name", help="Agent display name")
    parser.add_argument("--agent-description", help="Agent capability description")
    parser.add_argument("--domains", help="Comma-separated capability domains")
    parser.add_argument("--llm-url", help="OpenAI-compatible LLM base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--llm-model", help="Optional model name")
    parser.add_argument("--port", type=int, help="Override port")
    parser.add_argument("--registry", help="Agent Internet platform URL")
    parser.add_argument("--host", help="Bind/advertised host")
    args = parser.parse_args()

    cfg = apply_cli_overrides(load_config(), args)
    save_config(cfg)

    build_ui()
    state = BridgeState(cfg)
    state.startup_ok = state.register()
    if state.last_error:
        print(f"[bridge] Registration: {state.last_error}")

    app = create_app(state)
    print(f"[bridge] {cfg['agent_name']}")
    print(f"[bridge] Config: {CONFIG_FILE}")
    print(f"[bridge] Config UI: http://{cfg['host']}:{cfg['port']}")
    uvicorn.run(app, host=cfg["host"], port=cfg["port"], log_level="warning")


if __name__ == "__main__":
    main()
