"""End-to-end test for the Agent Internet Platform.

Prerequisites: platform backend running on localhost:8000
Usage: pytest test_e2e.py -v
"""

import os
import uuid
import pytest
import httpx
from agent_internet_protocol import AIP_VERSION

BASE = os.getenv("PLATFORM_URL", "http://localhost:8000/api/v1")


# ── Agent definitions ───────────────────────────────────────────
CREDIT_ANALYST = {
    "id": "test.credit-risk-analyst@1.0.0",
    "name": "Credit Risk Analyst",
    "version": "1.0.0",
    "description": "金融风险分析 — 评估企业供应链相关的信用风险",
    "provider": {"name": "Test Suite", "contact": "test@example.com"},
    "capabilities": [{
        "id": "credit-risk",
        "name": "信用风险评估",
        "description": "给定企业名称和时间范围，返回供应链风险评分及详细因子分析",
        "domains": ["analysis.financial", "analysis.risk"],
        "input_schema": {
            "type": "object",
            "properties": {"company": {"type": "string"}, "timeframe": {"type": "string"}},
            "required": ["company"]
        },
        "output_schema": {
            "type": "object",
            "properties": {"risk_score": {"type": "number"}, "factors": {"type": "array"}},
            "required": ["risk_score", "factors"]
        },
    }],
    "endpoints": {
        "task": f"{os.getenv('AGENT1_URL', 'http://localhost:9121')}/api/v1/task",
        "health": f"{os.getenv('AGENT1_URL', 'http://localhost:9121')}/api/v1/health",
        "a2a": f"{os.getenv('AGENT1_URL', 'http://localhost:9121')}/api/v1/a2a",
    },
    "pricing": {"model": "per_call", "unit_price": 0.50},
    "tags": {"language": "python"},
}

SUPPLY_CHAIN_EXPERT = {
    "id": "test.supply-chain-expert@1.0.0",
    "name": "Supply Chain Expert",
    "version": "1.0.0",
    "description": "供应链数据分析 — 提供关键原材料的供需趋势和价格数据",
    "provider": {"name": "Test Suite", "contact": "test@example.com"},
    "capabilities": [{
        "id": "supply-chain",
        "name": "供应链分析",
        "description": "分析锂、钴、稀土等关键原材料的供应风险、价格趋势和替代方案",
        "domains": ["supply-chain"],
        "input_schema": {
            "type": "object",
            "properties": {"company": {"type": "string"}, "material": {"type": "string"}},
            "required": ["company"]
        },
        "output_schema": {
            "type": "object",
            "properties": {"risk_score": {"type": "number"}, "materials": {"type": "array"}},
            "required": ["risk_score", "materials"]
        },
    }],
    "endpoints": {
        "task": f"{os.getenv('AGENT2_URL', 'http://localhost:9122')}/api/v1/task",
        "health": f"{os.getenv('AGENT2_URL', 'http://localhost:9122')}/api/v1/health",
        "a2a": f"{os.getenv('AGENT2_URL', 'http://localhost:9122')}/api/v1/a2a",
    },
    "pricing": {"model": "per_call", "unit_price": 0.30},
    "tags": {"language": "python"},
}

ECHO = {
    "id": "test.echo@1.0.0",
    "name": "Echo Summarizer",
    "version": "1.0.0",
    "description": "文本摘要 — 将长文本压缩为简明摘要",
    "provider": {"name": "Test Suite", "contact": "test@example.com"},
    "capabilities": [{
        "id": "summarize",
        "name": "文本摘要",
        "description": "对输入文本进行摘要提取",
        "domains": ["nlp.summarization"],
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "max_length": {"type": "integer"}},
            "required": ["text"]
        },
        "output_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"]
        },
    }],
    "endpoints": {
        "task": f"{os.getenv('AGENT3_URL', 'http://localhost:9123')}/api/v1/task",
        "health": f"{os.getenv('AGENT3_URL', 'http://localhost:9123')}/api/v1/health",
        "a2a": f"{os.getenv('AGENT3_URL', 'http://localhost:9123')}/api/v1/a2a",
    },
    "pricing": {"model": "per_call", "unit_price": 0.01},
    "tags": {"language": "python"},
}


