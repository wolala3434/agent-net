"""API path constants for the Agent Internet SDK."""

API_PREFIX = "/api/v1"

# Registry
AGENTS_REGISTER = f"{API_PREFIX}/agents/register"
AGENTS_HEARTBEAT = f"{API_PREFIX}/agents/{{agent_id}}/heartbeat"
AGENTS_DEREGISTER = f"{API_PREFIX}/agents/{{agent_id}}"
AGENTS_SEARCH = f"{API_PREFIX}/discovery/search"
AGENTS_GET = f"{API_PREFIX}/agents/{{agent_id}}"

# Discovery
DISCOVERY_SEARCH = f"{API_PREFIX}/discovery/search"

# Collaboration
COLLAB_SESSIONS = f"{API_PREFIX}/collaboration/sessions"
COLLAB_SESSION_GET = f"{API_PREFIX}/collaboration/sessions/{{session_id}}"
COLLAB_MESSAGES = f"{API_PREFIX}/collaboration/sessions/{{session_id}}/messages"
COLLAB_MESSAGES_GET = f"{API_PREFIX}/collaboration/sessions/{{session_id}}/messages"

# Agent endpoints
AGENT_TASK = f"{API_PREFIX}/task"
AGENT_HEALTH = f"{API_PREFIX}/health"
AGENT_A2A = f"{API_PREFIX}/a2a"
