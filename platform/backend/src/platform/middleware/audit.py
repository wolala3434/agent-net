"""
Audit logging middleware for tracking critical operations.

Records:
  - Agent registration/deletion
  - Session creation/completion
  - Billing transactions
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Dedicated audit logger - writes to separate file/handler
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False

# Prevent duplicate handlers on reload
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - AUDIT - %(message)s")
    )
    audit_logger.addHandler(handler)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log critical operations for audit purposes.
    
    Tracked operations:
      - POST /api/v1/agents/register (Agent registered)
      - DELETE /api/v1/agents/{id} (Agent deleted)
      - POST /api/v1/collaboration/sessions (Session created)
      - POST /api/v1/billing/charge (Transaction recorded)
    """

    AUDIT_PATHS: dict[str, dict[str, Any]] = {
        "POST:/api/v1/agents/register": {
            "event": "agent_registered",
            "extract_id": lambda body: body.get("id", "unknown"),
        },
        "DELETE:/api/v1/agents/": {
            "event": "agent_deleted",
            "extract_id": lambda path: path.split("/")[-1],
        },
        "POST:/api/v1/collaboration/sessions": {
            "event": "session_created",
            "extract_id": lambda body: body.get("initiator_agent", "unknown"),
        },
        "POST:/api/v1/billing/charge": {
            "event": "billing_transaction",
            "extract_id": lambda body: body.get("agent_id", "unknown"),
        },
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        method = request.method

        # Check if this is an auditable operation
        audit_config = None
        
        for key, config in self.AUDIT_PATHS.items():
            if path.startswith(key.split(":")[1]) and method == key.split(":")[0]:
                audit_config = config
                break

        if not audit_config:
            return await call_next(request)

        # Read request body for audit info
        body_bytes = await request.body()
        body_data = {}
        if body_bytes:
            try:
                body_data = json.loads(body_bytes.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Process request
        response = await call_next(request)

        # Log audit event if successful
        if 200 <= response.status_code < 300:
            event = audit_config["event"]
            
            # Extract resource ID
            if "register" in path or "sessions" in path or "charge" in path:
                resource_id = audit_config["extract_id"](body_data)
            else:
                resource_id = audit_config["extract_id"](path)

            audit_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "resource_id": resource_id,
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "client_ip": request.client.host if request.client else "unknown",
            }

            audit_logger.info(json.dumps(audit_log, ensure_ascii=False))

        return response
