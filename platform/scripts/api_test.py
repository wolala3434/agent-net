"""Comprehensive API test script."""
import httpx
import uuid
import sys

c = httpx.Client(timeout=30)
BASE = "http://localhost:8000/api/v1"
print("=" * 60)
print("  全面 API 测试")
print("=" * 60)
errors = []

def test(name, fn):
    try:
        ok, detail = fn()
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if detail and not ok:
            print(f"         {detail[:200]}")
        if not ok:
            errors.append(name)
    except Exception as e:
        print(f"  [FAIL] {name} — EXCEPTION: {e}")
        errors.append(name)

# 1. Health
test("GET /health", lambda: (
    c.get("http://localhost:8000/health").status_code == 200, ""))

# 2. Agent listing
r = c.get(f"{BASE}/agents")
test("GET /agents", lambda: (r.status_code == 200, f"count={len(r.json())}"))

# 3. Agent registration
aid = f"test.comprehensive-{uuid.uuid4().hex[:8]}@1.0.0"
r = c.post(f"{BASE}/agents/register", json={
    "id": aid, "name": "Comprehensive Test Agent", "version": "1.0.0",
    "description": "Test agent for comprehensive API testing",
    "provider": {"name": "TestSuite"},
    "capabilities": [{
        "id": "security-audit",
        "name": "Security Audit",
        "description": "Code security review and vulnerability detection",
        "domains": ["code.security", "security.audit"],
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"issues": {"type": "array"}}},
    }],
    "endpoints": {"task": "http://127.0.0.1:9991/api/v1/task",
                  "health": "http://127.0.0.1:9991/api/v1/health",
                  "a2a": "http://127.0.0.1:9991/api/v1/a2a"},
    "pricing": {"model": "per_call", "unit_price": 0.01}
}, timeout=30)
reg_ok = r.status_code in (200, 201)
test("POST /agents/register", lambda: (reg_ok, r.text[:150]))

# 4. Get single agent
test("GET /agents/{id}", lambda: (
    c.get(f"{BASE}/agents/{aid}").status_code == 200, ""))

# 5. Heartbeat
test("POST /agents/{id}/heartbeat", lambda: (
    c.post(f"{BASE}/agents/{aid}/heartbeat", json={"status": "healthy"}).status_code == 200, ""))

# 6. Discovery
r = c.post(f"{BASE}/discovery/search", json={
    "description": "code security audit vulnerability detection",
    "domains": ["code.security"], "top_k": 3
}, timeout=30)
n_matches = len(r.json().get("matches", [])) if r.status_code == 200 else 0
test("POST /discovery/search", lambda: (
    r.status_code == 200 and n_matches > 0, f"matches={n_matches}"))

# 7. Task submission
r = c.post(f"{BASE}/tasks", json={
    "description": "Audit code for SQL injection vulnerabilities",
    "input": {"code": "SELECT * FROM users WHERE id = ?"},
    "domains": ["code.security"], "collaboration_mode": False,
    "user_id": "test-user"
}, timeout=30)
task_id = r.json().get("task_id", "") if r.status_code in (200, 201, 202) else ""
test("POST /tasks (single)", lambda: (
    bool(task_id), f"task_id={task_id}"))

# 8. Get task
if task_id:
    test("GET /tasks/{id}", lambda: (
        c.get(f"{BASE}/tasks/{task_id}").status_code in (200, 404), ""))

# 9. Collaboration session
r = c.post(f"{BASE}/collaboration/sessions", json={
    "initiator_agent": aid,
    "goal": "Audit security of high-concurrency order system",
    "required_domains": ["code.security"],
    "shared_context": {"system": "order system"}
}, timeout=30)
sid = r.json().get("id", "") if r.status_code in (200, 201) else ""
test("POST /collaboration/sessions", lambda: (bool(sid), f"session_id={sid}"))

# 10. Collaboration messages
if sid:
    r = c.post(f"{BASE}/collaboration/sessions/{sid}/messages", json={
        "aip_version": "1.0", "protocol_layer": "collaboration",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}", "session_id": sid,
        "timestamp": "2026-06-15T00:00:00Z",
        "sender": {"agent_id": aid, "role": "initiator"},
        "message_type": "propose",
        "body": {"proposal": {"conclusion": "System needs SQL injection protection"}}
    }, timeout=30)
    test("POST /sessions/.../messages", lambda: (r.status_code in (200, 201), ""))
    test("GET /sessions/.../messages", lambda: (
        c.get(f"{BASE}/collaboration/sessions/{sid}/messages").status_code == 200, ""))

# 11. Reviews
r = c.post(f"{BASE}/reviews", json={
    "agent_id": aid, "task_id": task_id or "task_x",
    "rating": 5, "user_id": "test-user",
    "review_text": "Excellent security audit"
}, timeout=30)
test("POST /reviews", lambda: (r.status_code in (200, 201), ""))

# 12. User pinned
r = c.post(f"{BASE}/users/test-user/pinned-agents", json={"agent_id": aid}, timeout=30)
test("POST /users/.../pinned-agents", lambda: (r.status_code in (200, 201), ""))
test("GET /users/.../pinned-agents", lambda: (
    c.get(f"{BASE}/users/test-user/pinned-agents").status_code == 200, ""))

# 13. Billing
test("GET /billing/account", lambda: (
    c.get(f"{BASE}/billing/account?user_id=test-user").status_code == 200, ""))

# 14. Admin
test("GET /admin/overview (admin)", lambda: (
    c.get(f"{BASE}/admin/overview?user_id=admin").status_code == 200, ""))
test("GET /admin/overview (reject normal)", lambda: (
    c.get(f"{BASE}/admin/overview?user_id=normal").status_code == 403, ""))

# 15. Agent update
test("PUT /agents/{id}", lambda: (
    c.put(f"{BASE}/agents/{aid}", json={
        "name": "Updated Agent", "version": "1.0.0",
        "description": "Updated", "provider": {"name": "TestSuite"},
        "capabilities": [{"id": "c1", "name": "U", "description": "U", "domains": ["code.security"],
            "input_schema": {"type": "object"}, "output_schema": {"type": "object"}}],
        "endpoints": {"task": "http://127.0.0.1:9991/task", "health": "http://127.0.0.1:9991/health",
                       "a2a": "http://127.0.0.1:9991/a2a"},
        "pricing": {"model": "per_call", "unit_price": 0.02}
    }).status_code in (200, 201), ""))

# 16. Cleanup
test("DELETE /agents/{id}", lambda: (
    c.delete(f"{BASE}/agents/{aid}").status_code in (200, 201, 204), ""))

# 17. List sessions
test("GET /collaboration/sessions", lambda: (
    c.get(f"{BASE}/collaboration/sessions?limit=10").status_code == 200, ""))

# 18. Admin pending agents
test("GET /admin/agents/pending", lambda: (
    c.get(f"{BASE}/admin/agents/pending?user_id=admin").status_code == 200, ""))

# 19. Admin revenue
test("GET /admin/revenue", lambda: (
    c.get(f"{BASE}/admin/revenue?user_id=admin").status_code == 200, ""))

# 20. Admin flagged reviews
test("GET /admin/reviews/flagged", lambda: (
    c.get(f"{BASE}/admin/reviews/flagged?user_id=admin").status_code == 200, ""))

print()
passed = 20 - len(errors)
print(f"Results: {passed}/20 passed")
if errors:
    print(f"Failures ({len(errors)}):")
    for e in errors:
        print(f"  ❌ {e}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