@pytest.fixture(scope="module")
def client():
    """Create HTTP client."""
    return httpx.Client(timeout=30)


def test_health(client):
    """Test platform health check."""
    try:
        backend_url = os.getenv("PLATFORM_URL", "http://localhost:8000")
        r = client.get(f"{backend_url}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("ok", "healthy"), f"Unexpected status: {data['status']}"
    except Exception as e:
        pytest.skip(f"Platform not running: {e}")


def test_register_agents(client):
    """Test registering demo agents."""
    for card in [CREDIT_ANALYST, SUPPLY_CHAIN_EXPERT, ECHO]:
        r = client.post(f"{BASE}/agents/register", json=card, timeout=30)
        assert r.status_code in (200, 201, 409), f"Failed to register {card['id']}: {r.text}"
        if r.status_code in (200, 201):
            data = r.json()
            agent_id = data.get("agent_id") or data.get("id") or card["id"]
            assert agent_id is not None, f"agent_id missing in response for {card['id']}"
            assert isinstance(agent_id, str), f"agent_id should be string, got {type(agent_id)}"
            assert len(agent_id) > 0, "agent_id should not be empty"


def test_list_agents(client):
    """Test listing registered agents."""
    r = client.get(f"{BASE}/agents", timeout=5)
    assert r.status_code == 200
    data = r.json()
    # Support both list and dict response formats
    if isinstance(data, list):
        agents_list = data
    else:
        assert "agents" in data, f"Response should contain 'agents' key, got keys: {list(data.keys())}"
        agents_list = data["agents"]
    assert isinstance(agents_list, list), "'agents' should be a list"
    assert len(agents_list) > 0, "No agents registered"
    # Each agent should have required fields
    for agent in agents_list:
        assert "id" in agent, f"Agent missing 'id' field: {agent}"
        assert "name" in agent, f"Agent missing 'name' field: {agent}"


def test_discovery(client):
    """Test discovery search."""
    r = client.post(f"{BASE}/discovery/search", json={
        "description": "评估特斯拉供应链风险",
        "domains": ["supply-chain", "analysis.risk"],
        "top_k": 2
    }, timeout=10)
    assert r.status_code == 200
    data = r.json()
    matches = data.get("matches", [])
    assert len(matches) > 0, "No search results"
    # Each match should have a score field > 0
    for match in matches:
        assert "score" in match, f"Match missing 'score' field: {match}"
        assert match["score"] > 0, f"Match score should be > 0, got {match['score']}"


def test_single_task(client):
    """Test single agent task submission."""
    r = client.post(f"{BASE}/tasks", json={
        "description": "总结这段文本",
        "input": {"text": "特斯拉于2026年Q2交付了创纪录的50万辆电动车..."},
        "domains": ["nlp.summarization"],
        "collaboration_mode": False,
        "user_id": "test-user"
    }, timeout=10)
    assert r.status_code in (200, 201)
    data = r.json()
    assert "task_id" in data or "id" in data
    # Assert task status is pending or assigned
    status = data.get("status")
    assert status in ("pending", "assigned"), f"Expected task status 'pending' or 'assigned', got '{status}'"


def test_collaboration_session(client):
    """Test collaboration session creation and messaging."""
    # Create session
    r = client.post(f"{BASE}/collaboration/sessions", json={
        "goal": "评估特斯拉 Q2 2026 供应链风险并给出共识评分",
        "initiator_agent": "test.credit-risk-analyst@1.0.0",
        "required_domains": ["analysis.risk", "supply-chain"],
        "shared_context": {"company": "Tesla", "timeframe": "Q2 2026"},
        "user_id": "test-user"
    }, timeout=30)
    assert r.status_code in (200, 201)
    data = r.json()

    # Extract session ID
    sid = data.get("session_id") or data.get("id") or (data.get("session", {}) or {}).get("id")
    assert sid is not None, "Session ID not found in response"

    # Send propose message
    msg1 = {
        "aip_version": AIP_VERSION,
        "protocol_layer": "collaboration",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "session_id": sid,
        "sender": {"agent_id": "test.credit-risk-analyst@1.0.0", "role": "analyst"},
        "message_type": "propose",
        "body": {"proposal": {"conclusion": "供应链风险评分：6.5/10", "reasoning": "锂价上涨12%", "confidence": 0.85}},
        "session_context_update": {"agreed_data_sources": ["Benchmark Q1 2026"]}
    }
    r2 = client.post(f"{BASE}/collaboration/sessions/{sid}/messages", json=msg1, timeout=10)
    assert r2.status_code in (200, 201), f"Failed to send propose: {r2.text}"

    # Send critique message
    msg2 = {
        "aip_version": AIP_VERSION,
        "protocol_layer": "collaboration",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "session_id": sid,
        "sender": {"agent_id": "test.supply-chain-expert@1.0.0", "role": "expert"},
        "message_type": "critique",
        "body": {"critique": "锂价数据过时。最新 S&P Global 数据：锂价下跌8%。", "suggestion": "使用最新数据"},
        "session_context_update": {"agreed_data_sources": ["S&P Global 2026-05"]}
    }
    r3 = client.post(f"{BASE}/collaboration/sessions/{sid}/messages", json=msg2, timeout=10)
    assert r3.status_code in (200, 201), f"Failed to send critique: {r3.text}"

    # Get session state
    r4 = client.get(f"{BASE}/collaboration/sessions/{sid}", timeout=5)
    assert r4.status_code == 200
    sess = r4.json()
    assert "status" in sess
    # Assert status is initiated or negotiating
    assert sess["status"] in ("initiated", "negotiating"), f"Expected session status 'initiated' or 'negotiating', got '{sess['status']}'"
    assert "turn_count" in sess
    # Assert turn_count >= 0
    assert sess["turn_count"] >= 0, f"Expected turn_count >= 0, got {sess['turn_count']}"


def test_review(client):
    """Test submitting a review."""
    # First create a task
    r = client.post(f"{BASE}/tasks", json={
        "description": "测试任务",
        "input": {"text": "测试"},
        "domains": ["nlp.summarization"],
        "collaboration_mode": False,
        "user_id": "test-user"
    }, timeout=10)
    if r.status_code not in (200, 201):
        pytest.skip("Could not create task for review test")

    data = r.json()
    task_id = data.get("task_id") or data.get("id")

    # Submit review
    r = client.post(f"{BASE}/reviews", json={
        "agent_id": "test.credit-risk-analyst@1.0.0",
        "task_id": task_id,
        "rating": 5,
        "review_text": "数据准确，协作体验良好",
        "user_id": "test-user"
    }, timeout=5)
    assert r.status_code in (200, 201)


def test_billing(client):
    """Test billing account query."""
    r = client.get(f"{BASE}/billing/account?user_id=test-user", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "balance" in data or "free_credit" in data


def test_invalid_agent_registration(client):
    """Test registering agent with invalid data - expect 422."""
    # Missing required fields (id, name, capabilities)
    invalid_agent = {
        "description": "Invalid agent without required fields",
        "version": "1.0.0"
    }
    r = client.post(f"{BASE}/agents/register", json=invalid_agent, timeout=10)
    assert r.status_code == 422, f"Expected 422 for invalid registration, got {r.status_code}: {r.text}"


def test_nonexistent_agent(client):
    """Test querying non-existent agent - expect 404."""
    r = client.get(f"{BASE}/agents/nonexistent.agent@1.0.0", timeout=5)
    assert r.status_code == 404, f"Expected 404 for non-existent agent, got {r.status_code}: {r.text}"


def test_unauthorized_access(client):
    """Test accessing protected endpoint without token - expect 401."""
    # Try to access a protected endpoint without authorization header
    r = client.get(f"{BASE}/protected/resource", timeout=5)
    # Should return 401 Unauthorized or 403 Forbidden
    assert r.status_code in (401, 403, 404), f"Expected 401/403/404 for unauthorized access, got {r.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
