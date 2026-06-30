"""Test async forwarding fix — POST /messages should return fast."""
import httpx
import json
import time
import uuid
import sys

c = httpx.Client(timeout=60)
ARCHITECT = "llm-agents.code-architect@1.0.0"

r = c.post("http://localhost:8000/api/v1/collaboration/sessions", json={
    "initiator_agent": ARCHITECT,
    "goal": "安全评估秒杀系统",
    "required_domains": ["code.security"],
})
sid = r.json()["id"]
print(f"Session: {sid}")

# Send propose — should return FAST (async forwarding)
t0 = time.time()
r = c.post(f"http://localhost:8000/api/v1/collaboration/sessions/{sid}/messages", json={
    "aip_version": "1.0", "protocol_layer": "collaboration",
    "message_id": f"msg_{uuid.uuid4().hex[:12]}", "session_id": sid,
    "timestamp": "2026-06-15T00:00:00Z",
    "sender": {"agent_id": ARCHITECT, "role": "initiator"},
    "message_type": "propose",
    "body": {"proposal": {"conclusion": "系统需要HMAC签名+幂等token+限流"}}
}, timeout=15)
elapsed = time.time() - t0
fast = "FAST" if elapsed < 5 else "SLOW"
result = "PASS" if r.status_code in (200, 201) else "FAIL"
print(f"POST /messages -> {r.status_code} ({elapsed:.1f}s) [{result}] [{fast}]")

# Wait for async forwarding to deliver + Auditor to respond
print("Waiting for async response (40s max)...")
got_response = False
for i in range(8):
    time.sleep(5)
    r = c.get(f"http://localhost:8000/api/v1/collaboration/sessions/{sid}")
    s = r.json()
    t = s.get("turn_count", 0)
    print(f"  [{i*5}s] turns={t}")
    if t >= 2:
        got_response = True
        break

# Show results
msgs_r = c.get(f"http://localhost:8000/api/v1/collaboration/sessions/{sid}/messages")
msgs = msgs_r.json() if isinstance(msgs_r.json(), list) else msgs_r.json().get("messages", [])
print(f"\nResults ({len(msgs)} turns):")
for m in msgs:
    body = m.get("body", m.get("body_json", "{}"))
    if isinstance(body, str):
        body = json.loads(body)
    print(f"[{m.get('turn_number')}] {m.get('sender_id', '?')[:45]} -> {m.get('message_type')}")
    print(f"  {json.dumps(body, ensure_ascii=False)[:250]}")
    print()

if elapsed < 5:
    print("PASS: Message POST returned fast (async forwarding works)")
else:
    print("FAIL: Message POST blocked by forwarding")

if got_response:
    print("PASS: Auditor auto-responded asynchronously")
else:
    print("WARN: Auditor did not respond within 40s")

sys.exit(0 if (elapsed < 5 and got_response) else 1)
